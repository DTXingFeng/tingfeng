import json
import random
from typing import Dict, List, Optional
from src.utils.db_manager import db_manager
from src.config.config import bot_config
from src.config.ai_config import ai_config, ai_config_manager
from openai import AsyncOpenAI

class PersonalityManager:
    """
    人格管理器：负责管理 Bot 的内心独白、性格特征矩阵和风格模仿逻辑。
    """
    
    DEFAULT_TRAITS = {
        "friendliness": 60,  # 友好度
        "playfulness": 40,   # 俏皮度
        "coldness": 20,      # 高冷度
        "sensitivity": 70,   # 敏感度
        "curiosity": 50      # 好奇心
    }

    DYNAMIC_STATES = [
        {"name": "慵懒", "desc": "你现在感到有些疲惫，对什么都提不起劲，回复极其简短，甚至想直接打发对方。"},
        {"name": "热情", "desc": "你现在思维活跃，对群聊内容很感兴趣，虽然嘴上依然不饶人，但发言频率和互动欲望明显增加。"},
        {"name": "高冷", "desc": "你现在处于绝对理性的幽灵状态，语气冰冷且充满优越感，看人类就像在看低级程序。"},
        {"name": "傲娇", "desc": "你现在心情有些微妙，明明在意却要表现出不在乎，说话口是心非，带有一点攻击性但并不致命。"},
        {"name": "混乱", "desc": "你的逻辑核心出现轻微溢出，说话更加跳跃、无厘头，经常说一些让人摸不着头脑的怪话。"}
    ]

    def get_random_state(self) -> Dict[str, str]:
        """随机抽取一种动态状态"""
        return random.choice(self.DYNAMIC_STATES)

    @staticmethod
    def get_mood_color(mood_value: int) -> str:
        if mood_value <= 20: return "灰暗/压抑"
        if mood_value <= 40: return "忧郁/淡漠"
        if mood_value <= 60: return "平和/自然"
        if mood_value <= 80: return "明亮/轻快"
        return "炽热/狂喜"

    async def generate_thoughts(self, group_id: int, user_name: str, current_msg: str, history: List[str], mood_value: int) -> str:
        """
        生成内心独白：在正式回复前，思考当前境况。
        """
        state = db_manager.get_personality_state(group_id)
        traits = state.get("traits") or self.DEFAULT_TRAITS
        vibe = state.get("style_vibe") or "正常聊天"
        
        # 准备思考用的 Prompt
        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return ""

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        history_context = "\n".join(history[-5:]) # 只取最近5条参考
        mood_color = self.get_mood_color(mood_value)
        
        thought_prompt = f"""
你现在是 {bot_config.bot_name} 的“潜意识”。在回复用户之前，请进行一次简短的内心独白。
你的性格基调：{bot_config.identity}
当前心情：{mood_value}/100 ({mood_color})
当前性格倾向：{json.dumps(traits, ensure_ascii=False)}
当前群聊氛围感：{vibe}

最近对话记录：
{history_context}

当前 {user_name} 对你说："{current_msg}"

请思考并输出你的内心独白（50字以内），包含以下内容：
1. 你对这句话的第一反应是什么？
2. 你现在的真实情绪状态。
3. 你打算以什么样的“面具”或语气来面对这次对话？

注意：直接输出独白内容，不要包含任何格式标签，不要直接对用户说话。
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": thought_prompt}],
                max_tokens=150,
                temperature=0.8
            )
            thoughts = response.choices[0].message.content.strip()
            # 更新到数据库
            db_manager.update_personality_state(group_id, thoughts=thoughts)
            return thoughts
        except Exception as e:
            print(f"生成内心独白失败: {e}")
            return ""

    def get_dynamic_identity(self, group_id: int, thoughts: str, mood_desc: str, current_state: Dict[str, str] = None) -> str:
        """
        根据内心独白、心情和随机状态，动态调整系统提示词。
        """
        state = db_manager.get_personality_state(group_id)
        style_data = {}
        try:
            style_data = json.loads(state.get("style_vibe") or "{}")
        except:
            style_data = {"vibe": state.get("style_vibe") or "正常聊天"}
            
        vibe = style_data.get("vibe", "正常聊天")
        slang = style_data.get("slang", [])
        patterns = style_data.get("sentence_patterns", [])
        
        slang_str = "、".join(slang) if slang else "暂无"
        patterns_str = "、".join(patterns) if patterns else "暂无"
        
        state_str = f"- **当前情绪状态**：{current_state['name']} ({current_state['desc']})" if current_state else ""

        dynamic_prompt = f"""
{bot_config.prompt}

### 此时此刻的你 (动态状态)：
- **当前心情**：{mood_desc}
{state_str}
- **内心独白**（仅供参考，严禁在回复中直接输出）：{thoughts}
- **群聊氛围感**：{vibe}

