from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
import json

async def should_i_reply(group_id: int, user_name: str, current_msg: str) -> bool:
    """
    判断机器人是否应该参与当前对话
    1. 即使没有艾特，是否有人在回复机器人？
    2. 对话内容是否符合机器人的兴趣点？
    """
    # 1. 获取配置
    model_alias = ai_config.decision_model
    if not model_alias:
        return False
        
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return False

    # 2. 准备上下文 (获取最近 10 条消息)
    history = db_manager.get_chat_log(group_id, limit=10)
    history_str = "\n".join(history)

    # 3. 构造决策 Prompt
    # 这里的目标是让模型输出一个简单的 JSON，判断是否需要回复
    prompt = (
        f"你现在是群聊机器人'{bot_config.bot_name}'的决策大脑。\n"
        f"你的角色设定是：{bot_config.identity}\n\n"
        "### 任务：\n"
        f"请根据最近的聊天记录和当前收到的消息，判断'{bot_config.bot_name}'是否应该回复这条消息。\n\n"
        "### 判断准则：\n"
        f"1. **直接交互**：即使没有艾特，如果用户明显是在接'{bot_config.bot_name}'上一句话，或者在询问'{bot_config.bot_name}'，则应该回复。\n"
        f"2. **兴趣匹配**：如果对话内容涉及符合你设定的兴趣话题，或者你认为有必要参与讨论，则可以考虑回复。\n"
        "3. **社交礼仪**：如果别人正在进行私密对话或与你无关的严肃讨论，则不应打扰。\n\n"
        f"### 最近聊天记录：\n{history_str}\n"
        f"### 当前收到的消息：\n{user_name}: {current_msg}\n\n"
        "### 输出要求：\n"
        "请直接输出 JSON 格式，包含以下字段：\n"
        f"- 'is_replying_to_bot': boolean (用户是否在接'{bot_config.bot_name}'的话，或者在跟'{bot_config.bot_name}'说话)\n"
        "- 'should_reply': boolean (综合判断是否回复)\n"
        "- 'reason': string (简短的原因)\n"
        "- 'interest_score': number (对该话题的兴趣度 0-1)"
    )

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])

    try:
        # 使用配置的模型进行决策
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # Qwen 2.5 7B 等小模型通常支持 JSON 模式
        )
        
        content = response.choices[0].message.content.strip()
        
        # 兼容 Reasoner 可能输出的 Markdown 代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)
        
        # 结果解析
        should_reply = decision.get('should_reply', False)
        interest_score = decision.get('interest_score', 0)
        is_replying_to_bot = decision.get('is_replying_to_bot', False) # 新增：是否在回我
        
        print(f"决策结果: [回我:{is_replying_to_bot}] [兴趣:{interest_score}] [建议:{should_reply}] (原因: {decision.get('reason')})")
        
        return {
            "should_reply": should_reply,
            "interest_score": interest_score,
            "is_replying_to_bot": is_replying_to_bot
        }

    except Exception as e:
        print(f"决策过程出错: {e}")
        return False
