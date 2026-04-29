from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from src.utils.openai_compat import openai_compat
from src.utils.thinking_mode import thinking_handler
from src.mcp.registry import tool_registry
from src.aimodel.decision.prefilter import reply_prefilter
from typing import Optional
import json
import asyncio
import re

logger = get_logger(__name__)


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


async def should_i_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
    is_at_me: bool = False,
    user_id: Optional[int] = None,
    is_sticker: bool = False,
) -> dict:
    """
    判断机器人是否应该参与当前对话，并评价该对话对机器人心情的影响

    Args:
        group_id: 群组 ID
        user_name: 用户名称
        current_msg: 当前消息内容
        is_at_me: 是否艾特了机器人
        user_id: 用户 ID（可选）
        is_sticker: 是否是表情包消息

    Returns:
        决策结果字典
    """
    # -1. 惹人生厌检测（低优先级，只在未艾特时生效）
    if not is_at_me:
        # 检测 1: 当前心情值过低
        current_mood_val = await db_manager.get_mood(group_id)
        ANNOYANCE_MOOD_THRESHOLD = 30  # 心情值低于30分表示可能已惹人生厌

        if current_mood_val < ANNOYANCE_MOOD_THRESHOLD:
            logger.info(
                f"惹人生厌检测: 当前心情值过低 ({current_mood_val} < {ANNOYANCE_MOOD_THRESHOLD})，"
                f"机器人可能已惹人生厌，保持沉默以让气氛缓和"
            )
            return {"should_reply": False, "mood_impact": 0}

        # 检测 2: 最近是否有明显的负面反馈
        has_negative_feedback = await db_manager.has_recent_negative_feedback(group_id)

        if has_negative_feedback:
            logger.info(
                f"惹人生厌检测: 检测到最近的负面反馈（最近几次心情变化多为负面），"
                f"机器人可能已惹人生厌，暂停主动发言以缓和气氛"
            )
            return {"should_reply": False, "mood_impact": 0}

    # 0. 发言频率控制 - 只限制主动发言，被艾特时不限制
    if not is_at_me:
        last_reply_time = await db_manager.get_last_reply_time(group_id)

        # 频率限制配置（仅针对主动发言）
        MIN_INTERVAL_SECONDS = 60  # 两次主动回复间最小间隔

        # 计算距离上次回复的时间
        from datetime import datetime

        time_since_last_reply = None
        if last_reply_time:
            time_since_last_reply = (datetime.now() - last_reply_time).total_seconds()

        # 频率检查：只对主动发言进行间隔限制
        if time_since_last_reply and time_since_last_reply < MIN_INTERVAL_SECONDS:
            logger.info(f"频率限制: 距离上次回复仅{time_since_last_reply:.0f}秒，跳过非艾特消息")
            return {"should_reply": False, "mood_impact": 0}

    # 1. 获取配置
    model_alias = ai_config.decision_model
    if not model_alias:
        return {"should_reply": False, "mood_impact": 0}

    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"should_reply": False, "mood_impact": 0}

    # 获取当前心情
    current_mood_val = await db_manager.get_mood(group_id)

    # 2. 准备上下文 (获取最近 10 条消息)
    history = await db_manager.get_chat_log(group_id, limit=10)

    # 提取消息文本和对应的 message_id，并清理引用格式
    history_messages = []
    history_message_ids = []
    for item in history:
        # 清理引用格式，避免AI模仿
        clean_msg = clean_reply_format(item["message"])
        history_messages.append(clean_msg)
        history_message_ids.append(item["message_id"])

    # 2.5. 规则预过滤器：在调用 AI 前用快速规则判断是否值得决策
    if not is_at_me:
        prefilter_result = reply_prefilter.should_skip_ai_decision(
            user_name=user_name,
            current_msg=current_msg,
            is_at_me=False,
            is_sticker=is_sticker,
            history_messages=history_messages,
        )
        if prefilter_result.should_skip_ai:
            logger.info(
                f"预过滤器跳过 AI 决策: {prefilter_result.reason} " f"[用户:{user_name}] [消息:{current_msg[:30]}...]"
            )
            return {"should_reply": prefilter_result.should_reply, "mood_impact": 0}

    # 3. 检索相关记忆与知识
    user_profile = await db_manager.get_user_impression(group_id, user_id) if user_id else None
    user_specific_memories = await db_manager.get_user_specific_memories(group_id, user_id, limit=3) if user_id else []

    # 注入高频黑话（只使用频率>=30的已验证黑话）
    learned_slangs = await db_manager.get_slang_candidates(group_id, min_freq=30, stage=2)
    slang_context = ""
    if learned_slangs:
        slang_list = [f"- {s['phrase']}: {s['definition']}" for s in learned_slangs]
        slang_context = "\n### 本群特有黑话/暗语库：\n" + "\n".join(slang_list)

    long_term_memories = []
    content = ""
    try:
        query_vectors = await get_embeddings([current_msg])
        if query_vectors and len(query_vectors) > 0:
            long_term_memories = await vector_db.query_memory(group_id, query_vectors[0], n_results=2)
    except Exception as e:
        logger.warning(f"获取长期记忆失败: {e}")

    # 获取禁言反思记录
    mute_reflections = []
    try:
        mute_reflection_records = await db_manager.get_mute_reflections(group_id, limit=3)
        if mute_reflection_records:
            for i, reflection in enumerate(mute_reflection_records, 1):
                mute_reflections.append(
                    f"{i}. 原因: {reflection['ban_reason']} | 教训: {reflection['lesson_learned'][:50]}..."
                )
    except Exception as e:
        logger.warning(f"获取禁言反思失败: {e}")

    # 构造记忆上下文
    memory_context = []
    if user_profile:
        memory_context.append(f"- 你对 {user_name} 的整体印象：{user_profile}")
    if user_specific_memories:
        mem_str = "\n  ".join([f"* {m}" for m in user_specific_memories])
        memory_context.append(f"- 关于 {user_name} 的具体往事：\n  {mem_str}")
    if long_term_memories:
        lt_mem_str = "\n  ".join([f"* {m}" for m in long_term_memories])
        memory_context.append(f"- 相关的长期记忆：\n  {lt_mem_str}")
    if mute_reflections:
        mute_ref_str = "\n  ".join([f"* {m}" for m in mute_reflections])
        memory_context.append(f"- 之前的禁言反思（避免重蹈覆辙）：\n  {mute_ref_str}")

    memory_str = "\n".join(memory_context) if memory_context else "暂无相关背景记忆。"

    # 构建带索引的历史消息
    history_with_index = []
    for idx, msg in enumerate(history_messages):
        history_with_index.append(f"[{idx}] {msg}")
    history_str = "\n".join(history_with_index)

    # 4. 场景智能分析（基于规则的轻量级提示）
    def analyze_conversation_context() -> dict:
        """
        分析对话上下文，提供场景判断的辅助信息

        Returns:
            包含上下文分析的字典
        """
        if not history_messages:
            return {"has_bot_msg_recently": False, "bot_msg_position": None, "suggested_scene": "C"}

        # 检查最近5条消息中bot发言的位置
        bot_msg_indices = []
        for i in range(min(5, len(history_messages))):
            msg = history_messages[-(i + 1)]
            if msg.startswith(f"{bot_config.bot_name}:") or msg.startswith(f"{bot_config.bot_name} "):
                bot_msg_indices.append(len(history_messages) - 1 - i)

        if not bot_msg_indices:
            # 最近没有bot发言
            suggested_scene = "B" if is_at_me or bot_config.bot_name in current_msg else "C"
            return {"has_bot_msg_recently": False, "bot_msg_position": None, "suggested_scene": suggested_scene}

        # 有bot发言，分析对话流向
        last_bot_idx = bot_msg_indices[0]  # 最近一次bot发言的位置
        messages_after_bot = len(history_messages) - last_bot_idx - 1  # bot发言后的消息数

        context_hint = ""
        if messages_after_bot <= 2:
            # bot发言后只有1-2条消息，很可能是在回应bot
            context_hint = "bot发言后紧接着1-2条消息，很可能是对bot的回应"
            suggested_scene = "A"
        elif messages_after_bot <= 4:
            # bot发言后有3-4条消息，需要看话题是否延续
            context_hint = "bot发言后有3-4条消息，需要判断话题是否延续"
            suggested_scene = "unknown"  # 让AI自己判断
        else:
            # bot发言后超过4条消息，对话可能已经转向
            context_hint = "bot发言后已有较多消息，对话可能已经转向其他话题"
            suggested_scene = "C"

        return {
            "has_bot_msg_recently": True,
            "bot_msg_position": last_bot_idx,
            "messages_after_bot": messages_after_bot,
            "context_hint": context_hint,
            "suggested_scene": suggested_scene,
        }

    # 分析对话上下文
    context_analysis = analyze_conversation_context()

    # 构建带索引的历史消息（bot的消息添加★标记）
    history_with_index = []
    for idx, msg in enumerate(history_messages):
        marked_msg = msg
        # 给bot的消息添加显式标记
        if msg.startswith(f"{bot_config.bot_name}:") or msg.startswith(f"{bot_config.bot_name} "):
            marked_msg = f"★ {msg}"
        history_with_index.append(f"[{idx}] {marked_msg}")
    history_str = "\n".join(history_with_index)

    # 计算最大索引
    max_idx = len(history_messages) - 1 if history_messages else 0

    # 判断对话参与类型（用于更精确的决策）
    conversation_type = "unknown"
    if len(history) >= 3:
        # 分析最近几条消息的参与者
        recent_senders = [msg.split(":")[0] if ":" in msg else "unknown" for msg in history[-5:]]
        unique_senders = len(set([s for s in recent_senders if s != bot_config.bot_name and s != "unknown"]))

        if unique_senders <= 1:
            conversation_type = "single_user"
        elif unique_senders == 2:
            conversation_type = "dual_chat"
        else:
            conversation_type = "group_chat"

    # 检查最近的发言是否来自机器人自己
    bot_recently_spoke = context_analysis["has_bot_msg_recently"]

    prompt = (
        f"你是'{bot_config.bot_name}'，心情{current_mood_val}/100。决定是否回复。\n"
        f"对话类型：{conversation_type}，"
        f"{'刚发言过，下一条很可能是在接你的话' if bot_recently_spoke else '沉默中'}。\n"
        f"### 背景：\n{memory_str}\n{slang_context}\n"
        f"### 决策规则：\n"
        f"场景A（对话延续）：最近1-2条在回应你的发言/延续你开启的话题 → interest 0.5-1.0，强烈建议回。\n"
        f"场景B（被提到）：被@或讨论到你但未直接对话 → interest 0.1-0.5，谨慎参与。\n"
        f"场景C（无关）：与你完全无关 → 默认0分。仅当强关联记忆+有价值内容才给0.3-0.7分。无记忆→0分。\n"
        f"默认沉默，你是真人不是客服。只说有料的话。\n"
        f"历史中★是你的发言：对方在追问/重新发起/有新进展→可以回；纯粹刷屏/重复→不回。\n"
        f"他人A↔B对话中的'你'不指你。无法确定→默认不指你。\n"
        f"心情：夸奖+1~+3，辱骂-5~-12，无关/玩笑=0。\n"
        f"### 历史（★=你的发言）：\n{history_str}\n"
        f"引用格式 [回复@:内容] 表示发送者在回复被引用者。\n"
        f"当前：{user_name}: {current_msg} [{'@你' if is_at_me else '普通消息'}] [{'表情包' if is_sticker else ''}]\n"
        f'输出JSON：{{"should_reply":bool,"target_message_index":0-{max_idx},'
        f'"reply_to_user":"用户名","mood_impact":-10~10,"reason":"理由",'
        f'"is_replying_to_bot":bool,"interest_score":0-1,"conversation_scene":"A/B/C"}}'
    )

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)

    try:
        # 获取 MCP 工具定义
        mcp_tools = tool_registry.get_all_definitions()

        optimized_prompt, prompt_tokens = context_manager.truncate_text(
            text=prompt, model_alias=model_alias, max_output_tokens=200, reserve_ratio=0.1
        )

        if prompt_tokens > 0:
            print(
                f"[上下文管理] 决策模型: {model_alias}, 使用tokens: {prompt_tokens}/{context_manager.get_model_max_tokens(model_alias)}"
            )

        # 获取 MCP 工具定义
        mcp_tools = tool_registry.get_all_definitions()

        # 构建基础请求参数
        base_params = {
            "model": creds["model"],
            "messages": [{"role": "user", "content": optimized_prompt}],
            "stream": True,
        }

        # 如果有 MCP 工具可用，添加工具支持（工具调用时不使用 response_format）
        if mcp_tools:
            base_params["tools"] = mcp_tools
            base_params["tool_choice"] = "auto"

        # 使用兼容性工具调用（自动处理 response_format）
        stream = await openai_compat.create_with_auto_fallback(
            client=client,
            use_response_format=not bool(mcp_tools),  # 有工具时不使用 response_format
            base_url=creds["base_url"],
            **base_params,
        )

        # 收集工具调用的字典
        tool_calls_buffer = {}

        async def tool_chunk_callback(chunk):
            """收集工具调用的回调函数"""
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    idx = tool_call.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": tool_call.id, "name": "", "arguments": ""}
                    if tool_call.function and tool_call.function.name:
                        tool_calls_buffer[idx]["name"] = tool_call.function.name
                    if tool_call.function and tool_call.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tool_call.function.arguments

        # 使用思考模式处理器处理流式响应
        stream_result = await thinking_handler.process_streaming_response(
            stream=stream,
            model_name=creds["model"],
            collect_thinking=True,
            chunk_callback=tool_chunk_callback,
        )

        content = stream_result["content"]

        # 记录思考模式状态
        if stream_result["has_thinking"]:
            logger.info(f"决策模型使用思考模式: 推理长度={len(stream_result['thinking'])}")

        # 如果有工具调用，执行并重新请求
        if tool_calls_buffer:
            logger.info(f"决策模型调用 {len(tool_calls_buffer)} 个工具")

            for idx, tool_call in tool_calls_buffer.items():
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]

                if not tool_name:
                    continue

                logger.info(f"决策模型调用工具: {tool_name}")

                try:
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                except json.JSONDecodeError as e:
                    logger.error(f"工具参数解析失败: {e}")
                    tool_args = {}

                # 执行工具
                tool_result = await tool_registry.execute(tool_name, **tool_args)

                if tool_result.get("success"):
                    logger.info(f"工具 {tool_name} 执行成功")
                    # 将工具结果添加到 prompt
                    optimized_prompt += f"\n\n### 工具执行结果（{tool_name}）：\n{json.dumps(tool_result.get('data', {}), ensure_ascii=False)}\n"
                else:
                    logger.error(f"工具 {tool_name} 执行失败: {tool_result.get('error')}")

            # 重新请求最终决策（不带工具，使用兼容性工具）
            stream = await openai_compat.create_with_auto_fallback(
                client=client,
                model=creds["model"],
                messages=[{"role": "user", "content": optimized_prompt}],
                base_url=creds["base_url"],
                use_response_format=True,
                stream=True,
            )

            # 使用思考模式处理器处理
            final_stream_result = await thinking_handler.process_streaming_response(
                stream=stream,
                model_name=creds["model"],
                collect_thinking=True,
            )

            content = final_stream_result["content"]

        content = content.strip()
        if not content:
            logger.warning("决策模型返回空内容，使用默认决策")
            raise json.JSONDecodeError("Empty content", "", 0)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # 再次检查清理后的内容是否为空
        if not content:
            logger.warning("清理后内容为空，使用默认决策")
            raise json.JSONDecodeError("Empty content after cleaning", "", 0)

        decision = json.loads(content)

        # 记录AI判断的场景（仅用于日志分析）
        ai_detected_scene = decision.get("conversation_scene", "C")
        suggested_scene = context_analysis.get("suggested_scene", "C")
        if ai_detected_scene != suggested_scene and suggested_scene != "unknown":
            logger.info(f"场景判断差异：系统建议={suggested_scene}，AI判断={ai_detected_scene}（已采用AI判断）")

        # 结果解析
        should_reply = decision.get("should_reply", False)

        # 确保 max_idx 是有效的（处理空历史消息的情况）
        safe_max_idx = max_idx if max_idx >= 0 else 0

        target_message_index = decision.get("target_message_index", safe_max_idx)  # 默认选择最新消息

        # 验证索引有效性（先处理 None 值）
        if target_message_index is None:
            target_message_index = safe_max_idx
        elif not isinstance(target_message_index, int):
            target_message_index = safe_max_idx
        elif target_message_index < 0 or target_message_index > safe_max_idx:
            target_message_index = safe_max_idx

        # 再次确保索引有效（防止空列表访问）
        if len(history_messages) == 0:
            logger.warning("历史消息为空，使用当前消息")
            target_message_index = 0
            # 临时创建虚拟消息记录以避免索引错误
            history_messages = [f"{user_name}: {current_msg}"]
            history_message_ids = [None]

        # 从选定的消息中提取用户名、纯消息内容和message_id
        selected_message = history_messages[target_message_index]
        selected_message_id = history_message_ids[target_message_index]
        selected_user = user_name  # 默认为当前用户
        target_message_content = selected_message  # 默认使用完整消息

        if ":" in selected_message:
            parts = selected_message.split(":", 1)
            selected_user = parts[0].strip()
            target_message_content = parts[1].strip()  # 只提取冒号后的内容

        # 使用AI指定的回复对象，如果没有则使用选定消息的发送者
        reply_to_user = decision.get("reply_to_user", selected_user)

        mood_impact = decision.get("mood_impact", 0)
        interest_score = decision.get("interest_score", 0)
        is_replying_to_bot = decision.get("is_replying_to_bot", False)
        conversation_scene = decision.get("conversation_scene", "C")  # 默认为场景C（未对话）

        # 场景描述映射
        scene_descriptions = {
            "A": "正在和bot对话",
            "B": "提到bot但未对话",
            "C": "完全没和bot聊天",
            "unknown": "未知场景",
        }
        scene_desc = scene_descriptions.get(conversation_scene, "未知场景")

        # 构建上下文提示（用于日志）
        context_info = ""
        if context_analysis["has_bot_msg_recently"]:
            context_info = f" [Bot后{context_analysis['messages_after_bot']}条]"

        print(
            f"决策引擎: [场景:{conversation_scene}({scene_desc}){context_info}] [回复:{should_reply}] [目标消息:{target_message_index}] [消息ID:{selected_message_id}] [对象:{reply_to_user}] [内容:{target_message_content[:30]}...] [兴趣:{interest_score}] [心情:{mood_impact:+}] [理由:{decision.get('reason')}]"
        )

        return {
            "should_reply": should_reply,
            "target_message_index": target_message_index,
            "target_message_id": selected_message_id,  # 选定消息的QQ消息ID
            "target_message_content": target_message_content,  # 纯消息内容(不含用户名)
            "selected_user": selected_user,  # 选定消息的发送者
            "reply_to_user": reply_to_user,  # AI选择的回复对象
            "mood_impact": mood_impact,
            "interest_score": interest_score,
            "is_replying_to_bot": is_replying_to_bot,
        }

    except json.JSONDecodeError as e:
        logger.error(f"决策结果JSON解析失败: {e}，原始内容: {content[:200] if content else '(空)'}")
        return {
            "should_reply": is_at_me,
            "mood_impact": 0,
            "target_message_index": 0,
            "target_message_id": None,
            "target_message_content": current_msg,
            "selected_user": user_name,
            "reply_to_user": user_name,
            "interest_score": 0.0,
            "is_replying_to_bot": False,
        }


