from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from typing import List, Optional, Dict
import random
import re

async def get_chat_reply(group_id: int, user_name: str, current_msg: str) -> Dict[str, any]:
    """
    获取 AI 回复逻辑
    返回格式: {"text": str, "sticker": Optional[str]}
    """
    # 1. 获取配置
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return f"唔... {bot_config.bot_name}好像断网了，找不到模型配置哒~ (＞﹏＜)"

    # 2. 准备历史记录
    # 获取最近 20 条记录作为短期记忆
    history = db_manager.get_chat_log(group_id, limit=20)
    
    # 获取相关长期记忆 (RAG)
    long_term_memories = []
    user_profile = db_manager.get_user_impression(group_id, user_name)
    user_specific_memories = db_manager.get_user_specific_memories(group_id, user_name, limit=5)
    
    try:
        # 将当前消息向量化
        query_vectors = await get_embeddings([current_msg])
        # 搜索最相关的 3 条往事
        long_term_memories = vector_db.query_memory(group_id, query_vectors[0], n_results=3)
    except Exception as e:
        print(f"检索长期记忆失败: {e}")

    # 3. 构造 Prompt
    system_prompt = bot_config.prompt
    if bot_config.identity:
        system_prompt = f"{bot_config.identity}\n\n{system_prompt}"

    # 引导 AI 使用表情包
    system_prompt += (
        "\n\n### 表情包使用指南：\n"
        "如果你觉得当前语境适合发送表情包，请在回复文本的最后加上 '[表情:标签名]'。\n"
        "可选标签：开心、大哭、暴躁、委屈、傲娇、得意、摸摸头、疑惑、震惊。\n"
        "例如：'大哥哥最棒了！[表情:开心]'"
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
            temperature=0.8, # 稍微高一点让萝莉更有趣
        )
        
        reply_content = response.choices[0].message.content.strip()
        
        # 提取并处理表情包标签
        sticker_url = None
        match = re.search(r'\[表情:(.*?)\]', reply_content)
        if match:
            tag = match.group(1).strip()
            # 从数据库中随机选一个对应标签的表情包
            available_stickers = db_manager.get_stickers_by_tag(tag)
            if available_stickers:
                sticker_url = random.choice(available_stickers)["file_id"]
            # 移除文本中的标签
            reply_content = re.sub(r'\[表情:.*?\]', '', reply_content).strip()

        # 移除可能的 "self:" 或 "听风:" 前缀（如果 AI 自动带上的话）
        if reply_content.startswith("self:"):
            reply_content = reply_content[5:].strip()
        elif reply_content.startswith(f"{bot_config.bot_name}:"):
            reply_content = reply_content[len(bot_config.bot_name)+1:].strip()
            
        return {"text": reply_content, "sticker": sticker_url}

    except Exception as e:
        print(f"AI 回复生成出错: {e}")
        return {"text": f"唔... {bot_config.bot_name}脑子突然卡住了哒~ (＞﹏＜)", "sticker": None}
