from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from src.mcp.registry import tool_registry
from typing import Optional
import json
import asyncio

logger = get_logger(__name__)


async def should_i_reply(
    group_id: int, user_name: str, current_msg: str, is_at_me: bool = False, user_id: Optional[int] = None
) -> dict:
    """
    判断机器人是否应该参与当前对话，并评价该对话对机器人心情的影响
    """
    # 0. 发言频率控制 - 只限制主动发言，被艾特时不限制
    if not is_at_me:
        recent_replies = await db_manager.get_recent_reply_count(group_id, minutes=10)
        last_reply_time = await db_manager.get_last_reply_time(group_id)

        # 频率限制配置（仅针对主动发言）
        MAX_REPLIES_10MIN = 3  # 10分钟内最多主动回复次数（从5降低到3）
        MIN_INTERVAL_SECONDS = 60  # 两次主动回复间最小间隔（从30秒提高到60秒）

        # 计算距离上次回复的时间
        from datetime import datetime

        time_since_last_reply = None
        if last_reply_time:
            time_since_last_reply = (datetime.now() - last_reply_time).total_seconds()

        # 频率检查：只对主动发言进行限制
        if recent_replies >= MAX_REPLIES_10MIN:
            logger.info(f"频率限制: 10分钟内已主动回复{recent_replies}次，跳过非艾特消息")
            return {"should_reply": False, "mood_impact": 0}

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

    # 构建带索引的历史消息，方便 AI 选择
    history_with_index = []
    for idx, msg in enumerate(history):
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
    prompt = (
        f"你现在是群聊机器人'{bot_config.bot_name}'的感性大脑，负责决策和情感评估。\n"
        f"你的角色设定是：{bot_config.identity}\n"
        f"你当前的内心状态：\n"
        f"- 心情值：{current_mood_val} (0-100)\n"
        f"- 性格特征：{json.dumps(traits, ensure_ascii=False)}\n"
        f"- 最近的内心独白：{recent_thoughts}\n\n"
        "### 你的背景记忆：\n"
        f"{memory_str}\n"
        f"{slang_context}\n\n"
        "### 任务：\n"
        f"1. **理解上下文**：结合黑话库，深度解码当前对话的真实含义（注意识别谐音、缩写或游戏暗语）。\n"
        f"2. **选择回复目标**：从历史消息中选择**一条**最值得回复的消息（不限于最新消息）。你可以回复历史记录中的任何一条消息，只要它值得回应。\n"
        f"3. 判断'{bot_config.bot_name}'是否应该回复。\n"
        f"4. 评估选定消息对'{bot_config.bot_name}'心情的影响。\n\n"
        "### 判断准则：\n"
        "1. **核心原则 (Stay Silent - 沉默是金)**：\n"
        "   - 你是一个真实的人，而不是一个随时待命的 AI 助手。你不需要对群里发生的每一件事都发表评论。\n"
        "   - **默认策略是沉默**：除非有充分理由回复，否则保持沉默。群聊是人类的交流空间，你作为幽灵应该克制介入的冲动。\n"
        "   - 宁可不回复，也不要让人觉得你'嘴碎'或'刷存在感'。\n"
        "   - 适度克制比过度参与更重要。\n"
        "2. **选择回复目标 (target_message_index)**：\n"
        "   - 仔细阅读历史消息，寻找最值得回复的内容。\n"
        "   - 你可以选择回复历史记录中的**任何一条消息**，不必是最新的。\n"
        "   - 优先选择：与你相关的话题、对你的提及、有趣的内容、或你感兴趣的话题。\n"
        "   - 如果最新消息不值得回复，但历史中有一条重要消息被忽略了，你可以选择回复那条旧消息。\n"
        "   - **历史消息格式**：每条消息前有索引号 `[0]`、`[1]`、`[2]` 等，你需要返回你选择的消息索引。\n"
        "3. **回复决策 (should_reply)** - 请严格执行以下标准：\n"
        "   - **对话流向分析（核心）**：\n"
        "     * 首先判断历史消息的对话流向：是「用户A↔用户B」的双人对话，还是「用户↔你」的对话，还是「多人群聊」。\n"
        "     * 如果是「用户A↔用户B」的连续对话（如：用户A问→用户B答→用户A追问），且内容与你无关，**严禁插话**，这是他们的私人对话空间。\n"
        "     * 如果是「用户A→用户B→用户A」的快速来回，即使中间偶尔有人提到'你'或'它'，那也是他们在互相指代，不是在叫你。\n"
        "     * 只有当对话明显与你的话题、你的发言、或你的记忆相关时，才考虑参与。\n"
        "   - **上下文关联性优先**：仔细检查历史消息，如果上一条或最近几条消息是你（self）发送的，而当前消息是自然的对话延续（如回答你的问题、接续你的话题、对你的话做出反应），则强烈建议回复，即使没有艾特你。\n"
        "   - **指代消歧（关键）**：\n"
        "     * 历史消息中的「你」、「它」、「这个东西」等代词，需要仔细判断指代对象。\n"
        "     * 例如：「用户A: 你觉得呢？用户B: 还行吧」→ 这里的「你」指用户A在问用户B，不是在问你（{bot_config.bot_name}）。\n"
        "     * 只有当上下文明确显示话题与你相关、或者上一条消息是你发的、或者明确提到你的名字时，代词才可能指你。\n"
        "   - 如果 is_at_me 为 true，通常应该回复，除非对方在明显刷屏、辱骂或无理取闹。\n"
        "   - **关于图片**：除非图片内容直接提及你、或者是你记忆中的重要物品/场景，否则不要随意'点评'别人的图片。人类发图通常是在互相交流，你作为一个幽灵，随意插话点评图片会显得非常唐突且'AI 味'十足。\n"
        "   - **适度参与**：即使没有相关记忆，如果话题轻松有趣（如梗图、游戏、搞笑内容、日常闲聊），也可以适度参与，给出简短的反应。\n"
        "   - **记忆驱动**：当话题与你的背景记忆（长期记忆、用户往事）有高度重合时，应优先考虑回复。\n"
        "   - **无聊话题直接跳过**：普通的日常寒暄、问候、没有实质内容的闲聊，直接判定为不回复。\n"
        "4. **兴趣评分 (interest_score)** - 严格标准：\n"
        "   - 评估你对选定话题的'参与必要性'。0 代表完全不感兴趣/无关，1 代表必须立刻加入对话。\n"
        "   - **上下文关联**：如果这是对你上一句话的回应或接续，兴趣评分至少应为 0.5-0.7。\n"
        "   - 有趣的梗图、游戏话题、搞笑内容、轻松的日常闲聊：**只给 0.15-0.35 的评分**（降低了原来的 0.25-0.5）。\n"
        "   - **只有与记忆强相关、对你非常重要、或直接艾特你的话题才给 0.75 以上的高分**。\n"
        "   - 普通话题的兴趣评分不应超过 0.5。\n"
        "5. **心情评估 (mood_impact)**：\n"
        f"   - **核心原则**：你是一个有一定心理承受能力的真实少女，不要因为一点琐事就心情不好。只有明确针对你、且带有恶意或严重冒犯的言论才需要扣分。\n"
        f"   - 别人夸奖、关心、聊愉快的话题：+1 到 +3。\n"
        f"   - **严重辱骂、持续性恶意攻击**：-5 到 -12。\n"
        f"   - 正常的交流、被需要、被认可：+1。\n"
        f"   - 轻微的吐槽、无伤大雅的玩笑、被冷落：**不扣分 (0)**。\n"
        f"   - 感到尴尬、被开**过分**的玩笑：-1 到 -3。\n"
        f"   - **无关话题**：无论大家聊得多么火热或压抑，只要不涉及你，一律视为心情无影响 (0)。\n\n"
        f"### 上下文信息：\n"
        f"最近记录（带索引）：\n{history_str}\n"
        f"### 重要格式说明：\n"
        f'1. **引用消息格式**：历史记录中可能出现 `[回复@用户名: "内容"]` 格式，这表示「当前消息的发送者正在引用/回复某位用户的话」。\n'
        f"   - 例如：`用户A: 我觉得不对 [回复@用户B: \"你说的对\"]` 表示「用户A正在回复用户B说过的话，用户B才说了'你说的对'」。\n"
        f"   - 引用内容是「被引用者」说的，不是「当前消息发送者」说的。请仔细区分！\n"
        f"2. **指代消歧规则（核心规则，必须严格执行）**：\n"
        f"   - **基本原则**：历史消息中的「你」、「它」、「这个东西」、「那个」等代词，需要根据上下文严格判断指代对象。\n"
        f"   - **双向对话判断**：\n"
        f"     * 如果历史显示「用户A」和「用户B」在快速来回对话（A→B→A→B...），他们之间的「你」互相指代，不是在叫你（{bot_config.bot_name}）。\n"
        f"     * 示例：`用户A: 你觉得呢？用户B: 还行吧。用户A: 那你呢？` → 这是A和B在对话，与你无关。\n"
        f"   - **只有以下情况，「你」才可能指你**：\n"
        f"     * 消息明确艾特你（{bot_config.bot_name}）\n"
        f"     * 消息直接提到你的名字「{bot_config.bot_name}」\n"
        f"     * 上一条消息是你（self）发的，而当前消息在回应\n"
        f"     * 上下文明确显示话题与你的发言、你的记忆、或你的设定相关\n"
        f"   - **默认策略**：如果无法确定「你」是否指你，**默认不指你**，保持沉默。\n"
        f"3. **对话流向分析**：\n"
        f"   - 仔细观察消息的发送者和接收者关系，判断对话是在用户之间进行，还是用户与你之间进行。\n"
        f"   - 如果发现是「用户A↔用户B」的双人对话流程，且不涉及你，**严禁插话**。\n\n"
        f"当前消息：{user_name}: {current_msg}\n"
        f"是否艾特你：{is_at_me}\n\n"
        "### 输出要求：\n"
        "请直接输出 JSON 格式：\n"
        "{\n"
        f'  "should_reply": boolean,\n'
        f'  "target_message_index": number (选择回复的历史消息索引，0-{max_idx}),\n'
        f'  "reply_to_user": "指定回复对象的用户名（必须从选定消息或上下文中选择）",\n'
        f'  "mood_impact": number (-10 到 10 之间的整数),\n'
        f'  "reason": "简短的理由（说明为什么选择这条消息）",\n'
        f'  "is_replying_to_bot": boolean,\n'
        f'  "interest_score": number (0-1)\n'
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

        # 构建请求参数
        request_params = {
            "model": creds["model"],
            "messages": [{"role": "user", "content": optimized_prompt}],
            "response_format": {"type": "json_object"},
            "stream": True,
        }

        # 如果有 MCP 工具可用，添加工具支持
        if mcp_tools:
            request_params["tools"] = mcp_tools
            request_params["tool_choice"] = "auto"
            # 移除 response_format，因为工具调用与 JSON 格式不兼容
            del request_params["response_format"]

        stream = await client.chat.completions.create(**request_params)

        content = ""
        tool_calls_buffer = {}  # 存储工具调用

        async for chunk in stream:
            # 收集文本内容
            if chunk.choices and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content

            # 收集工具调用
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    idx = tool_call.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": tool_call.id, "name": "", "arguments": ""}

                    if tool_call.function and tool_call.function.name:
                        tool_calls_buffer[idx]["name"] = tool_call.function.name
                    if tool_call.function and tool_call.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tool_call.function.arguments

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
                    import json as json_lib

                    if isinstance(tool_args, str):
                        tool_args = json_lib.loads(tool_args)
                except json_lib.JSONDecodeError as e:
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

            # 重新请求最终决策（不带工具）
            stream = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "user", "content": optimized_prompt}],
                response_format={"type": "json_object"},
                stream=True,
            )

            content = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content

        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)

        # 结果解析
        should_reply = decision.get("should_reply", False)
        target_message_index = decision.get("target_message_index", max_idx)  # 默认选择最新消息

        # 验证索引有效性
        if target_message_index < 0 or target_message_index > max_idx:
            target_message_index = max_idx

        # 从选定的消息中提取用户名和纯消息内容
        selected_message = history[target_message_index]
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

        print(
            f"决策引擎: [回复:{should_reply}] [目标消息:{target_message_index}] [对象:{reply_to_user}] [内容:{target_message_content[:30]}...] [兴趣:{interest_score}] [心情:{mood_impact:+}] [理由:{decision.get('reason')}]"
        )

        return {
            "should_reply": should_reply,
            "target_message_index": target_message_index,
            "target_message_content": target_message_content,  # 纯消息内容(不含用户名)
            "selected_user": selected_user,  # 选定消息的发送者
            "reply_to_user": reply_to_user,  # AI选择的回复对象
            "mood_impact": mood_impact,
            "interest_score": interest_score,
            "is_replying_to_bot": is_replying_to_bot,
        }

    except json.JSONDecodeError as e:
        logger.error(f"决策结果JSON解析失败: {e}, 原始内容: {content}")
        return {"should_reply": is_at_me, "mood_impact": 0}
    except Exception as e:
        logger.error(f"决策过程出错: {e}", exc_info=True)
        return {"should_reply": is_at_me, "mood_impact": 0}