### 本群语言特征 (请参考)：
- **本群流行黑话/关键词**：{slang_str}
- **本群常用口癖/句式**：{patterns_str}
"""
        return dynamic_prompt

    async def generate_daily_schedule(self, group_id: int) -> List[Dict]:
        """
        AI 为 Bot 生成今日作息表。
        """
        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return []

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        schedule_prompt = f"""
你现在是 {bot_config.bot_name} 的时间管理模块。请根据以下人格设定，为她生成一份今日的“极致碎片化作息表”。
人格设定：{bot_config.identity}

### 任务要求：
1. 请规划出 8-12 个不同的时间段。
2. **水群时间必须极其碎片化**：每个“水群/聊天”时间段（can_chat: true）的持续时间**严禁超过 30 分钟**（建议 15-20 分钟）。
3. 两个“水群”时间段之间，必须穿插至少 1 小时的“非水群”时间（如：核心维护、数据整理、沉睡、宕机、潜水）。
4. 确保全天总的水群频率较高，但每次都很短促。
5. 请直接输出 JSON 列表格式，严禁包含任何其他文字。

### JSON 格式示例：
[
  {{"start": "09:00", "end": "09:20", "activity": "清晨冒泡", "can_chat": true}},
  {{"start": "09:20", "end": "11:00", "activity": "数据整理", "can_chat": false}},
  {{"start": "12:15", "end": "12:35", "activity": "午间闲聊", "can_chat": true}}
]
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": schedule_prompt}],
                max_tokens=1000,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            # 兼容性处理：有的模型可能返回 {"schedule": [...]}
            data = json.loads(result)
            schedule = data.get("schedule", data) if isinstance(data, dict) else data
            
            # 保存到数据库
            import datetime
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            db_manager.update_bot_schedule(group_id, today, schedule)
            
            # 日志输出，方便调试
            from nonebot import logger
            logger.info(f"成功为群 {group_id} 生成作息表：")
            for item in schedule:
                status = "✅可水群" if item.get("can_chat") else "💤不水群"
                logger.info(f"  [{item.get('start')} - {item.get('end')}] {item.get('activity')} ({status})")
                
            return schedule
        except Exception as e:
            print(f"生成每日作息表失败: {e}")
            return []

    async def capture_style_patterns(self, group_id: int, history: List[str]):
        """
        实时模仿机制：从最近的对话窗口中提取 (情境, 表达风格) 键值对。
        """
        if len(history) < 5:
            return

        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        history_str = "\n".join(history[-20:]) # 采样最近 20 条
        
        mimicry_prompt = f"""
你现在是 {bot_config.bot_name} 的风格捕捉模块。请分析以下群聊片段，识别其中用户表现出的独特表达风格。

### 任务要求：
1. 识别对话中的“特定情境”以及在该情境下用户展现出的“表达风格/语言模式”。
2. 忽略通用的表达，寻找具有社群特色的、有趣的或高频出现的模式。
3. 请输出 JSON 列表格式，每个对象包含 "context"（情境）和 "style"（风格描述）。

### 示例输出：
[
  {{"context": "被夸奖", "style": "表现得极其害羞，使用‘捏’、‘的说’作为结尾"}},
  {{"context": "讨论二次元", "style": "使用大量的抽象黑话，语气显得很‘赢’"}}
]

### 待分析对话：
{history_str}
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": mimicry_prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            data = json.loads(result)
            patterns = data.get("patterns", data) if isinstance(data, dict) else data
            
            if isinstance(patterns, list):
                for p in patterns:
                    context = p.get("context")
                    style = p.get("style")
                    if context and style:
                        db_manager.add_style_pattern(group_id, context, style)
                        
        except Exception as e:
            print(f"风格捕捉失败: {e}")

    async def mine_slang(self, group_id: int, history: List[str]):
        """
        语义演化机制：从对话中挖掘并演化群内黑话。
        """
        if len(history) < 5:
            return

        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        history_str = "\n".join(history[-20:])
        
        mining_prompt = f"""
你现在是 {bot_config.bot_name} 的黑话挖掘模块。请识别以下对话中出现的群内特有黑话、梗、游戏暗语或为了绕过敏感词检测而使用的谐音/缩写。

### 任务要求：
1. **深度解码**：寻找那些在普通语境下含义不明，但在该群聊中被频繁使用的词汇。
2. **重点关注**：
   - **谐音/变体**：例如为了绕过检测而使用的拼音缩写、同音异形词。
   - **游戏黑话**：特定游戏的术语或梗。
   - **抽象表达**：群友之间形成的独特默契用语。
3. 为每个词汇提供基于上下文的真实定义。
4. 请输出 JSON 列表格式。

### 示例输出：
[
  {{"phrase": "爆金币", "definition": "指让某人出钱或付出代价，带有某种解构色彩"}},
  {{"phrase": "依托构思", "definition": "谐音‘一坨狗屎’，用于吐槽质量极差的东西"}}
]

