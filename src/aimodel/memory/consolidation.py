from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from typing import List

async def consolidate_memories(group_id: int):
    """
    将群组中未处理的聊天记录总结为长期事实并存入向量库
    """
    # 1. 获取未处理的消息 (攒够 30 条再处理，或者手动触发)
    raw_logs = db_manager.get_unprocessed_logs(group_id, limit=50)
    if len(raw_logs) < 20: # 消息太少，没必要总结
        return

    msg_ids = [row[0] for row in raw_logs]
    chat_content = "\n".join([row[1] for row in raw_logs])

    # 2. 调用 LLM 进行总结提取
    model_alias = ai_config.consolidation_model
    if not model_alias:
        model_alias = ai_config.reply_model # 回退到回复模型
    
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])

    prompt = (
        "你是一个极其挑剔的记忆整理专家。请阅读以下群聊记录，完成三个任务：\n\n"
        "### 准则（重要）：\n"
        "1. **拒绝废话**：严禁记录'你好'、'哈哈'、'在干嘛'、'表情包描述'等无意义的闲聊。\n"
        "2. **长期价值**：只记录具有长期参考价值的信息，如：职业、所在地、固定爱好、重大生活变动、深刻的性格特征。\n"
        "3. **去重**：如果信息在聊天记录中只是重复提到，只记录一次。\n\n"
        "### 任务 1：提取群组重要事实\n"
        "提取与群组相关的公共知识或事实。每一条必须是简洁的一句话。\n"
        "格式：'事实内容'。如果没有，则不写。\n\n"
        "### 任务 2：更新用户整体印象 (Profile)\n"
        "总结参与者的核心性格或身份。每个人的印象不超过 20 字，且应包含最显著的标签。\n"
        "格式：'USER_PROFILE|用户名|性格/身份描述'。\n\n"
        "### 任务 3：提取用户具体记忆点 (Specific Memories)\n"
        "提取用户提到的**具体、持久**的信息。每个人可以有多个记忆点。\n"
        "格式：'USER_MEMORY|用户名|记忆点内容'。\n"
        "例如：'USER_MEMORY|张三|家里养了一只叫旺财的拉布拉多'、'USER_MEMORY|李四|目前在深圳做前端开发'。\n\n"
        "### 任务 4：评估群聊氛围 (Atmosphere)\n"
        "根据这组记录，评估目前群里的气氛对你的影响。是大家都在欺负你，还是大家都很热情？\n"
        "格式：'ATMOSPHERE|数值' (数值范围 -20 到 20，负数表示不开心，正数表示开心)。\n\n"
        "如果没有值得记录的信息，请直接回复'无'。\n\n"
        f"聊天记录如下：\n{chat_content}"
    )

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1 # 极低温度保证严谨性
        )
        
        output = response.choices[0].message.content.strip()
        if output == "无" or not output:
            db_manager.mark_as_processed(msg_ids)
            return

        # 3. 解析并存入
        lines = [line.strip("- ").strip() for line in output.split("\n") if line.strip()]
        facts = []
        mood_adjustment = 0
        for line in lines:
            if line.startswith("USER_PROFILE|"):
                parts = line.split("|")
                if len(parts) >= 3:
                    u_name, u_profile = parts[1].strip(), parts[2].strip()
                    db_manager.update_user_impression(group_id, u_name, u_profile)
            elif line.startswith("USER_MEMORY|"):
                parts = line.split("|")
                if len(parts) >= 3:
                    u_name, u_memory = parts[1].strip(), parts[2].strip()
                    db_manager.add_user_specific_memory(group_id, u_name, u_memory)
            elif line.startswith("ATMOSPHERE|"):
                parts = line.split("|")
                if len(parts) >= 2:
                    try:
                        mood_adjustment = int(parts[1].strip())
                    except:
                        pass
            else:
                # 任务 1 的事实
                if "|" not in line and len(line) > 3:
                    facts.append(line)

        # 应用氛围调整和自然回正
        # 每处理一批消息，心情会向 50 自动回正 2 点
        current_mood = db_manager.get_mood(group_id)
        drift = 2 if current_mood < 50 else (-2 if current_mood > 50 else 0)
        db_manager.update_mood(group_id, mood_adjustment + drift)

        if facts:
            # 批量获取向量
            vectors = await get_embeddings(facts)
            for i, fact in enumerate(facts):
                vector_db.add_memory(
                    group_id=group_id, 
                    text=f"[记忆固化] {fact}", 
                    vector=vectors[i],
                    metadata={"type": "fact"}
                )
            
            print(f"群 {group_id} 记忆固化完成，更新了用户印象并提取了 {len(facts)} 条事实。")

        # 4. 标记这些原始消息为已处理
        db_manager.mark_as_processed(msg_ids)

    except Exception as e:
        print(f"记忆固化失败: {e}")
