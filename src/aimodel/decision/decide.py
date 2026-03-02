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
    pattern = r'\[回复@[^:]+:\s*\]'
    cleaned = re.sub(pattern, '', text)
    
    # 清理富文本标签（如图片HTML标签）
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
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

    # 获取当前心情（作为参考）
    current_mood_val = await db_manager.get_mood(group_id)

    # 获取人格状态
    personality_state = await db_manager.get_personality_state(group_id)
    traits = personality_state.get("traits", {})
    recent_thoughts = personality_state.get("recent_thoughts", "暂无")

    # 2. 准备上下文 (获取最近 15 条消息，提供更多选择空间)
    history = await db_manager.get_chat_log(group_id, limit=15)

    # 提取消息文本和对应的 message_id，并清理引用格式
    history_messages = []
    history_message_ids = []
    for item in history:
        # 清理引用格式，避免AI模仿
        clean_msg = clean_reply_format(item["message"])
        history_messages.append(clean_msg)
        history_message_ids.append(item["message_id"])

    # 构建带索引的历史消息，方便 AI 选择
    history_with_index = []
    for idx, msg in enumerate(history_messages):
        history_with_index.append(f"[{idx}] {msg}")
    history_str = "\n".join(history_with_index)

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
            long_term_memories = await vector_db.query_memory(group_id, query_vectors[0], n_results=3)
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

    # 4. 构造决策 Prompt
    max_idx = len(history) - 1  # 历史消息的最大索引

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
    bot_recently_spoke = False
    if len(history_messages) > 0:
        for msg in reversed(history_messages[-3:]):
            if msg.startswith(bot_config.bot_name + ":") or msg.startswith(f"{bot_config.bot_name}:"):
                bot_recently_spoke = True
                break

    prompt = (
        f"你是'{bot_config.bot_name}'的决策大脑。当前状态：心情{current_mood_val}/100，性格{json.dumps(traits, ensure_ascii=False)}，最近想法：{recent_thoughts}\n"
        f"对话类型：{conversation_type}，最近发言：{'是' if bot_recently_spoke else '否'}\n\n"
        f"### 记忆：\n{memory_str}\n{slang_context}\n\n"
        "### 任务：\n"
        "1. 判断对话场景（A/B/C），选择最值得回复的消息（可以是历史中的任何一条）\n"
        "2. 决定是否回复，评估心情影响\n\n"
        "### 场景判断（核心）：\n"
        "**A. 正在和你对话**（0.5-0.95分）：历史有你的发言，当前消息在回应/延续你的话。优先回复。\n"
        "**B. 提到你但未对话**（0.1-0.5分）：被作为话题讨论，谨慎插话。\n"
        "**C. 完全无关**（0.0-0.7分）：他人交流，必须有强关联记忆才考虑参与：\n"
        "   - **强关联记忆**（必须满足至少一条）\n"
        "     * 记忆中明确提到过该话题/关键词\n"
        "     * 记忆中与当前消息内容高度相关（相同事件、相似经历）\n"
        "     * 有明确的用户印象或往事与此话题直接相关\n"
        "   - **评分标准**\n"
        "     * 有强关联记忆且能提供有价值信息：0.5-0.7分\n"
        "     * 有弱关联记忆（仅略微相关）：0.1-0.3分\n"
        "     * 无关联记忆：0分（绝不参与）\n"
        "   - 只能说'哈哈''厉害'这种废话 → 即使有记忆也不参与\n"
        "   - 默认沉默，有强关联记忆且有料才说\n"
        "   - **关键约束**：即使满足上述条件，也必须遵守你的人设风格（极简自然、符合性格），绝对不能为了参与而参与导致表现人机感\n\n"
        "### 核心原则：\n"
        "- **沉默是金**：默认不回复，你是真人不是助手，不需要对每件事都评论\n"
        "- **指代消歧**：历史中的'你'需要判断是否指你。用户A↔用户B的快速来回，他们的'你'互相指代，不是在叫你\n"
        "  - 只有以下情况'你'才指你：明确艾特你/提到你的名字/上一条是你发的/上下文明确与你相关\n"
        "  - 无法确定 → 默认不指你\n"
        "- **对话流向**：如果是用户A↔用户B的双人对话，不涉及你 → 严禁插话\n"
        "- **绝对禁止复读攻击性言论**：不要选择包含攻击、嘲讽、贬低他人的消息进行回复，即使对方@你\n"
        "  - 例如：对方说'你真蠢'，不要回复'你真蠢'\n"
        "  - 正确做法：用不同的方式回应，或者选择忽略\n"
        "- **记忆驱动**：\n"
        "  - 场景A/B：话题与记忆重合可提升兴趣，但不是必需\n"
        "  - 场景C：必须有强关联记忆才能参与，无记忆绝不插话\n"
        "- **心情影响**：\n"
        "  - 夸奖/关心/愉快话题：+1~+3\n"
        "  - 严重辱骂/恶意攻击：-5~-12\n"
        "  - 轻微吐槽/玩笑/冷落：0（别太敏感）\n"
        "  - 无关话题：0\n\n"
        f"### 上下文信息：\n"
        f"最近记录（带索引）：\n{history_str}\n"
        f"### 格式说明：\n"
        f'- 引用格式 [回复@用户名: "内容"] 表示「当前发送者在回复某用户」，引用内容是「被引用者」说的\n'
        f"- 历史消息中的'你''它'等代词需要判断是否指你（见前述指代消歧规则）\n\n"
        f"当前消息：{user_name}: {current_msg}\n"
        f"是否艾特你：{is_at_me}\n"
        f"是否表情包：{is_sticker}\n\n"
        "### 输出要求：\n"
        "请直接输出 JSON 格式：\n"
        "{\n"
        f'  "should_reply": boolean,\n'
        f'  "target_message_index": number (选择回复的历史消息索引，0-{max_idx}),\n'
        f'  "reply_to_user": "指定回复对象的用户名（必须从选定消息或上下文中选择）",\n'
        f'  "mood_impact": number (-10 到 10 之间的整数),\n'
        f'  "reason": "简短的理由（说明为什么选择这条消息）",\n'
        f'  "is_replying_to_bot": boolean,\n'
        f'  "interest_score": number (0-1),\n'
        f'  "conversation_scene": "A/B/C (场景识别：A=正在和bot对话, B=提到bot但未对话, C=完全没和bot聊天)"\n'
        f"}}"
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

        print(
            f"决策引擎: [场景:{conversation_scene}({scene_desc})] [回复:{should_reply}] [目标消息:{target_message_index}] [消息ID:{selected_message_id}] [对象:{reply_to_user}] [内容:{target_message_content[:30]}...] [兴趣:{interest_score}] [心情:{mood_impact:+}] [理由:{decision.get('reason')}]"
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
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        logger.opt(exception=True).error("决策过程出错: {}: {}", type(e).__name__, error_msg)
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
