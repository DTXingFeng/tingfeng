from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
import json

async def should_i_reply(group_id: int, user_name: str, current_msg: str, is_at_me: bool = False) -> dict:
    """
    判断机器人是否应该参与当前对话，并评价该对话对机器人心情的影响
    """
    # 1. 获取配置
    model_alias = ai_config.decision_model
    if not model_alias:
        return {"should_reply": False, "mood_impact": 0}
        
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"should_reply": False, "mood_impact": 0}

    # 获取当前心情（作为参考）
    current_mood_val = db_manager.get_mood(group_id)

    # 2. 准备上下文 (获取最近 10 条消息)
    history = db_manager.get_chat_log(group_id, limit=10)
    history_str = "\n".join(history)

    # 3. 构造决策 Prompt
    prompt = (
        f"你现在是群聊机器人'{bot_config.bot_name}'的感性大脑，负责决策和情感评估。\n"
        f"你的角色设定是：{bot_config.identity}\n"
        f"你当前的内心状态（心情值）：{current_mood_val} (0-100，50为平静)\n\n"
        "### 任务：\n"
        f"1. 判断'{bot_config.bot_name}'是否应该回复当前消息。\n"
        f"2. 评估当前消息及上下文对'{bot_config.bot_name}'心情的影响。\n\n"
        "### 判断准则：\n"
        f"1. **回复决策**：\n"
        f"   - 如果 is_at_me 为 true，通常应该回复，除非对方在辱骂或无理取闹。\n"
        f"   - 如果用户在接你上一句话，或者在询问你，则应该回复。\n"
        f"   - 如果话题是你感兴趣的（二次元、游戏等），可以主动插话。\n"
        f"2. **心情评估 (mood_impact)**：\n"
        f"   - 别人夸奖、关心、聊愉快的话题：+1 到 +5。\n"
        f"   - 别人辱骂、欺负、冷落、聊压抑的话题：-1 到 -10。\n"
        f"   - 正常的交流、被需要、被认可：+1 到 +2。\n"
        f"   - 感到尴尬、不知所措、被开过分的玩笑：-1 到 -3。\n\n"
        f"### 上下文信息：\n"
        f"最近记录：\n{history_str}\n"
        f"当前消息：{user_name}: {current_msg}\n"
        f"是否艾特你：{is_at_me}\n\n"
        "### 输出要求：\n"
        "请直接输出 JSON 格式：\n"
        "{\n"
        "  \"should_reply\": boolean,\n"
        "  \"mood_impact\": number (-10 到 10 之间的整数),\n"
        "  \"reason\": \"简短的理由\",\n"
        "  \"is_replying_to_bot\": boolean,\n"
        "  \"interest_score\": number (0-1)\n"
        "}"
    )

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)
        
        # 结果解析
        should_reply = decision.get('should_reply', False)
        mood_impact = decision.get('mood_impact', 0)
        interest_score = decision.get('interest_score', 0)
        is_replying_to_bot = decision.get('is_replying_to_bot', False)
        
        print(f"决策引擎: [回复:{should_reply}] [心情:{mood_impact:+} ] [理由:{decision.get('reason')}]")
        
        return {
            "should_reply": should_reply,
            "mood_impact": mood_impact,
            "interest_score": interest_score,
            "is_replying_to_bot": is_replying_to_bot
        }

    except Exception as e:
        print(f"决策过程出错: {e}")
        return {"should_reply": is_at_me, "mood_impact": 0}