async def should_i_scan_join(
    group_id: int,
    queued_contexts: list,
    history_messages: list = None,
) -> dict:
    """
    扫描模式：bot 主动回看群聊，判断是否有值得参与的话题

    与 should_i_reply 的区别：
    - 批量处理多条消息（而非逐条判断）
    - 放宽预过滤限制（扫描模式下不检查"bot是否相关"）
    - 更紧凑的 prompt（减少 token 消耗）
    - 只回复有强记忆关联 + 有料可说的话题
    - 极度负面心情时（<20）拒绝参与

    Args:
        group_id: 群组 ID
        queued_contexts: 队列中的消息上下文列表
        history_messages: 已清理的历史消息列表（外部传入，避免重复DB查询）

    Returns:
        决策结果字典，包含 should_reply, target_context 等
    """
    model_alias = ai_config.decision_model
    if not model_alias:
        return {"should_reply": False, "reason": "模型未配置"}

    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"should_reply": False, "reason": "凭证无效"}

    # 获取完整历史（如果外部未传入则自行查询）
    if history_messages is None:
        history = await db_manager.get_chat_log(group_id, limit=20)
        history_messages = []
        for item in history:
            clean_msg = clean_reply_format(item["message"])
            history_messages.append(clean_msg)

    current_mood_val = await db_manager.get_mood(group_id)

    # 极度负面心情 → 不参与任何对话
    SCAN_MOOD_MINIMUM = 20
    if current_mood_val < SCAN_MOOD_MINIMUM:
        return {
            "should_reply": False,
            "reason": f"心情过低({current_mood_val}/100)，不想说话",
            "mood_impact": 0,
        }

    # 用预过滤器在扫描模式下过滤队列中的消息
    # 只保留有实质性内容的消息
    viable_messages = []
    for ctx in queued_contexts:
        prefilter_result = reply_prefilter.should_skip_ai_decision(
            user_name=ctx.get("display_name", "未知"),
            current_msg=ctx.get("llm_text", ""),
            is_at_me=False,
            is_sticker=len(ctx.get("stickers", [])) > 0,
            history_messages=history_messages,
            scan_mode=True,
        )
        if not prefilter_result.should_skip_ai:
            viable_messages.append(ctx)

    if not viable_messages:
        logger.info(f"扫描模式: 队列中 {len(queued_contexts)} 条消息均被质量过滤")
        return {"should_reply": False, "reason": "没有有实质内容的消息"}

    logger.info(f"扫描模式: 队列 {len(queued_contexts)} 条 → 预过滤后 {len(viable_messages)} 条有效消息")

    # 构建紧凑的扫描 prompt（取最近 8 条历史 + 全部有效待处理消息）
    recent_history = history_messages[-8:] if len(history_messages) > 8 else history_messages
    history_str = "\n".join(f"[{i}] {msg}" for i, msg in enumerate(recent_history))

    # 注入记忆（用最后一条有效消息做向量搜索，匹配回复目标）
    memory_text = "暂无相关记忆"
    try:
        last_msg = viable_messages[-1].get("llm_text", "")
        if last_msg:
            query_vectors = await get_embeddings([last_msg])
            if query_vectors and len(query_vectors) > 0:
                memories = await vector_db.query_memory(group_id, query_vectors[0], n_results=2)
                if memories:
                    memory_text = "\n".join(f"- {m}" for m in memories)
    except Exception:
        pass

    # 获取高频黑话
    learned_slangs = await db_manager.get_slang_candidates(group_id, min_freq=30, stage=2)
    slang_text = ""
    if learned_slangs:
        slang_items = [f"- {s['phrase']}: {s['definition']}" for s in learned_slangs]
        slang_text = "\n".join(slang_items)

    # 构建有效待处理消息摘要（注入到 prompt 中）
    viable_summary = "\n".join(
        f"- {ctx.get('display_name', '未知')}: {ctx.get('llm_text', '')[:80]}" for ctx in viable_messages
    )

    prompt = (
        f"你是'{bot_config.bot_name}'，一个群聊里的真人，刚离开一会儿回来看看。\n"
        f"心情{current_mood_val}/100。\n\n"
        f"### 记忆：\n{memory_text}\n"
    )
    if slang_text:
        prompt += f"\n### 群内黑话：\n{slang_text}\n"
    prompt += (
        f"\n### 历史：\n{history_str}\n\n"
        f"### 你没看到的新消息：\n{viable_summary}\n\n"
        f"### 决定是否加入对话。规则：\n"
        f"1. 你是真人不是客服，不需要每条都回\n"
        f"2. 必须有记忆关联或你有料可说才开口，只能说'哈哈'就别回\n"
        f"3. 话题已冷（最后一条过了5+条消息）→ 不追\n"
        f"4. 心情很低(<40)→更谨慎\n"
        f"5. 回看群聊就像打开群看了一眼，自然一点\n"
        f'输出JSON：{{"should_join":true/false,"reason":"简述","mood_impact":-2~+5}}'
    )

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=20.0)

    try:
        optimized_prompt, prompt_tokens = context_manager.truncate_text(
            text=prompt, model_alias=model_alias, max_output_tokens=100, reserve_ratio=0.1
        )

        if prompt_tokens > 0:
            print(
                f"[上下文管理] 扫描模式, 使用tokens: {prompt_tokens}/{context_manager.get_model_max_tokens(model_alias)}"
            )

        stream = await openai_compat.create_with_auto_fallback(
            client=client,
            model=creds["model"],
            messages=[{"role": "user", "content": optimized_prompt}],
            base_url=creds["base_url"],
            use_response_format=True,
            stream=True,
        )

        stream_result = await thinking_handler.process_streaming_response(
            stream=stream,
            model_name=creds["model"],
            collect_thinking=True,
        )

        content = stream_result["content"].strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)
        should_join = decision.get("should_join", False)
        mood_impact = decision.get("mood_impact", 0)
        reason = decision.get("reason", "")

        print(f"扫描决策: [加入:{should_join}] [心情:{mood_impact:+}] [理由:{reason}]")

        if not should_join:
            return {"should_reply": False, "reason": reason, "mood_impact": mood_impact}

        # 如果决定加入，选最新的有效消息回复（扫描模式只接最新话题）
        latest_ctx = viable_messages[-1]
        return {
            "should_reply": True,
            "reason": reason,
            "mood_impact": mood_impact,
            "target_context": latest_ctx,
            "reply_to_user": latest_ctx.get("display_name", "未知"),
            "target_message_content": latest_ctx.get("llm_text", ""),
            "target_message_id": latest_ctx.get("message_id"),
            "interest_score": bot_config.interest_threshold,  # 使用配置阈值，确保一致
        }

    except json.JSONDecodeError as e:
        logger.error(f"扫描决策JSON解析失败: {e}")
        return {"should_reply": False, "reason": "JSON解析失败"}
    except Exception as e:
        logger.opt(exception=True).error(f"扫描决策出错: {type(e).__name__}: {e}")
        return {"should_reply": False, "reason": f"异常: {type(e).__name__}"}
