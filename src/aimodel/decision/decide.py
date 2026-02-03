from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from typing import Optional
import json

logger = get_logger(__name__)

async def should_i_reply(group_id: int, user_name: str, current_msg: str, is_at_me: bool = False, user_id: Optional[int] = None) -> dict:
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
    
    # 获取人格状态
    personality_state = db_manager.get_personality_state(group_id)
    traits = personality_state.get("traits", {})
    recent_thoughts = personality_state.get("recent_thoughts", "暂无")

    # 2. 准备上下文 (获取最近 10 条消息)
    history = db_manager.get_chat_log(group_id, limit=10)
    history_str = "\n".join(history)

    # 3. 检索相关记忆与知识
    user_profile = db_manager.get_user_impression(group_id, user_name)
    user_specific_memories = db_manager.get_user_specific_memories(group_id, user_name, limit=3)
    
    # 注入高频黑话（只使用频率>=30的已验证黑话）
    learned_slangs = db_manager.get_slang_candidates(group_id, min_freq=30, stage=2)
    slang_context = ""
    if learned_slangs:
        slang_list = [f"- {s['phrase']}: {s['definition']}" for s in learned_slangs]
        slang_context = "\n### 本群特有黑话/暗语库：\n" + "\n".join(slang_list)
    
    long_term_memories = []
    try:
        query_vectors = await get_embeddings([current_msg])
        long_term_memories = vector_db.query_memory(group_id, query_vectors[0], n_results=3)
    except:
        pass

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
    
    memory_str = "\n".join(memory_context) if memory_context else "暂无相关背景记忆。"

    # 4. 构造决策 Prompt
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
        f"2. 判断'{bot_config.bot_name}'是否应该回复当前消息。\n"
        f"3. 评估当前消息及上下文对'{bot_config.bot_name}'心情的影响。\n\n"
        "### 判断准则：\n"
        "1. **核心原则 (Stay Silent)**：你是一个真实的人，而不是一个随时待命的 AI 助手。你不需要对群里发生的每一件事都发表评论。保持适度的克制，但也不必过于高冷。\n"
        "2. **回复决策 (should_reply)**：\n"
        "   - **上下文关联性优先**：仔细检查历史消息，如果上一条或最近几条消息是你（self）发送的，而当前消息是自然的对话延续（如回答你的问题、接续你的话题、对你的话做出反应），则强烈建议回复，即使没有艾特你。\n"
        "   - **对话流向分析**：判断当前消息是否是「接话」。如果用户在回应你的话、继续你开启的话题、或对你说的话有反应，这就算作上下文关联，应该回复。\n"
        "   - 如果 is_at_me 为 true，通常应该回复，除非对方在明显刷屏、辱骂或无理取闹。\n"
        "   - **关于图片**：除非图片内容直接提及你、或者是你记忆中的重要物品/场景，否则不要随意'点评'别人的图片。人类发图通常是在互相交流，你作为一个幽灵，随意插话点评图片会显得非常唐突且'AI 味'十足。\n"
        "   - **适度参与**：即使没有相关记忆，如果话题轻松有趣（如梗图、游戏、搞笑内容、日常闲聊），也可以适度参与，给出简短的反应。兴趣评分达到 0.25 以上即可考虑回复。\n"
        "   - **记忆驱动**：当话题与你的背景记忆（长期记忆、用户往事）有高度重合时，应优先考虑回复。\n"
        "3. **兴趣评分 (interest_score)**：\n"
        "   - 评估你对当前话题的'参与必要性'。0 代表完全不感兴趣/无关，1 代表必须立刻加入对话。\n"
        "   - **上下文关联**：如果这是对你上一句话的回应或接续，兴趣评分至少应为 0.5-0.7。\n"
        "   - 有趣的梗图、游戏话题、搞笑内容、轻松的日常闲聊可以给 0.25-0.5 的评分。\n"
        "   - 只有与记忆强相关或对你非常重要的话题才给 0.7 以上的高分。\n"
        "4. **心情评估 (mood_impact)**：\n"
        f"   - **核心原则**：你是一个有一定心理承受能力的真实少女，不要因为一点琐事就心情不好。只有明确针对你、且带有恶意或严重冒犯的言论才需要扣分。\n"
        f"   - 别人夸奖、关心、聊愉快的话题：+1 到 +3。\n"
        f"   - **严重辱骂、持续性恶意攻击**：-5 到 -12。\n"
        f"   - 正常的交流、被需要、被认可：+1。\n"
        f"   - 轻微的吐槽、无伤大雅的玩笑、被冷落：**不扣分 (0)**。\n"
        f"   - 感到尴尬、被开**过分**的玩笑：-1 到 -3。\n"
        f"   - **无关话题**：无论大家聊得多么火热或压抑，只要不涉及你，一律视为心情无影响 (0)。\n\n"
        f"### 上下文信息：\n"
        f"最近记录：\n{history_str}\n"
        f"### 重要格式说明：\n"
        f"1. **引用消息格式**：历史记录中可能出现 `[回复@用户名: \"内容\"]` 格式，这表示「当前消息的发送者正在引用/回复某位用户的话」。\n"
        f"   - 例如：`用户A: 我觉得不对 [回复@用户B: \"你说的对\"]` 表示「用户A正在回复用户B说过的话，用户B才说了'你说的对'」。\n"
        f"   - 引用内容是「被引用者」说的，不是「当前消息发送者」说的。请仔细区分！\n"
        f"2. **指代消歧规则**：\n"
        f"   - 历史消息中的「你」需要根据上下文判断指代对象。\n"
        f"   - 如果是用户A对用户B的对话（如「用户A: 你觉得呢？」），这里的「你」通常指的是用户B，而不是你（{bot_config.bot_name}）。\n"
        f"   - 只有当消息明确艾特你、提到你的名字「{bot_config.bot_name}」、或者是在接你上一句话时，才是对你的称呼。\n"
        f"3. 分析对话流向：仔细观察消息的发送者和接收者关系，判断对话是在用户之间进行，还是用户与你之间进行。\n\n"
        f"当前消息：{user_name}: {current_msg}\n"
        f"是否艾特你：{is_at_me}\n\n"
        "### 输出要求：\n"
        "请直接输出 JSON 格式：\n"
        "{\n"
        "  \"should_reply\": boolean,\n"
        "  \"reply_to_user\": \"指定回复对象的用户名（必须从上下文或当前消息发送者中选择）\",\n"
        "  \"mood_impact\": number (-10 到 10 之间的整数),\n"
        "  \"reason\": \"简短的理由\",\n"
        "  \"is_replying_to_bot\": boolean,\n"
        "  \"interest_score\": number (0-1)\n"
        "}"
    )

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)

    try:
        optimized_prompt, prompt_tokens = context_manager.truncate_text(
            text=prompt,
            model_alias=model_alias,
            max_output_tokens=200,
            reserve_ratio=0.1
        )
        
        if prompt_tokens > 0:
            print(f"[上下文管理] 决策模型: {model_alias}, 使用tokens: {prompt_tokens}/{context_manager.get_model_max_tokens(model_alias)}")
        
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": optimized_prompt}],
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
        reply_to_user = decision.get('reply_to_user', user_name) # 默认回复当前消息发送者
        mood_impact = decision.get('mood_impact', 0)
        interest_score = decision.get('interest_score', 0)
        is_replying_to_bot = decision.get('is_replying_to_bot', False)
        
        print(f"决策引擎: [回复:{should_reply}] [对象:{reply_to_user}] [兴趣:{interest_score}] [心情:{mood_impact:+} ] [理由:{decision.get('reason')}]")
        
        return {
            "should_reply": should_reply,
            "reply_to_user": reply_to_user,
            "mood_impact": mood_impact,
            "interest_score": interest_score,
            "is_replying_to_bot": is_replying_to_bot
        }

    except json.JSONDecodeError as e:
        logger.error(f"决策结果JSON解析失败: {e}, 原始内容: {content}")
        return {"should_reply": is_at_me, "mood_impact": 0}
    except Exception as e:
        logger.error(f"决策过程出错: {e}", exc_info=True)
        return {"should_reply": is_at_me, "mood_impact": 0}
