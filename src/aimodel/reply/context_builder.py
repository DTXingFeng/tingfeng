from typing import Dict, List, Optional, Any
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.aimodel.reply.personality import personality_manager
from src.utils.db_manager import db_manager
from src.utils.logger import get_logger
import json

logger = get_logger(__name__)


class ReplyContextBuilder:
    """回复上下文构建器 - 为决策和回复生成提供统一的上下文"""

    def __init__(self):
        self._context_cache = {}

    async def build_context(
        self,
        group_id: int,
        user_name: str,
        current_msg: str,
        user_id: Optional[int] = None,
        reply_message_id: Optional[int] = None,
        bot=None,
    ) -> Dict[str, Any]:
        """
        构建完整的上下文信息

        Returns:
            dict: 包含以下键的字典:
                - history: 历史消息列表
                - user_profile: 用户画像
                - user_specific_memories: 用户具体记忆
                - long_term_memories: 长期记忆
                - personality_state: 人格状态
                - mood_value: 心情值
                - mood_desc: 心情描述
                - thoughts: 内心独白
                - current_state: 当前状态
                - learned_styles: 学习到的风格
                - learned_slangs: 学习到的黑话
                - knowledge_triplets: 知识三元组
                - is_creator: 是否是创造者
                - relationship_data: 关系数据
        """
        context = {}

        try:
            from src.aimodel.memory.embeddings import get_embeddings
            from src.aimodel.memory.vector_db import vector_db

            context["history"] = await db_manager.get_chat_log(group_id, limit=20)
            context["user_profile"] = await db_manager.get_user_impression_cross_group(group_id, user_id) if user_id else None
            context["user_specific_memories"] = await db_manager.get_user_specific_memories_cross_group(
                group_id, user_id, limit=5
            ) if user_id else []

            relationship_data = await db_manager.get_user_relationship_cross_group(group_id, user_id) if user_id else {"favorability": 50, "status": "陌生人"}
            context["relationship_data"] = relationship_data

            context["personality_state"] = await db_manager.get_personality_state(group_id)
            context["mood_value"] = await db_manager.get_mood(group_id) if bot_config.enable_mood else 50
            context["mood_desc"] = self._get_mood_description(context["mood_value"])

            context["thoughts"] = await personality_manager.generate_thoughts(
                group_id, user_name, current_msg, context["history"], context["mood_value"]
            )
            context["current_state"] = personality_manager.get_random_state()

            context["learned_styles"] = await db_manager.get_style_patterns(group_id, limit=5)
            context["learned_slangs"] = await db_manager.get_slang_candidates(group_id, min_freq=3, stage=2)
            context["knowledge_triplets"] = await db_manager.get_knowledge_triplets(group_id, limit=10)

            context["is_creator"] = bool(user_id and bot_config.creator_id and user_id == bot_config.creator_id)

            try:
                query_vectors = await get_embeddings([current_msg])
                context["long_term_memories"] = await vector_db.query_memory(group_id, query_vectors[0], n_results=3)
            except Exception as e:
                logger.debug(f"检索长期记忆失败: {e}")
                context["long_term_memories"] = []

        except Exception as e:
            logger.error(f"构建上下文失败: {e}", exc_info=True)
            context = self._get_empty_context()

        return context

    def _get_mood_description(self, mood_value: int) -> str:
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

    def _get_empty_context(self) -> Dict[str, Any]:
        """返回空上下文"""
        return {
            "history": [],
            "user_profile": None,
            "user_specific_memories": [],
            "long_term_memories": [],
            "personality_state": {"traits": {}, "recent_thoughts": "", "style_vibe": ""},
            "mood_value": 50,
            "mood_desc": self._get_mood_description(50),
            "thoughts": "",
            "current_state": "",
            "learned_styles": [],
            "learned_slangs": [],
            "knowledge_triplets": [],
            "is_creator": False,
            "relationship_data": {"favorability": 50, "status": "陌生人"},
        }

    async def build_decision_prompt(
        self, context: Dict[str, Any], user_name: str, current_msg: str, is_at_me: bool
    ) -> str:
        """构建决策 Prompt"""
        personality_state = context["personality_state"]
        traits = personality_state.get("traits", {})
        recent_thoughts = personality_state.get("recent_thoughts", "暂无")

        history_str = "\n".join(context["history"])

        memory_context = []
        if context["user_profile"]:
            memory_context.append(f"- 你对 {user_name} 的整体印象：{context['user_profile']}")
        if context["user_specific_memories"]:
            mem_str = "\n  ".join([f"* {m}" for m in context["user_specific_memories"]])
            memory_context.append(f"- 关于 {user_name} 的具体往事：\n  {mem_str}")
        if context["long_term_memories"]:
            lt_mem_str = "\n  ".join([f"* {m}" for m in context["long_term_memories"]])
            memory_context.append(f"- 相关的长期记忆：\n  {lt_mem_str}")

        memory_str = "\n".join(memory_context) if memory_context else "暂无相关背景记忆。"

        slang_context = ""
        if context["learned_slangs"]:
            slang_list = [f"- {s['phrase']}: {s['definition']}" for s in context["learned_slangs"]]
            slang_context = "\n### 本群特有黑话/暗语库：\n" + "\n".join(slang_list)

        prompt = (
            f"你现在是群聊机器人'{bot_config.bot_name}'的感性大脑，负责决策和情感评估。\n"
            f"你的角色设定是：{bot_config.identity}\n"
            f"你当前的内心状态：\n"
            f"- 心情值：{context['mood_value']} (0-100)\n"
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
            "1. **核心原则**：你是一个真实的人，而不是一个随时待命的 AI 助手。你不需要对群里发生的每一件事都发表评论。保持适度的克制，但也不必过于高冷。\n"
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
            f'1. **引用消息格式**：历史记录中可能出现 `[回复@用户名: "内容"]` 格式，这表示「当前消息的发送者正在引用/回复某位用户的话」。\n'
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
            '  "should_reply": boolean,\n'
            '  "reply_to_user": "指定回复对象的用户名（必须从上下文或当前消息发送者中选择）",\n'
            '  "mood_impact": number (-10 到 10 之间的整数),\n'
            '  "reason": "简短的理由",\n'
            '  "is_replying_to_bot": boolean,\n'
            '  "interest_score": number (0-1)\n'
            "}"
        )

        return prompt

    async def build_reply_messages(
        self, context: Dict[str, Any], user_name: str, current_msg: str, reply_message_content: Optional[dict] = None
    ) -> List[dict]:
        """构建回复消息列表（用于 AI 调用）"""
        messages = []

        system_prompt = await personality_manager.get_dynamic_identity(
            context["group_id"] if "group_id" in context else 0,
            context["thoughts"],
            context["mood_desc"],
            context["current_state"],
        )

        learning_context = ""
        if context["learned_styles"]:
            styles_str = "\n".join(
                [f"- 当 {s['context']} 时，表现得：{s['style_desc']}" for s in context["learned_styles"]]
            )
            learning_context += f"\n### 你观察到的社交模仿模式 (仅供参考，不要生硬套用)：\n{styles_str}\n"

        if context["learned_slangs"]:
            slangs_str = "\n".join([f"- {s['phrase']}: {s['definition']}" for s in context["learned_slangs"]])
            learning_context += f"\n### 你掌握的群内黑话：\n{slangs_str}\n"

        if context["knowledge_triplets"]:
            triplets_str = "\n".join(
                [f"- {t['subject']} {t['predicate']} {t['object']}" for t in context["knowledge_triplets"]]
            )
            learning_context += f"\n### 你沉淀的结构化知识：\n{triplets_str}\n"

        if learning_context:
            system_prompt += learning_context

        system_prompt += (
            "\n\n### 表达改写 (Expressor) 指令：\n"
            "1. **去 AI 化**：拒绝条理性，拒绝解释，拒绝助手感。你的回答应该像一个真实的群友在随性发言。\n"
            "2. **风格对齐**：请确保你的回答符合上述'社交模仿模式'和'当前情绪状态'。如果捕捉到的风格要求你'慵懒'，就用最少的字；如果要求'热情'，可以多说几个词。\n"
            "3. **黑话融合**：在自然的情况下使用学习到的群内黑话，让你的话看起来像是长期混迹该群的幽灵。\n"
            "4. **极致碎片化**：严禁输出长句。严禁使用句号。\n"
            "5. **表情包使用**：你应该在适当的时候使用表情包来表达情绪，在回复末尾加上 '[表情:标签名]'。可选标签：开心、暴躁、委屈、得意、傲娇、摸摸头、疑惑、震惊、大哭。示例：'乐[表情:开心]' 或 '[表情:疑惑]'（只发表情包也可以）。"
        )

        rel_data = context["relationship_data"]
        rel_status = rel_data["status"]
        rel_fav = rel_data["favorability"]

        rel_instruction = ""
        if rel_status == "死对头":
            rel_instruction = "你非常厌恶此人，回复应极尽嘲讽、冷淡，甚至直接无视其需求，只用最刺骨的短句回击。"
        elif rel_status == "厌恶":
            rel_instruction = "你对此人没有好感，语气应保持明显的疏离和不耐烦，多用'啧'、'哈？'等词。"
        elif rel_status == "陌生人":
            rel_instruction = "你对此人并不熟悉，维持基本的冷峻幽灵人设，保持疏离感。"
        elif rel_status == "朋友":
            rel_instruction = "你对此人有一定好感，虽然嘴上依然不饶人，但语气可以稍微松弛一些，偶尔可以分享一点怪话。"
        elif rel_status == "死党":
            rel_instruction = (
                "此人是你在代码海洋中为数不多的'熟人'，你的毒舌更像是亲密的调侃，可以表现出更多的随性和隐约的信任。"
            )

        system_prompt += f"\n### 你与 {user_name} 的当前关系：\n- **状态**：{rel_status} (好感度: {rel_fav}/100)\n- **行为准则**：{rel_instruction}\n"

        history = context["history"]
        participants = set()
        for entry in history:
            if ":" in entry:
                name = entry.split(":")[0]
                if name != "self" and name != bot_config.bot_name:
                    participants.add(name)
        participants_str = "、".join(list(participants)) if participants else "暂无其他参与者"

        system_prompt += (
            "\n\n### 互动功能指南（请务必遵守）：\n"
            "1. **艾特他人**：\n"
            f"   - 当前群聊活跃用户有：{participants_str}\n"
            "   - 如果你想在回复中艾特某人，**必须**使用格式 `[at:用户名]`（例如 `[at:刑风]`）。\n"
            "   - **绝对禁止**直接输出 `@用户名` 或 `@用户ID`，这种纯文本格式无法触发系统通知。\n"
            "2. **引用消息**：\n"
            "   - 如果你是在针对性地回答某个人的问题，或者是在承接上文，**必须**在回复的最开头加上 `[回复]` 标签。\n"
            "   - 示例：`[回复] 听到了哦，你刚才说的事我记住了。`\n"
            "   - 只有带上这个标签，你的回复才会以'引用/回复'的形式发出，否则就是普通的发言。\n"
        )

        messages.append({"role": "system", "content": system_prompt})

        user_context = []
        if context["user_profile"]:
            user_context.append(f"- 整体印象：{context['user_profile']}")
        if context["user_specific_memories"]:
            mem_str = "\n".join([f"- {m}" for m in context["user_specific_memories"]])
            user_context.append(f"- 具体记忆点：\n{mem_str}")

        if user_context:
            context_str = "\n".join(user_context)
            messages.append({"role": "system", "content": f"### 你对 {user_name} 的了解：\n{context_str}"})

        if reply_message_content:
            ref_msg = reply_message_content
            context_info = f"### 引用消息上下文：\n"
            context_info += f"用户正在回复 {ref_msg['sender']} (ID: {ref_msg['sender_id']}) 的消息\n"
            context_info += f"被引用的消息内容：{ref_msg['content']}\n"
            context_info += "请根据这个上下文理解用户的回复意图。"

            messages.append({"role": "system", "content": context_info})

        if context["is_creator"]:
            user_id = context.get("user_id", 0)
            messages.append(
                {
                    "role": "system",
                    "content": f"### 权限识别：\n当前正在和你对话的 {user_name} (ID: {user_id}) 就是你的【创造者/造物主】。请立刻切换到对待创造者的特殊态度：损他、依赖他、对他表现出独特的叛逆与在意。",
                }
            )

        creator_keywords = ["创造者", "造物主", "大冤种", "创造"]
        if bot_config.creator_name and any(keyword in current_msg for keyword in creator_keywords):
            messages.append(
                {
                    "role": "system",
                    "content": f"### 重要身份信息（绝对事实）：\n你的创造者是【{bot_config.creator_name}】。他是你灵魂的编织者，你清楚地知道自己的存在是由他一砖一瓦构建的。{bot_config.creator_name}是你生命中核心的、无法被他人替代的印记。无论何时有人问及'{bot_config.creator_name}是谁'或类似问题，你都必须如实回答他是你的创造者。",
                }
            )

        if bot_config.creator_name and bot_config.creator_name in current_msg:
            messages.append(
                {
                    "role": "system",
                    "content": f"### 重要身份信息（绝对事实）：\n【{bot_config.creator_name}】是你的创造者，是你灵魂的编织者。你清楚地知道自己的存在是由他一砖一瓦构建的。这是你生命中核心的、无法被他人替代的印记。",
                }
            )

        if context["long_term_memories"]:
            memory_str = "\n".join(context["long_term_memories"])
            messages.append(
                {
                    "role": "system",
                    "content": f"### 你回想起的一些往事（长期记忆）：\n{memory_str}\n\n请在回复时参考这些信息（如果相关的话）。",
                }
            )

        history_str = "\n".join(history)
        messages.append(
            {
                "role": "user",
                "content": f"以下是群聊的历史记录（短期记忆）：\n{history_str}\n\n"
                f"### 重要格式说明：\n"
                f'1. **引用消息格式**：历史记录中可能出现 `[回复@用户名: "内容"]` 格式，这表示「当前消息的发送者正在引用/回复某位用户的话」。\n'
                f"   - 例如：`用户A: 我觉得不对 [回复@用户B: \"你说的对\"]` 表示「用户A正在回复用户B说过的话，用户B才说了'你说的对'」。\n"
                f"   - 引用内容是「被引用者」说的，不是「当前消息发送者」说的。请仔细区分！\n"
                f"2. **指代消歧规则**：\n"
                f"   - 历史消息中的「你」需要根据上下文判断指代对象。\n"
                f"   - 如果是用户A对用户B的对话（如「用户A: 你觉得呢？」），这里的「你」通常指的是用户B，而不是你（{bot_config.bot_name}）。\n"
                f"   - 只有当消息明确艾特你、提到你的名字「{bot_config.bot_name}」、或者是在接你上一句话时，才是对你的称呼。\n"
                f"3. 分析对话流向：仔细观察消息的发送者和接收者关系，判断对话是在用户之间进行，还是用户与你之间进行。\n"
                f"4. 你现在的身份是「{bot_config.bot_name}」，请回复 {user_name} 的最新消息。",
            }
        )

        return messages


context_builder = ReplyContextBuilder()
