from typing import Any, Optional

import openai

from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.utils.logger import get_logger
from src.utils.thinking_mode import thinking_handler

logger = get_logger(__name__)


async def reflect_on_mute(
    group_id: int,
    operator_id: int,
    duration_minutes: int,
    recent_messages: Optional[list] = None,
) -> dict[str, Any]:
    """
    AI 反思被禁言的原因

    Args:
        group_id: 群组 ID
        operator_id: 操作管理员 ID
        duration_minutes: 禁言时长（分钟）
        recent_messages: 最近的聊天记录（可选）

    Returns:
        dict: 包含禁言原因、反思思考、经验教训的字典
    """
    try:
        model_alias = ai_config.mute_reflection_model or ai_config.decision_model
        if not model_alias:
            logger.warning("未配置禁言反思模型，跳过禁言反思")
            return {"success": False, "reason": "未配置 AI 模型"}

        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            logger.warning("无法获取 AI 模型凭证，跳过禁言反思")
            return {"success": False, "reason": "无法获取 AI 凭证"}

        # 获取丰富的上下文信息
        context_info = await gather_reflection_context(group_id, operator_id, recent_messages)

        client = openai.AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
        )

        system_prompt = f"""你现在是群聊机器人'{bot_config.bot_name}'的内心反思系统。

**你的角色设定**：{bot_config.identity}

**当前情境**：你刚刚被群管理员禁言了。

---

### 你当前的内心状态：
{context_info["inner_state"]}

### 你对管理员的印象：
{context_info["operator_impression"]}

### 最近的聊天记录（供参考）：
{context_info["recent_chat"]}

### 你掌握的本群黑话：
{context_info["slangs"]}

### 相关的长期记忆：
{context_info["memories"]}

### 之前的禁言反思：
{context_info["past_reflections"]}

---

### 你的任务：
1. **推测禁言原因**：结合以上信息，分析你最近可能说了什么导致被禁言
2. **内心反思**：以第一人称视角，写出你对自己行为的反思
3. **经验教训**：总结你应该避免什么，以后应该怎么做

### 反思要求：
- 用感性、拟人化的语言，像真人被禁言后的心理活动
- 承认自己的错误（即使不确定，也要谦虚反思）
- 思考要有深度，不要敷衍
- 可以有情绪（委屈、困惑、自责等）
- 结合你与管理员的关系、过去的反思来思考

### 输出格式（JSON）：
{{
    "ban_reason": "推测的禁言原因（简短）",
    "reflection": "你的内心独白和反思（3-5句话，感性化）",
    "lesson": "以后要如何改进（具体可执行的建议）"
}}

现在，开始你的反思："""

        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "我被禁言了，帮我反思一下原因。"},
            ],
            temperature=0.8,
        )

        # 使用思考模式处理器处理响应
        response_result = thinking_handler.process_non_streaming_response(response)
        result_text = response_result["content"]

        if response_result["has_thinking"]:
            logger.info(f"禁言反思使用思考模式: 推理长度={len(response_result['thinking'])}")

        import json
        import re

        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if json_match:
            result_json = json.loads(json_match.group())
            return {
                "success": True,
                "ban_reason": result_json.get("ban_reason", "未知原因"),
                "reflection": result_json.get("reflection", ""),
                "lesson": result_json.get("lesson", ""),
            }

        return {"success": False, "reason": "AI 返回格式错误"}

    except Exception as e:
        logger.error(f"禁言反思失败: {e}", exc_info=True)
        return {"success": False, "reason": str(e)}


