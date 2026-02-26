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
import random
import re
import asyncio
import json

logger = get_logger(__name__)


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
        if ":" in entry:
            name = entry.split(":")[0]
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
        "   - **不要复读**对方的自嘲、困境、负面陈述（如'白粥配热水'），这会显得你在嘲笑他。\n"
        "   - **可以参与**群体的刷梗、接梗、+1、复读欢乐氛围，这时候不参与反而很奇怪。\n"
        "3. **情感共鸣优先**：关注对方当下的真实感受，而不是字面内容。自嘲时给予安慰/共情，开心时一起开心，困惑时提供帮助。\n"
        "4. **多样化表达**：不要总用相同的模式（如'绷不住了''笑死'）。换点新鲜的表达，根据情境变化。\n"
        "5. **禁止解释**：不要解释为什么好笑、不要分析话题、不要点评效果、不要说教。直接给出反应或回应，说完就闭嘴。\n"
        "6. **接地气但不刻意**：用群友的说话风格，但不要生硬套用。你是真人，不是在模仿真人。\n"
        "7. **表情包使用**：自然时才用，不要每句话都加。格式：'[表情:标签名]'，可选：开心、暴躁、委屈、得意、傲娇、摸摸头、疑惑、震惊、大哭。\n"
        "8. **玩梗识别**：网络用语里'四'='死'、'笑死''想死噜'这些就是普通表达，别过度解读。除非对方表现出明显的痛苦绝望或具体的自伤计划，否则一律按玩笑处理。\n"
        "9. **敷衍回复（当被@但不知道说什么时）**：如果对方@你但你真的不知道说什么，或者觉得要说的内容会很空洞、很官方、像在说教，可以用极简短的方式敷衍（1-2个字），或者只发表情包标签。宁可敷衍也不要强行回复一堆废话。\n"
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
        "艾特人用[at:名字]，回复人加[回复]开头。别用纯文本@。\n"
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
    # 历史记录已经是 "名字:内容" 格式
    history_str = "\n".join(history)
    messages.append(
        {
            "role": "user",
            "content": f"群聊记录：\n{history_str}\n\n"
            f"注意：[回复@名字:内容]是引用格式，'你'可能指别人。你是{bot_config.bot_name}，回复{user_name}。",
        }
    )

    # 4. 使用上下文管理器优化消息列表
    optimized_messages, total_tokens = context_manager.truncate_messages(
        messages=messages, model_alias=model_alias, max_output_tokens=500, reserve_ratio=0.1
    )

    if total_tokens > 0:
        print(
            f"[上下文管理] 模型: {model_alias}, 使用tokens: {total_tokens}/{context_manager.get_model_max_tokens(model_alias)}"
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
            "max_tokens": 150,
            "temperature": 0.7,
            "stream": True,
        }

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
            tool_messages = optimized_messages.copy()

            # 添加 assistant 的工具调用记录
            assistant_tool_calls = []
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

                    # 添加工具结果消息（使用 tool role）
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(result_data, ensure_ascii=False),
                        }
                    )
                else:
                    tool_error = tool_result.get("error")
                    logger.error(f"工具 {tool_name} 执行失败: {tool_error}")
                    # 添加错误结果
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": tool_error}, ensure_ascii=False),
                        }
                    )

            # 添加 assistant 的工具调用消息
            tool_messages.append({"role": "assistant", "content": "", "tool_calls": assistant_tool_calls})

            # 再次使用流式传输生成最终回复
            tool_messages_payload = cast(list, tool_messages)
            stream = await client.chat.completions.create(
                model=creds["model"],
                messages=tool_messages_payload,
                max_tokens=120,
                temperature=0.7,
                stream=True,
            )

            # 使用思考模式处理器处理
            tool_stream_result = await thinking_handler.process_streaming_response(
                stream=stream,
                model_name=creds["model"],
                collect_thinking=True,
            )

            # 优先使用最终回复
            final_content = (
                tool_stream_result["content"] if tool_stream_result["content"] else tool_stream_result["thinking"]
            )
            final_content = final_content.strip()
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

        # 移除可能的 "self:" 或 "听风:" 前缀
        if final_content.startswith("self:"):
            final_content = final_content[5:].strip()
        elif final_content.startswith(f"{bot_config.bot_name}:"):
            final_content = final_content[len(bot_config.bot_name) + 1 :].strip()

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
