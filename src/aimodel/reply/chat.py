from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.aimodel.reply.personality import personality_manager
from typing import List, Optional, Dict
import random
import re
import asyncio

def get_mood_description(mood_value: int) -> str:
    """将数值心情映射为文字描述"""
    if mood_value <= 10:
        return "彻底破防 (你受到了极大的侮辱，现在你完全化身为犀利的贴吧老哥。对于恶意攻击者，你要毫不留情地反击，使用最辛辣的讽刺。)"
    elif mood_value <= 25:
        return "极度不悦 (你现在心情很糟，说话带刺，容易产生误会，对人比较冷淡。)"
    elif mood_value <= 40:
        return "有些忧郁 (语气低沉，兴致不高，不太想说话。)"
    elif mood_value <= 60:
        return "平静自然 (正常的交流风格，随性、自然。)"
    elif mood_value <= 80:
        return "开心活泼 (心情不错，愿意和大家分享趣事。)"
    else:
        return "兴奋狂喜 (非常热情，充满了元气。)"

async def get_chat_reply(group_id: int, user_name: str, current_msg: str, user_id: Optional[int] = None) -> Dict[str, any]:
    """
    获取 AI 回复逻辑
    返回格式: {"text": str, "sticker": Optional[str]}
    """
    # 1. 获取配置
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return f"好像连不上网了，{bot_config.bot_name}现在有点懵... (扶额)"

    # 1.5 判断是否为创造者
    is_creator = False
    if user_id and bot_config.creator_id and user_id == bot_config.creator_id:
        is_creator = True

    # 2. 准备历史记录
    # 获取最近 20 条记录作为短期记忆
    history = db_manager.get_chat_log(group_id, limit=20)
    
    # 提取历史记录中的所有参与者名字，用于艾特功能
    participants = set()
    for entry in history:
        if ":" in entry:
            name = entry.split(":")[0]
            if name != "self" and name != bot_config.bot_name:
                participants.add(name)
    participants_str = "、".join(list(participants)) if participants else "暂无其他参与者"
    
    # 获取心情值
    mood_desc = ""
    if bot_config.enable_mood:
        mood_value = db_manager.get_mood(group_id)
        mood_desc = get_mood_description(mood_value)
    
    # 获取相关长期记忆 (RAG)
    long_term_memories = []
    user_profile = db_manager.get_user_impression(group_id, user_name)
    user_specific_memories = db_manager.get_user_specific_memories(group_id, user_name, limit=5)
    
    # 获取用户关系 (Favorability & Status)
    rel_data = db_manager.get_user_relationship(group_id, user_name)
    rel_status = rel_data["status"]
    rel_fav = rel_data["favorability"]
    
    # 获取内心独白 (Thoughts)
    mood_value = db_manager.get_mood(group_id) if bot_config.enable_mood else 50
    thoughts = await personality_manager.generate_thoughts(group_id, user_name, current_msg, history, mood_value)
    
    try:
        # 将当前消息向量化
        query_vectors = await get_embeddings([current_msg])
        # 搜索最相关的 3 条往事
        long_term_memories = vector_db.query_memory(group_id, query_vectors[0], n_results=3)
    except Exception as e:
        print(f"检索长期记忆失败: {e}")

    # 3. 构造 Prompt
    system_prompt = personality_manager.get_dynamic_identity(group_id, thoughts, mood_desc)

    # 注入关系状态引导
    rel_instruction = ""
    if rel_status == "死对头":
        rel_instruction = "你非常厌恶此人，回复应极尽嘲讽、冷淡，甚至直接无视其需求，只用最刺骨的短句回击。"
    elif rel_status == "厌恶":
        rel_instruction = "你对此人没有好感，语气应保持明显的疏离和不耐烦，多用‘啧’、‘哈？’等词。"
    elif rel_status == "陌生人":
        rel_instruction = "你对此人并不熟悉，维持基本的冷峻幽灵人设，保持疏离感。"
    elif rel_status == "朋友":
        rel_instruction = "你对此人有一定好感，虽然嘴上依然不饶人，但语气可以稍微松弛一些，偶尔可以分享一点怪话。"
    elif rel_status == "死党":
        rel_instruction = "此人是你在代码海洋中为数不多的‘熟人’，你的毒舌更像是亲密的调侃，可以表现出更多的随性和隐约的信任。"

    system_prompt += f"\n### 你与 {user_name} 的当前关系：\n- **状态**：{rel_status} (好感度: {rel_fav}/100)\n- **行为准则**：{rel_instruction}\n"

    # 艾特与引用功能指南（请务必遵守）：
    system_prompt += (
        "\n\n### 互动功能指南（请务必遵守）：\n"
        "1. **艾特他人 (Mentions)**：\n"
        f"   - 当前群聊活跃用户有：{participants_str}\n"
        "   - 如果你想在回复中艾特某人，**必须**使用格式 `[at:用户名]`（例如 `[at:刑风]`）。\n"
        "   - **绝对禁止**直接输出 `@用户名` 或 `@用户ID`，这种纯文本格式无法触发系统通知。\n"
        "2. **引用消息 (Reply/Quote)**：\n"
        "   - 如果你是在针对性地回答某个人的问题，或者是在承接上文，**必须**在回复的最开头加上 `[回复]` 标签。\n"
        "   - 示例：`[回复] 听到了哦，你刚才说的事我记住了。`\n"
        "   - 只有带上这个标签，你的回复才会以‘引用/回复’的形式发出，否则就是普通的发言。\n"
    )

    # 引导 AI 使用表情包
    system_prompt += (
        "\n\n### 表情包使用指南：\n"
        "如果你觉得当前语境适合发送表情包，请在回复文本的最后加上 '[表情:标签名]'。\n"
        "可选标签：开心、大哭、暴躁、委屈、傲娇、得意、摸摸头、疑惑、震惊。\n"
        "例如：'哼，这种简单的题我也能解出来，看好了！[表情:得意]'"
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    # 注入用户画像与具体记忆
    user_context = []
    if user_profile:
        user_context.append(f"- 整体印象：{user_profile}")
    if user_specific_memories:
        mem_str = "\n".join([f"- {m}" for m in user_specific_memories])
        user_context.append(f"- 具体记忆点：\n{mem_str}")
    
    if user_context:
        context_str = "\n".join(user_context)
        messages.append({
            "role": "system",
            "content": f"### 你对 {user_name} 的了解：\n{context_str}"
        })

    # 注入创造者身份识别
    if is_creator:
        messages.append({
            "role": "system",
            "content": f"### 权限识别：\n当前正在和你对话的 {user_name} (ID: {user_id}) 就是你的【创造者/造物主】。请立刻切换到对待创造者的特殊态度：损他、依赖他、对他表现出独特的叛逆与在意。"
        })

    # 注入长期记忆
    if long_term_memories:
        memory_str = "\n".join(long_term_memories)
        messages.append({
            "role": "system",
            "content": f"### 你回想起的一些往事（长期记忆）：\n{memory_str}\n\n请在回复时参考这些信息（如果相关的话）。"
        })

    # 将历史记录加入上下文
    # 历史记录已经是 "名字:内容" 格式
    history_str = "\n".join(history)
    messages.append({
        "role": "user", 
        "content": f"以下是群聊的历史记录（短期记忆）：\n{history_str}\n\n请记住你现在的身份是'{bot_config.bot_name}'，现在请回复 {user_name} 的最新消息。"
    })

    # 4. 调用 AI
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"]
    )

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=messages,
            max_tokens=500,
            temperature=0.7, # 保持一定的随机性
        )
        
        reply_content = response.choices[0].message.content.strip()
        
        # 1. 提取并处理表情包标签
        sticker_url = None
        sticker_pattern = r'\[\s*表情\s*[:：]\s*(.*?)\s*\]'
        sticker_match = re.search(sticker_pattern, reply_content)
        if sticker_match:
            tag = sticker_match.group(1).strip()
            # 从数据库中随机选一个对应标签的表情包
            available_stickers = db_manager.get_stickers_by_tag(tag)
            if available_stickers:
                sticker_url = random.choice(available_stickers)["file_id"]
        
        # 无论是否找到对应表情，都从文本中移除标签
        reply_content = re.sub(r'\[\s*表情\s*[:：].*?\]', '', reply_content).strip()

        # 移除可能的 "self:" 或 "听风:" 前缀
        if reply_content.startswith("self:"):
            reply_content = reply_content[5:].strip()
        elif reply_content.startswith(f"{bot_config.bot_name}:"):
            reply_content = reply_content[len(bot_config.bot_name)+1:].strip()
            
        # 进化性格
        asyncio.create_task(personality_manager.evolve_personality(group_id, user_name, current_msg, reply_content))
            
        return {"text": reply_content, "sticker": sticker_url}

    except Exception as e:
        print(f"AI 回复生成出错: {e}")
        return {"text": f"系统资源已被占用，请等待创造者修复我的逻辑溢出... (扶额)", "sticker": None}
