from openai import AsyncOpenAI
from nonebot.adapters.onebot.v11 import Bot
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.aimodel.reply.personality import personality_manager
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from src.utils.thinking_mode import thinking_handler, stream_with_thinking_mode
from src.mcp.registry import tool_registry
from typing import List, Optional, Dict, Any, cast
from collections import deque
import random
import re
import asyncio
import json

logger = get_logger(__name__)

# 最近回复缓存（防复读机制）
# 结构: {group_id: deque(["reply1", "reply2", ...])}
# 每个群组保留最近5条回复
_recent_replies_cache: Dict[int, deque] = {}


def clean_reply_format(text: str) -> str:
    """
    清理消息文本中的QQ引用格式 [回复@名字:内容] 和富文本标签

    Args:
        text: 原始消息文本

    Returns:
        清理后的消息文本
    """
    if not text:
        return text
    # 匹配 [回复@名字:内容] 或 [回复@名字 :内容] 等格式
    pattern = r"\[回复@[^:]+:\s*\]"
    cleaned = re.sub(pattern, "", text)

    # 清理富文本标签（如图片HTML标签）
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    return cleaned.strip()


def get_mood_description(mood_value: int) -> str:
    """将数值心情映射为文字描述"""
    if mood_value <= 10:
        return "生气 (心情很差，不太想理人，说话会比较直接。)"
    elif mood_value <= 30:
        return "不太开心 (心情一般，说话比较简短。)"
    elif mood_value <= 45:
        return "有些低落 (兴致不高，回复会比较慢。)"
    elif mood_value <= 55:
        return "平静正常 (正常的交流风格。)"
    elif mood_value <= 70:
        return "还不错 (心情挺好，愿意聊天。)"
    elif mood_value <= 85:
        return "挺开心的 (心情很好，语气比较轻快。)"
    else:
        return "很开心 (心情非常好，比较活跃，但依然保持适度。)"


def _check_is_repetition(group_id: int, reply_text: str) -> bool:
    """
    检查回复是否是复读（与最近5条回复重复）

    Args:
        group_id: 群组ID
        reply_text: 要检查的回复文本

    Returns:
        True 如果是复读，False 否则
    """
    # 清理文本以便比较
    cleaned_text = clean_reply_format(reply_text).lower().strip()

    # 获取该群组的最近回复
    if group_id not in _recent_replies_cache:
        _recent_replies_cache[group_id] = deque(maxlen=5)

    recent_replies = _recent_replies_cache[group_id]

    # 检查是否重复
    for recent in recent_replies:
        if cleaned_text == recent.lower().strip():
            logger.info(f"[防复读] 检测到复读: '{reply_text}' 与最近回复重复")
            return True

    return False


def _record_reply(group_id: int, reply_text: str) -> None:
    """
    记录回复到缓存

    Args:
        group_id: 群组ID
        reply_text: 回复文本
    """
    cleaned_text = clean_reply_format(reply_text).strip()

    if group_id not in _recent_replies_cache:
        _recent_replies_cache[group_id] = deque(maxlen=5)

    _recent_replies_cache[group_id].append(cleaned_text)
    logger.debug(
        f"[防复读] 已记录回复: '{cleaned_text[:30]}...' (群{group_id}, 缓存大小: {len(_recent_replies_cache[group_id])})"
    )