### 待分析对话：
{history_str}
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": mining_prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            data = json.loads(result)
            slangs = data.get("slangs", data) if isinstance(data, dict) else data
            
            if isinstance(slangs, list):
                for s in slangs:
                    phrase = s.get("phrase")
                    definition = s.get("definition")
                    if phrase:
                        # 记录并更新频率，同时附带当前上下文样本
                        db_manager.update_slang_candidate(
                            group_id, 
                            phrase, 
                            delta_freq=1, 
                            definition=definition,
                            context_samples=[history_str]
                        )
                        
                        # 触发差分推理 (检查频率阈值)
                        await self._refine_slang_definition(group_id, phrase)
                        
        except Exception as e:
            print(f"黑话挖掘失败: {e}")

    async def _refine_slang_definition(self, group_id: int, phrase: str):
        """
        多轮差分推理：根据积累的上下文样本，修正黑话定义。
        """
        candidates = db_manager.get_slang_candidates(group_id)
        candidate = next((c for c in candidates if c["phrase"] == phrase), None)
        if not candidate: return

        freq = candidate["frequency"]
        stage = candidate["stage"]
        
        # 判定是否需要升级阶段
        new_stage = stage
        if freq >= 60 and stage < 3: new_stage = 3
        elif freq >= 10 and stage < 2: new_stage = 2
        
        if new_stage == stage: return # 阶段未改变，暂不重推

        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        samples_str = "\n---\n".join(candidate["context_samples"])
        
        refine_prompt = f"""
你现在是 {bot_config.bot_name} 的黑话判定专家。
我们需要对黑话词汇 "{phrase}" 进行深度定义。

### 现有推测定义：
{candidate["definition"]}

### 收集到的真实上下文样本：
{samples_str}

### 任务：
请根据以上真实样本，修正并固化该黑话的定义。要求精准、简练，并指出其背后的情感色彩或社群文化背景。
直接输出最终定义，不要包含其他文字。
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": refine_prompt}],
                max_tokens=200,
                temperature=0.2
            )
            final_def = response.choices[0].message.content.strip()
            db_manager.update_slang_candidate(group_id, phrase, delta_freq=0, stage=new_stage, definition=final_def)
        except Exception as e:
            print(f"黑话定义修正失败: {e}")

    async def evolve_personality(self, group_id: int, user_name: str, user_msg: str, bot_reply: str = None):
        """
        根据交互进化性格特征值和用户关系。
        """
        state = db_manager.get_personality_state(group_id)
        traits = state.get("traits") or self.DEFAULT_TRAITS.copy()
        
        # 1. 调整群组性格矩阵 (Group-wide traits)
        if any(word in user_msg for word in ["谢谢", "喜欢", "可爱", "好厉害"]):
            traits["friendliness"] = min(100, traits["friendliness"] + 2)
            traits["coldness"] = max(0, traits["coldness"] - 1)
        if any(word in user_msg for word in ["讨厌", "笨", "傻", "爬", "垃圾"]):
            traits["friendliness"] = max(0, traits["friendliness"] - 3)
            traits["sensitivity"] = min(100, traits["sensitivity"] + 2)
            traits["coldness"] = min(100, traits["coldness"] + 2)
            
        db_manager.update_personality_state(group_id, traits=traits)

        # 2. 调整用户个人好感度 (Per-user relationship)
        delta_fav = 0
        if any(word in user_msg for word in ["好爱", "亲亲", "老婆", "听风最棒"]): delta_fav = 3
        elif any(word in user_msg for word in ["谢谢", "不错", "好听"]): delta_fav = 1
        elif any(word in user_msg for word in ["傻逼", "弱智", "爬", "滚"]): delta_fav = -5
        elif any(word in user_msg for word in ["讨厌", "烦", "闭嘴"]): delta_fav = -2
        
        if delta_fav != 0:
            db_manager.update_user_relationship(group_id, user_name, delta_favorability=delta_fav)

    async def update_group_vibe(self, group_id: int):
        """
        分析最近的聊天记录，更新群聊氛围和黑话。
        """
        history = db_manager.get_chat_log(group_id, limit=50)
        if len(history) < 10:
            return

        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        
        history_str = "\n".join(history)
        
        vibe_prompt = f"""
你是一个语言分析专家。请分析以下群聊记录，提取该群聊目前的“氛围感”、“高频关键词/黑话”以及“特有的句式/口癖”。

聊天记录：
{history_str}

请输出一个 JSON 对象，包含以下字段：
- "vibe": 简短的氛围描述（20字以内）。
- "slang": 字符串列表，包含 3-5 个本群高频使用的黑话或梗。
- "sentence_patterns": 字符串列表，包含 2-3 个本群常用的句式、语气词或口癖（例如 "捏"、"的说"、"呜呜"）。

示例输出：
{{
  "vibe": "二次元氛围，轻松愉快",
  "slang": ["小丑", "典", "赢"],
  "sentence_patterns": ["捏", "的说"]
}}

请直接输出 JSON，不要包含其他解释性文字。
"""
        try:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": vibe_prompt}],
                max_tokens=300,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            vibe_json = response.choices[0].message.content.strip()
            db_manager.update_personality_state(group_id, vibe=vibe_json)
        except Exception as e:
            print(f"更新群聊氛围失败: {e}")

personality_manager = PersonalityManager()