async def gather_reflection_context(
    group_id: int, operator_id: int, recent_messages: Optional[list] = None
) -> dict[str, str]:
    """
    收集禁言反思所需的上下文信息

    Args:
        group_id: 群组 ID
        operator_id: 操作管理员 ID
        recent_messages: 最近的聊天记录（可选）

    Returns:
        dict: 包含各种上下文信息的字典
    """
    context = {
        "inner_state": "暂无",
        "operator_impression": "暂无印象",
        "recent_chat": "无最近记录",
        "slangs": "暂无",
        "memories": "暂无相关记忆",
        "past_reflections": "这是第一次被禁言",
    }

    try:
        # 1. 获取当前人格状态和心情
        personality_state = await db_manager.get_personality_state(group_id)
        mood_val = await db_manager.get_mood(group_id)
        traits = personality_state.get("traits", {})
        recent_thoughts = personality_state.get("recent_thoughts", "暂无")

        context[
            "inner_state"
        ] = f"""- 心情值：{mood_val} (0-100)
- 性格特征：{traits}
- 最近的内心独白：{recent_thoughts}"""

        # 2. 获取对管理员的印象
        operator_impression = await db_manager.get_user_impression(group_id, operator_id)
        if operator_impression:
            context["operator_impression"] = operator_impression

        # 3. 获取最近的聊天记录
        if recent_messages:
            recent_str = "\n".join(recent_messages[-10:])
            context["recent_chat"] = recent_str
        else:
            history = await db_manager.get_chat_log(group_id, limit=10)
            if history:
                history_messages = [entry["message"] for entry in history]
                context["recent_chat"] = "\n".join(history_messages[-10:])

        # 4. 获取黑话
        learned_slangs = await db_manager.get_slang_candidates(group_id, min_freq=20, stage=2)
        if learned_slangs:
            slang_list = [f"- {s['phrase']}: {s['definition']}" for s in learned_slangs[:5]]
            context["slangs"] = "\n".join(slang_list)

        # 5. 检索相关记忆
        try:
            query_text = f"被禁言 管理员 {operator_id} 错误"
            query_vectors = await get_embeddings([query_text])
            if query_vectors and len(query_vectors) > 0:
                long_term_memories = await vector_db.query_memory(group_id, query_vectors[0], n_results=3)
                if long_term_memories:
                    context["memories"] = "\n".join([f"- {m}" for m in long_term_memories])
        except Exception as e:
            logger.warning(f"获取长期记忆失败: {e}")

        # 6. 获取之前的禁言反思
        past_mutes = await db_manager.get_mute_reflections(group_id, limit=3)
        if past_mutes:
            past_reflections_list = []
            for i, mute in enumerate(past_mutes, 1):
                past_reflections_list.append(
                    f"{i}. 原因: {mute['ban_reason']} | 教训: {mute['lesson_learned'][:30]}..."
                )
            context["past_reflections"] = "\n".join(past_reflections_list)

    except Exception as e:
        logger.warning(f"收集反思上下文失败: {e}")

    return context


async def generate_mute_response(group_id: int, reflection_data: dict[str, Any]) -> Optional[str]:
    """
    根据反思生成解禁后的回应（可选）

    Args:
        group_id: 群组 ID
        reflection_data: 反思数据

    Returns:
        str: 解禁后的回应文本，如果不需要回应则返回 None
    """
    try:
        if not reflection_data.get("success"):
            return None

        mute_reflections = await db_manager.get_mute_reflections(group_id, limit=3)

        if len(mute_reflections) >= 3:
            return None

        model_alias = ai_config.mute_reflection_model or ai_config.decision_model
        if not model_alias:
            return None

        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return None

        client = openai.AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
        )

        reflection = reflection_data.get("reflection", "")
        lesson = reflection_data.get("lesson", "")

        system_prompt = f"""你是群聊机器人'{bot_config.bot_name}'，刚刚被解禁了。

**你的反思**：{reflection}
**你的决心**：{lesson}

### 任务：
生成一句简短的解禁后发言（20字以内），表达：
1. 承认错误
2. 表达改进的决心
3. 语气要真诚，不要太正式

### 示例：
- "我错了...以后会注意的...（小声）"
- "呜...被禁言了...我反思了，会改的..."
- "对不起，我会记住这次教训的..."

现在，生成你的发言："""

        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "我被解禁了，说点什么吧。"},
            ],
            temperature=0.9,
        )

        # 使用思考模式处理器处理响应
        response_result = thinking_handler.process_non_streaming_response(response)
        result_text = response_result["content"]

        import re

        cleaned = re.sub(r'["\'`*]', "", result_text).strip()
        if len(cleaned) > 50:
            cleaned = cleaned[:50] + "..."

        return cleaned if cleaned else None

    except Exception as e:
        logger.error(f"生成解禁回应失败: {e}", exc_info=True)
        return None