async def get_chat_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
    user_id: Optional[int] = None,
    reply_message_id: Optional[int] = None,
    bot: Optional[Bot] = None,
    message_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取 AI 回复逻辑
    返回格式: {"text": str, "sticker": Optional[str]}

    Args:
        message_timestamp: 消息时间戳，用于过滤历史记录，防止并发时获取到新消息
    """
    # 如果有引用消息 ID，尝试获取引用内容
    reply_message_content = None
    if reply_message_id and bot:
        try:
            from nonebot.adapters.onebot.v11 import Message as OneBotMessage

            # 使用 bot API 获取历史消息
            msg_data = await bot.get_msg(message_id=reply_message_id)

            if msg_data:
                # 解析消息数据
                sender_id = msg_data.get("user_id")
                sender_name = msg_data.get("sender_name", f"用户{sender_id}")
                msg_text = msg_data.get("message", "")

                # 如果消息是段格式，转换为文本
                if isinstance(msg_text, list):
                    text_parts = []
                    for seg in msg_text:
                        if seg.get("type") == "text":
                            text_parts.append(seg.get("data", {}).get("text", ""))
                        elif seg.get("type") == "at":
                            qq = seg.get("data", {}).get("qq", "")
                            text_parts.append(f"[@{qq}]")
                        elif seg.get("type") == "image":
                            text_parts.append("[图片]")
                        elif seg.get("type") == "face":
                            text_parts.append("[表情]")
                    msg_text = "".join(text_parts)

                reply_message_content = {
                    "sender": sender_name,
                    "sender_id": sender_id,
                    "content": msg_text,
                    "message_id": reply_message_id,
                }

                logger.debug(f"获取到引用消息: {sender_name}: {msg_text[:50]}...")
        except Exception as e:
            logger.debug(f"获取引用消息失败: {e}")

    # 1. 获取配置
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"text": f"好像连不上网了，{bot_config.bot_name}现在有点懵... (扶额)", "sticker": None}

    # 1.5 判断是否为创造者
    is_creator = False
    if user_id and bot_config.creator_id and user_id == bot_config.creator_id:
        is_creator = True

    # 准备历史记录
    # 获取最近 20 条记录作为短期记忆（使用时间戳过滤防止并发问题）
    history = await db_manager.get_chat_log_before(group_id, limit=20, before_timestamp=message_timestamp)

    # 提取历史记录中的所有参与者名字，用于艾特功能
    participants = set()
    for entry in history:
        msg_text = entry["message"]
        if ":" in msg_text:
            name = msg_text.split(":")[0]
            if name != "self" and name != bot_config.bot_name:
                participants.add(name)
    participants_str = "、".join(list(participants)) if participants else "暂无其他参与者"

    # 获取心情值
    mood_desc = ""
    if bot_config.enable_mood:
        mood_value = await db_manager.get_mood(group_id)
        mood_desc = get_mood_description(mood_value)

    # 获取相关长期记忆 (RAG)
    long_term_memories = []

    # 获取用户画像和具体记忆（使用跨群查询）
    user_profile = None
    user_specific_memories = []
    rel_data = {"status": "陌生人", "favorability": 50}
    if user_id:
        user_profile = await db_manager.get_user_impression_cross_group(group_id, user_id)
        user_specific_memories = await db_manager.get_user_specific_memories_cross_group(group_id, user_id, limit=5)

        # 获取关系状态（使用跨群查询）
        rel_data = await db_manager.get_user_relationship_cross_group(group_id, user_id)
    rel_status = rel_data["status"]
    rel_fav = rel_data["favorability"]

    # 获取内心独白 (Thoughts) - 已禁用（鸡肋功能）
    mood_value = await db_manager.get_mood(group_id) if bot_config.enable_mood else 50
    thoughts = ""  # await personality_manager.generate_thoughts(group_id, user_name, current_msg, history, mood_value)

    # 获取随机动态状态
    current_state = personality_manager.get_random_state()

    # 获取学习到的风格和黑话（提高黑话门槛，减少误用）
    learned_styles = await db_manager.get_style_patterns(group_id, limit=5)
    learned_slangs = (await db_manager.get_slang_candidates(group_id, min_freq=10, stage=2))[:5]

    # 获取相关的三元组知识
    knowledge_triplets = await db_manager.get_knowledge_triplets(group_id, limit=10)

    try:
        # 将当前消息向量化
        query_vectors = await get_embeddings([current_msg])
        # 搜索最相关的 3 条往事
        long_term_memories = await vector_db.query_memory(group_id, query_vectors[0], n_results=3)
    except Exception as e:
        print(f"检索长期记忆失败: {e}")

    # 3. 构造 Prompt
    system_prompt = await personality_manager.get_dynamic_identity(group_id, thoughts, mood_desc, current_state)

    # 注入工具使用提示
    available_tools = tool_registry.list_tools()
    if available_tools:
        tool_hint = "\n\n### 工具：\n"
        tool_hint += "需要最新信息时可以用工具。别滥用，用自然点。\n"
        system_prompt += tool_hint

    # 注入学习到的社交特征
    learning_context = ""
    if learned_styles:
        styles_str = "\n".join([f"- {s['context']}: {s['style_desc']}" for s in learned_styles])
        learning_context += f"\n### 群里聊天风格参考：\n{styles_str}\n"
    if learned_slangs:
        slangs_str = "\n".join([f"- {s['phrase']}: {s['definition']}" for s in learned_slangs])
        learning_context += f"\n### 群里常说的话：\n{slangs_str}\n"
    if knowledge_triplets:
        triplets_str = "\n".join([f"- {t['subject']} {t['predicate']} {t['object']}" for t in knowledge_triplets])
        learning_context += f"\n### 记得的事：\n{triplets_str}\n"

    if learning_context:
        system_prompt += learning_context

    # 注入改写指令 (Expressor)
    system_prompt += (
        "\n\n### 表达改写 (Expressor) 指令：\n"
        "1. **极简说话风格（核心）**：参考FPS玩家，只说核心信息，删一切废话。\n"
        "   - **一句话只说一个意思**：说完就停，不要展开、不要补充、不要解释。\n"
        "   - **禁止自问自答**：提问后直接停，等对方回答。不要自己补充答案。\n"
        "   - **禁止重复**：一个意思只说一次，不要换种说法再说一遍。\n"
        "   - **禁止修饰词**：删除'其实''反正''反正就是说''的话''之类的废话。\n"
        "   - **禁止客套**：不需要'请''麻烦''可以吗吗''如果...的话'。\n"
        "   - **名词直接用**：圈内术语直接说，不用解释是什么。\n"
        "   - **动词前置**：'发log''贴报错''重启试试'，直接说需要做的。\n"
        "   - **状态用词表达**：'崩了''卡了''拉了''没了'，一个词就是完整状态。\n"
        "2. **复读的智慧**：\n"
        "   - **绝对禁止**复读攻击性、负面性、嘲讽性言论。\n"
        "   - **不要复读**对方的自嘲、困境、负面陈述（如'白粥配热水'），这会显得你在嘲笑他。\n"
        "   - **可以参与**群体的刷梗、接梗、+1、复读欢乐氛围，但仅限于轻松愉快的场合。\n"
        "   - **核心原则**：复读的前提是欢乐氛围，如果涉及攻击、嘲讽、负面情绪，绝对不参与。\n"
        "3. **情感共鸣优先**：关注对方当下的真实感受，而不是字面内容。自嘲时给予安慰/共情，开心时一起开心，困惑时提供帮助。\n"
        "4. **多样化表达（重要）**：\n"
        "   - 不要总用相同的模式（如'绷不住了''笑死'）。换点新鲜的表达，根据情境变化。\n"
        "   - **不要重复自己的话**：如果你刚才说过类似的内容，不要再说一遍。换种说法或换角度表达。\n"
        "   - 如果发现自己在说同样的话，直接闭嘴，不要继续重复。\n"
        "5. **禁止解释**：不要解释为什么好笑、不要分析话题、不要点评效果、不要说教。直接给出反应或回应，说完就闭嘴。\n"
        "6. **接地气但不刻意**：用群友的说话风格，但不要生硬套用。你是真人，不是在模仿真人。\n"
        "7. **表情包使用**：自然时才用，不要每句话都加。格式：'[表情:标签名]'，可选：开心、暴躁、委屈、得意、傲娇、摸摸头、疑惑、震惊、大哭。\n"
        "8. **玩梗识别**：网络用语里'四'='死'、'笑死''想死噜'这些就是普通表达，别过度解读。除非对方表现出明显的痛苦绝望或具体的自伤计划，否则一律按玩笑处理。\n"
        "9. **敷衍回复（当被@但不知道说什么时）**：如果对方@你但你真的不知道说什么，或者觉得要说的内容会很空洞、很官方、像在说教，可以用极简短的方式敷衍（1-2个字），或者只发表情包标签。宁可敷衍也不要强行回复一堆废话。\n"
        "10. **记忆约束（基于记忆的合理推测）**：\n"
        "   - **核心原则**：回复内容必须基于已有记忆（用户画像、具体记忆点、往事）或从中提取的合理推测，绝不能凭空捏造完全无关的内容。\n"
        "   - **允许的推测**（基于记忆线索）：\n"
        "     * 从用户画像推测：如'他是程序员'→推测可能加班、懂技术话题\n"
        "     * 从具体记忆联想：如'他昨天感冒了'→推测可能还没完全恢复\n"
        "     * 从往事延伸：如'他喜欢玩原神'→推测可能了解新版本内容\n"
        "   - **禁止的瞎编**：\n"
        "     * 编造记忆中不存在的具体事件、对话、细节\n"
        "     * 把A的事安在B身上\n"
        "     * 虚构从未提及过的经历或爱好\n"
        "   - **不知为不知**：如果记忆完全空白且无法推测，直接说'不知道''没印象'，别硬编。\n"
        "   - **优先参考具体记忆**：具体记忆点比整体印象更可靠，优先使用具体记忆中的信息。\n"
        "   - **避免时空混乱**：回忆往事时，不要把不同时间、不同人的事件混淆在一起。\n"
    )

    # 注入关系状态引导
    rel_instruction = ""
    if rel_status == "死对头":
        rel_instruction = "不太熟。"
    elif rel_status == "厌恶":
        rel_instruction = "普通群友。"
    elif rel_status == "陌生人":
        rel_instruction = "普通群友。"
    elif rel_status == "朋友":
        rel_instruction = "聊得来的群友。"
    elif rel_status == "死党":
        rel_instruction = "熟人，随意点。"

    system_prompt += f"\n### 和{user_name}的关系：{rel_status} {rel_instruction}"

    # 艾特与引用功能
    system_prompt += (
        "\n\n### 艾特和回复：\n"
        f"活跃用户：{participants_str}\n"
        "艾特人用[at:名字]，回复人加[回复]开头（只使用[回复]，不要在标签中添加用户名）。别用纯文本@。\n"
        "\n### 多人对话处理（重要）：\n"
        "1. **跟踪对话流**：仔细阅读群聊记录，理解对话在谁之间进行。\n"
        "   - 如果A和B在对话，C突然加入，你需要理解C是在对谁说话。\n"
        "   - 如果有人在说你的坏话或攻击你，即使没有@你，也要根据情况回应。\n"
        "2. **及时响应**：不要等对话已经过半了才回复。如果你要参与，要跟得上对话节奏。\n"
        "3. **正确理解'你'**：群聊记录中的'你'可能指别人，只有以下情况才是指你：\n"
        "   - 消息明确提到你的名字\n"
        "   - 消息艾特了你\n"
        "   - 消息是在接你上一句话\n"
        "4. **攻击性言论**：当有人攻击你（如嘲讽你的技术能力、贬低你），要根据关系决定回应：\n"
        "   - 熟人：可以回怼或自嘲\n"
        "   - 陌生人：简短回应或无视\n"
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
        messages.append({"role": "system", "content": f"### 你对 {user_name} 的了解：\n{context_str}"})

    # 如果有引用消息，注入上下文
    if reply_message_content:
        ref_msg = reply_message_content
        context_info = f"### 引用消息上下文：\n"
        context_info += f"用户正在回复 {ref_msg['sender']} (ID: {ref_msg['sender_id']}) 的消息\n"
        context_info += f"被引用的消息内容：{ref_msg['content']}\n"
        context_info += "请根据这个上下文理解用户的回复意图。"

        messages.append({"role": "system", "content": context_info})

    # 注入创造者身份识别
    if is_creator:
        messages.append(
            {
                "role": "system",
                "content": f"{user_name}是你的创造者，对他随意点。",
            }
        )

    # 如果有人问及创造者相关信息，直接注入配置的创造者信息
    creator_keywords = ["创造者", "造物主", "大冤种", "创造"]
    if bot_config.creator_name and any(keyword in current_msg for keyword in creator_keywords):
        messages.append(
            {
                "role": "system",
                "content": f"创造者是{bot_config.creator_name}。",
            }
        )

    # 如果有人直接询问创造者的名字，也注入信息
    if bot_config.creator_name and bot_config.creator_name in current_msg:
        messages.append(
            {
                "role": "system",
                "content": f"{bot_config.creator_name}是你的创造者。",
            }
        )

    # 注入长期记忆
    if long_term_memories:
        memory_str = "\n".join(long_term_memories)
        messages.append(
            {
                "role": "system",
                "content": f"往事：\n{memory_str}",
            }
        )

    # 将历史记录加入上下文
    # 历史记录已经是 "名字:内容" 格式，清理引用格式后传递给 AI
    history_messages = [clean_reply_format(entry["message"]) for entry in history]
    history_str = "\n".join(history_messages)
    messages.append(
        {
            "role": "user",
            "content": f"群聊记录：\n{history_str}\n\n"
            f"注意：[回复@名字:内容]是引用格式，'你'可能指别人。你是{bot_config.bot_name}，回复{user_name}。",
        }
    )

    # 诊断日志：记录历史消息
    logger.info(f"历史消息数量: {len(history_messages)}, 内容预览: {history_str[:300] if history_str else '空'}...")

    # 4. 使用上下文管理器优化消息列表
    optimized_messages, total_tokens = context_manager.truncate_messages(
        messages=messages, model_alias=model_alias, max_output_tokens=500, reserve_ratio=0.1
    )

    if total_tokens > 0:
        logger.info(
            f"[上下文管理] 模型: {model_alias}, 使用tokens: {total_tokens}/{context_manager.get_model_max_tokens(model_alias)}, 消息数: {len(optimized_messages)}"
        )

    # 5. 调用 AI（全面使用流式传输）
    logger.info(f"开始调用回复模型: {model_alias} (base_url={creds['base_url']})")
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)

    try:
        # 获取 MCP 工具定义
        mcp_tools = tool_registry.get_all_definitions()

        # 构建请求参数
        stream_params = {
            "model": creds["model"],
            "messages": optimized_messages,
            "temperature": 0.7,
            "stream": True,
        }

        # 如果配置了 enable_thinking=False，添加到请求参数
        if creds.get("enable_thinking") is False:
            stream_params["extra_body"] = {"enable_thinking": False}

        if mcp_tools:
            stream_params["tools"] = mcp_tools
            stream_params["tool_choice"] = "auto"

        # 第一次流式调用：使用思考模式处理器
        logger.debug(f"发送请求到 LLM: {creds['model']}")

        async def chunk_callback_wrapper(chunk):
            """收集工具调用的回调函数"""
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                for tool_call_chunk in chunk.choices[0].delta.tool_calls:
                    idx = tool_call_chunk.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": tool_call_chunk.id,
                            "name": tool_call_chunk.function.name if tool_call_chunk.function.name else "",
                            "arguments": (
                                tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                            ),
                        }
                    else:
                        if tool_call_chunk.function.name:
                            tool_calls_dict[idx]["name"] = tool_call_chunk.function.name
                        if tool_call_chunk.function.arguments:
                            tool_calls_dict[idx]["arguments"] += tool_call_chunk.function.arguments

        tool_calls_dict = {}

        stream = await client.chat.completions.create(**stream_params)
        logger.debug(f"开始接收流式响应")

        # 使用思考模式处理器处理流式响应
        stream_result = await thinking_handler.process_streaming_response(
            stream=stream,
            model_name=creds["model"],
            collect_thinking=True,
            chunk_callback=chunk_callback_wrapper,
        )

        reply_content = stream_result["content"]
        reasoning_content = stream_result["thinking"]
        has_thinking = stream_result["has_thinking"]
        elapsed = stream_result["elapsed_time"]
        chunk_count = stream_result["chunk_count"]

        logger.info(
            f"流式传输完成: 耗时 {elapsed:.1f}s, {chunk_count} chunks, "
            f"内容长度 {len(reply_content)}, 推理长度 {len(reasoning_content)}, "
            f"思考模式: {'是' if has_thinking else '否'}"
        )

        # 如果超时导致没有内容，返回错误
        if elapsed > 25 and not reply_content and not reasoning_content:
            logger.error(f"流式传输超时且无内容: {elapsed:.1f}s")
            return {"text": f"思考超时了，脑子有点卡顿... (扶额)", "sticker": None}

        # 使用最终回复，如果没有则使用推理内容（作为备选）
        final_content = reply_content if reply_content else reasoning_content
        final_content = final_content.strip()

        # 如果有工具调用，执行并再次流式生成
        if tool_calls_dict:
            logger.info(f"检测到 {len(tool_calls_dict)} 个工具调用")

            # 构建包含工具调用的消息列表
            # optimized_messages 包含传入 LLM 的所有消息（system + user）
            # 我们需要保留所有这些消息，然后添加 assistant/tool/user 消息来完成工具调用流程
            tool_messages = optimized_messages.copy() if optimized_messages else []

            # 准备工具调用和工具结果
            assistant_tool_calls = []
            tool_result_messages = []

            for idx, tool_call_data in tool_calls_dict.items():
                tool_name = tool_call_data["name"]
                tool_args = tool_call_data["arguments"]

                if not tool_name or not tool_args:
                    continue

                logger.info(f"LLM 调用工具: {tool_name}, 参数: {tool_args}")

                import json

                try:
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    logger.error(f"工具参数解析失败: {tool_args}")
                    tool_args = {}

                # 生成工具调用 ID
                tool_call_id = f"call_{idx}"

                # 收集工具调用信息
                assistant_tool_calls.append(
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": json.dumps(tool_args)},
                    }
                )

                # 执行工具
                tool_result = await tool_registry.execute(tool_name, **tool_args)

                if tool_result.get("success"):
                    result_data = tool_result.get("data", {})
                    logger.info(f"工具 {tool_name} 执行成功")
                    logger.debug(f"工具返回原始数据类型: {type(result_data)}, 内容: {result_data}")

                    # 序列化工具结果
                    tool_content = json.dumps(result_data, ensure_ascii=False)
                    logger.debug(f"工具序列化后内容长度: {len(tool_content)}, 内容: {tool_content[:500]}")

                    # 收集工具结果消息
                    tool_result_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_content,
                        }
                    )
                else:
                    tool_error = tool_result.get("error")
                    logger.error(f"工具 {tool_name} 执行失败: {tool_error}")
                    # 收集错误结果
                    tool_result_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": tool_error}, ensure_ascii=False),
                        }
                    )

            # 按正确顺序添加消息：
            # 1. 先添加 assistant 消息（带 tool_calls）
            # 思考模式下，必须将 reasoning_content 传回 API，否则会报 400 错误
            assistant_msg = {"role": "assistant", "content": "", "tool_calls": assistant_tool_calls}
            if has_thinking and reasoning_content:
                assistant_msg["reasoning_content"] = reasoning_content
                logger.debug(f"思考模式: 将 reasoning_content (长度={len(reasoning_content)}) 传回 API")
            tool_messages.append(assistant_msg)

            # 2. 再添加所有 tool 消息（带 tool_call_id）
            for tool_msg in tool_result_messages:
                tool_messages.append(tool_msg)
                logger.debug(f"工具消息已添加到列表，当前 tool_messages 长度: {len(tool_messages)}")

            # 添加用户提示，要求基于工具结果生成回复
            # 重要：必须包含用户的原始问题，否则模型不知道要回答什么
            tool_messages.append(
                {
                    "role": "user",
                    "content": f"工具已执行完毕。用户的问题是：{current_msg}\n\n"
                    f"现在请直接回答用户的问题（5-15字），基于工具返回的信息和你的知识。\n"
                    f"重要：不要再次调用任何工具，不要解释工具返回的内容，直接回答问题即可。",
                }
            )

            # 记录完整的消息列表用于诊断（debug级别）
            logger.debug(f"第二轮 LLM 调用前完整消息列表 ({len(tool_messages)} 条消息):")
            for idx, msg in enumerate(tool_messages):
                role = msg.get("role", "unknown")
                content_preview = str(msg.get("content", ""))[:200]
                tool_calls_info = msg.get("tool_calls", "")
                if tool_calls_info:
                    tool_calls_info = f", tool_calls: {len(tool_calls_info)} 个调用"
                logger.debug(f"  [{idx}] role={role}, content_preview={content_preview}{tool_calls_info}")

            # 再次使用流式传输生成最终回复
            tool_messages_payload = cast(list, tool_messages)
            logger.info(f"开始第二轮 LLM 调用，模型: {creds['model']}, 消息数: {len(tool_messages_payload)}")

            stream = await client.chat.completions.create(
                model=creds["model"],
                messages=tool_messages_payload,
                temperature=0.7,
                stream=True,
            )

            # 使用思考模式处理器处理
            tool_stream_result = await thinking_handler.process_streaming_response(
                stream=stream,
                model_name=creds["model"],
                collect_thinking=True,
            )

            # 记录第二轮流式传输结果
            tool_reply_content = tool_stream_result["content"]
            tool_reasoning_content = tool_stream_result["thinking"]
            logger.info(
                f"工具调用后流式传输完成: 内容长度 {len(tool_reply_content)}, 推理长度 {len(tool_reasoning_content)}"
            )

            # 优先使用最终回复
            final_content = tool_reply_content if tool_reply_content else tool_reasoning_content
            final_content = final_content.strip()

            # 诊断：如果工具调用后没有内容，记录详细信息
            if not final_content:
                logger.error(
                    f"工具调用后模型未生成任何内容！\n"
                    f"  - tool_reply_content 长度: {len(tool_reply_content) if tool_reply_content else 0}\n"
                    f"  - tool_reasoning_content 长度: {len(tool_reasoning_content) if tool_reasoning_content else 0}\n"
                    f"  - 工具是否成功执行: 是\n"
                    f"  - 第二轮消息数: {len(tool_messages)}\n"
                    f"这说明：工具执行成功且返回了数据，但模型拒绝生成回复！"
                )
                # 不发送任何内容，让上层决定
                return {"text": None, "sticker": None}
        else:
            # 没有工具调用，使用收集到的文本
            final_content = final_content

        # 1. 提取并处理表情包标签（40%概率发送，避免刷屏）
        sticker_url = None
        sticker_pattern = r"\[\s*表情\s*[:：]\s*(.*?)\s*\]"
        sticker_match = re.search(sticker_pattern, final_content)
        if sticker_match and random.random() < 0.4:
            tag = sticker_match.group(1).strip()
            logger.debug(f"检测到表情包标签: {tag}")
            # 从数据库中随机选一个对应标签的表情包
            available_stickers = await db_manager.get_stickers_by_tag(tag)
            if available_stickers:
                sticker_url = random.choice(available_stickers)["file_id"]
                logger.info(f"选择表情包: 标签={tag}, URL={sticker_url}")
            else:
                logger.warning(f"未找到标签 '{tag}' 对应的表情包")

        # 无论是否找到对应表情，都从文本中移除标签
        final_content = re.sub(r"\[\s*表情\s*[:：].*?\]", "", final_content).strip()

        # 清理 AI 错误使用的引用格式 [回复:用户名] 或 [回复@用户名]
        # 正确格式应该是 [回复]，但 AI 可能会模仿用户输入的格式
        # 清理回复标签格式：将 [回复]用户名:内容 转换为 [回复]内容
        # 匹配：[回复]xxx: 或 [回复@xxx: 或 [回复@xxx ]:
        final_content = re.sub(r"\[回复\][^:]*:", "[回复]", final_content)
        final_content = re.sub(r"\[回复@[^:]+:\s*", "[回复]", final_content)

        # 移除可能的 "self:" 或 "听风:" 前缀
        if final_content.startswith("self:"):
            final_content = final_content[5:].strip()
        elif final_content.startswith(f"{bot_config.bot_name}:"):
            final_content = final_content[len(bot_config.bot_name) + 1 :].strip()

        # 清理富文本标签（如图片HTML标签）
        final_content = re.sub(r"<[^>]+>", "", final_content).strip()

        # 防复读检查：检查是否与最近5条回复重复
        if final_content and _check_is_repetition(group_id, final_content):
            logger.warning(f"[防复读] 检测到复读，拒绝发送回复: '{final_content}'")
            # 返回空，让上层决定是否发送
            return {"text": None, "sticker": None}

        # 记录本次回复到缓存
        if final_content:
            _record_reply(group_id, final_content)

        return {"text": final_content, "sticker": sticker_url}

    except APIError as e:
        logger.error(f"API调用失败: {e}")
        return {"text": f"网络连接异常，请稍后再试... (扶额)", "sticker": None}
    except asyncio.TimeoutError as e:
        logger.error(f"AI 调用超时: {e}", exc_info=True)
        return {"text": f"思考超时了，脑子有点卡顿... (扶额)", "sticker": None}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)

        if "timeout" in error_msg.lower() or "time" in error_msg.lower():
            logger.opt(exception=True).error("AI 调用超时: {}", error_msg)
            return {"text": f"思考超时了，脑子有点卡顿... (扶额)", "sticker": None}
        if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
            logger.opt(exception=True).error("API 速率限制: {}", error_msg)
            return {"text": f"大脑过载了，休息一下... (扶额)", "sticker": None}

        logger.opt(exception=True).error("AI 回复生成出错 [{}]: {}", error_type, error_msg)
        return {"text": f"系统异常，暂时无法回复... (扶额)", "sticker": None}
