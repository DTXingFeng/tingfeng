from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from typing import List, Set

# 记录正在处理记忆固化的群组，防止并发冲突导致重复记忆
active_consolidation_groups: Set[int] = set()

async def consolidate_memories(group_id: int):
    """
    将群组中未处理的聊天记录总结为长期事实并存入向量库
    """
    if group_id in active_consolidation_groups:
        return
    
    try:
        active_consolidation_groups.add(group_id)
        
        # 1. 获取未处理的消息 (为了保证总结质量，建议攒够 50 条再处理，单次最多处理 100 条)
        raw_logs = db_manager.get_unprocessed_logs(group_id, limit=100)
        if len(raw_logs) < 50: 
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
            f"你现在是'{bot_config.bot_name}'的深度记忆固化模块。你的任务是从最近的群聊记录中提取具有长期社交价值的‘记忆碎片’。\n\n"
            "### 提取准则：\n"
            "1. **记忆碎片化**：将复杂的对话拆解为独立、简洁的陈述句。每条记忆应包含‘主体’和‘行为/状态’。\n"
            "2. **社交价值优先**：关注用户的偏好、职业、所在地、重要经历、对特定事物的看法、以及与你的互动细节。\n"
            "3. **剔除冗余**：过滤掉无意义的打招呼、纯表情包交流、时效性极短的信息（如‘我下楼买个烟’）。\n"
            "4. **客观与主观并存**：既记录客观事实（他在北京），也记录主观态度（他讨厌加班）。\n\n"
            "### 任务 1：提取记忆碎片 (Memory Shards)\n"
            "这些碎片将被存入向量数据库，用于后续的语义检索。请确保描述具有代表性，即使未来的提问词不完全一致，也能通过含义关联到。\n"
            "格式：'SHARD|内容'。例如：'SHARD|刑风最近在研究神经网络，由于模型训练失败显得很暴躁'。\n\n"
            "### 任务 2：更新用户画像 (User Profile)\n"
            "更新你对参与者的整体刻板印象。要求极度精炼，包含身份标签和性格特征。\n"
            "格式：'PROFILE|用户名|标签A,标签B,性格描述'。\n\n"
            "### 任务 3：提取用户专属往事 (User Stories)\n"
            "提取关于某个用户的特定、具体的关键事件或属性。\n"
            "格式：'STORY|用户名|事件描述'。\n\n"
            "### 任务 4：情感共鸣评估 (Emotional Tone)\n"
            "评估这批聊天对你（听风）的情感冲击。你感到被重视了吗？还是被冷落了？\n"
            "格式：'EMO|数值' (-20 到 20)。\n\n"
            "如果没有值得记录的内容，请回复‘无’。\n\n"
            f"### 待处理聊天记录：\n{chat_content}"
        )

        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3 # 稍微给一点发散空间，有助于提取更有灵性的记忆
        )
        
        output = response.choices[0].message.content.strip()
        if output == "无" or not output:
            db_manager.mark_as_processed(msg_ids)
            return

        # 3. 解析并存入
        lines = [line.strip("- ").strip() for line in output.split("\n") if line.strip()]
        shards = []
        mood_adjustment = 0
        for line in lines:
            if line.startswith("PROFILE|"):
                parts = line.split("|")
                if len(parts) >= 3:
                    u_name, u_profile = parts[1].strip(), parts[2].strip()
                    db_manager.update_user_impression(group_id, u_name, u_profile)
            elif line.startswith("STORY|"):
                parts = line.split("|")
                if len(parts) >= 3:
                    u_name, u_story = parts[1].strip(), parts[2].strip()
                    db_manager.add_user_specific_memory(group_id, u_name, u_story)
            elif line.startswith("EMO|"):
                parts = line.split("|")
                if len(parts) >= 2:
                    try:
                        mood_adjustment = int(parts[1].strip())
                    except:
                        pass
            elif line.startswith("SHARD|"):
                content = line[6:].strip()
                if len(content) > 5:
                    shards.append(content)
            else:
                # 兼容性：如果 AI 没按格式带前缀，但内容像事实
                if "|" not in line and len(line) > 5:
                    shards.append(line)

        # 应用氛围调整
        db_manager.update_mood(group_id, mood_adjustment)

        if shards:
            # 批量获取向量
            vectors = await get_embeddings(shards)
            for i, shard in enumerate(shards):
                vector_db.add_memory(
                    group_id=group_id, 
                    text=f"[碎片] {shard}", 
                    vector=vectors[i],
                    metadata={"type": "shard"}
                )
            
            print(f"群 {group_id} 记忆固化完成：提取了 {len(shards)} 条碎片。")

        # 4. 标记这些原始消息为已处理
        db_manager.mark_as_processed(msg_ids)

    except Exception as e:
        print(f"记忆固化失败: {e}")
    finally:
        active_consolidation_groups.discard(group_id)
