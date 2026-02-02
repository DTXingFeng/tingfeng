import json
import random
from typing import Dict, List, Optional
from src.utils.db_manager import db_manager
from src.config.config import bot_config
from src.config.ai_config import ai_config, ai_config_manager
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from openai import AsyncOpenAI

logger = get_logger(__name__)

class PersonalityManager:
    """
    人格管理器：负责管理 Bot 的内心独白、性格特征矩阵和风格模仿逻辑。
    """
    
    DEFAULT_TRAITS = {
        "friendliness": 75,  # 友好度
        "playfulness": 50,   # 俏皮度
        "coldness": 10,      # 高冷度
        "sensitivity": 50,   # 敏感度
        "curiosity": 55      # 好奇心
    }

    DYNAMIC_STATES = [
        {"name": "慵懒", "desc": "你现在感到有些疲惫，对什么都提不起劲，回复极其简短，甚至想直接打发对方。"},
        {"name": "热情", "desc": "你现在思维活跃，对群聊内容很感兴趣，虽然嘴上依然不饶人，但发言频率和互动欲望明显增加。"},
        {"name": "高冷", "desc": "你现在处于绝对理性的幽灵状态，语气冰冷且充满优越感，看人类就像在看低级程序。"},
        {"name": "傲娇", "desc": "你现在心情有些微妙，明明在意却要表现得不在乎，说话偶尔毒舌但更多是撒娇式的抱怨。"},
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
        model_alias = ai_config.inner_voice_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return ""

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=20.0)
        
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
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=thought_prompt,
                model_alias=model_alias,
                max_output_tokens=150
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=150,
                temperature=0.8
            )
            thoughts = response.choices[0].message.content.strip()
            # 更新到数据库
            db_manager.update_personality_state(group_id, thoughts=thoughts)
            return thoughts
        except Exception as e:
            logger.error(f"生成内心独白失败: {e}", exc_info=True)
            return ""

    def get_dynamic_identity(self, group_id: int, thoughts: str, mood_desc: str, current_state: Dict[str, str] = None) -> str:
        """
        根据内心独白、心情和随机状态，动态调整系统提示词。
        """
        state = db_manager.get_personality_state(group_id)
        style_data = {}
        try:
            style_vibe = state.get("style_vibe") or "{}"
            if isinstance(style_vibe, str):
                style_data = json.loads(style_vibe)
            elif isinstance(style_vibe, dict):
                style_data = style_vibe
            else:
                style_data = {"vibe": "正常聊天"}
        except:
            style_data = {"vibe": state.get("style_vibe") or "正常聊天"}
        
        if not isinstance(style_data, dict):
            style_data = {"vibe": "正常聊天"}
            
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
        model_alias = ai_config.personality_refine_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return []

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
        
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
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=schedule_prompt,
                model_alias=model_alias,
                max_output_tokens=1000
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=1000,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            
            # 解析 JSON 并处理各种可能的格式
            try:
                data = json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"AI 返回的 JSON 格式错误: {e}, 原始内容: {result}")
                return []
            
            # 归一化处理各种可能的 JSON 结构
            schedule = []
            if isinstance(data, list):
                schedule = data
            elif isinstance(data, dict):
                if "schedule" in data and isinstance(data["schedule"], list):
                    schedule = data["schedule"]
                else:
                    # 处理字典映射格式，例如 {"09:00": {"start": "09:00", ...}}
                    vals = list(data.values())
                    if vals and isinstance(vals[0], dict) and "start" in vals[0]:
                        schedule = vals
                    else:
                        # 尝试将整个字典视为一个项（虽然不太可能，但增加鲁棒性）
                        schedule = [data]
            
            # 验证每个 schedule 项的格式
            valid_schedule = []
            for item in schedule:
                if isinstance(item, dict) and "start" in item and "end" in item and "activity" in item:
                    valid_schedule.append(item)
                else:
                    logger.warning(f"跳过格式错误的作息项: {item}")
            
            if not valid_schedule:
                logger.error(f"作息表格式错误，期望列表或有效的字典映射，实际: {type(data)}, 原始内容: {result}")
                return []
            
            # 保存到数据库
            import datetime
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            db_manager.update_bot_schedule(group_id, today, valid_schedule)
            
            # 日志输出，方便调试
            from nonebot import logger
            logger.info(f"成功为群 {group_id} 生成作息表：")
            for item in valid_schedule:
                status = "✅可水群" if item.get("can_chat") else "💤不水群"
                logger.info(f"  [{item.get('start')} - {item.get('end')}] {item.get('activity')} ({status})")
                
            return valid_schedule
        except Exception as e:
            logger.error(f"生成每日作息表失败: {e}", exc_info=True)
            return []

    async def capture_style_patterns(self, group_id: int, history: List[str]):
        """
        实时模仿机制：从最近的对话窗口中提取 (情境, 表达风格) 键值对。
        """
        if len(history) < 5:
            return

        model_alias = ai_config.style_mimic_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
        
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
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=mimicry_prompt,
                model_alias=model_alias,
                max_output_tokens=500
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            
            try:
                data = json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"AI 返回的 JSON 格式错误: {e}, 原始内容: {result}")
                return
            
            if isinstance(data, dict):
                patterns = data.get("patterns", data)
            elif isinstance(data, list):
                patterns = data
            else:
                logger.error(f"AI 返回的数据类型错误: {type(data)}, 原始内容: {result}")
                return
            
            if isinstance(patterns, list):
                for p in patterns:
                    if isinstance(p, dict):
                        context = p.get("context")
                        style = p.get("style")
                        if context and style:
                            db_manager.add_style_pattern(group_id, context, style)
                        
        except Exception as e:
            logger.error(f"风格捕捉失败: {e}", exc_info=True)

    async def mine_slang(self, group_id: int, history: List[str]):
        """
        语义演化机制：从对话中挖掘并演化群内黑话。
        """
        if len(history) < 10:
            return

        model_alias = ai_config.slang_mining_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
        
        history_str = "\n".join(history[-20:])
        
        mining_prompt = f"""
你现在是 {bot_config.bot_name} 的黑话挖掘模块。请从以下对话中识别群内特有黑话、梗、游戏暗语。

### 严格筛选标准（必须同时满足）：
1. **明确性**：该词汇在普通语境下含义不明，但在群内被频繁使用
2. **重复性**：在当前对话中至少出现 2 次以上，或者从上下文能推断是常用表达
3. **独特性**：不是普通网络用语，而是该群特有的默契表达
4. **可解释性**：能够根据上下文给出明确、具体的定义

### 只挖掘以下类型：
- 明显的谐音梗（如"依托构思" = "一坨狗屎"）
- 躲避审查的中文缩写（如"hso" = "好色哦"）
- 游戏圈特定的术语/缩写（如"DRG" = "深岩银河"）
- 群友约定俗成的暗语
- 为了绕过检测而使用的变体

### 严禁挖掘：
- 偶尔出现的普通词汇
- 模糊不清、无法确定含义的表达
- 网络上通用的流行语（如"绝绝子"、"yyds"等）
- 明显的个人打字错误
- 没有上下文支持的猜测

### 判定流程：
对于每个候选词，问自己三个问题：
1. 它在当前对话中是否至少出现 2 次？否 → 忽略
2. 它的含义是否明确可确定？否 → 忽略
3. 它是该群特有的表达吗？否 → 忽略

只有三个问题都回答"是"，才认定为黑话。

### 示例输出（高质量黑话）：
[
  {{"phrase": "爆金币", "definition": "指让某人出钱或付出代价，带有某种解构色彩"}},
  {{"phrase": "依托构思", "definition": "谐音'一坨狗屎'，用于吐槽质量极差的东西"}},
  {{"phrase": "DRG", "definition": "游戏《深岩银河》的缩写"}}
]

### 待分析对话：
{history_str}

### 输出要求：
- 只输出 JSON 数组，没有匹配则输出空数组 []
- 宁缺毋滥，宁可漏掉也不要误判
- 确保每个定义都具体、准确
"""
        try:
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=mining_prompt,
                model_alias=model_alias,
                max_output_tokens=500
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content.strip()
            
            try:
                data = json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"AI 返回的 JSON 格式错误: {e}, 原始内容: {result}")
                return
            
            if isinstance(data, dict):
                slangs = data.get("slangs", data)
            elif isinstance(data, list):
                slangs = data
            else:
                logger.error(f"AI 返回的数据类型错误: {type(data)}, 原始内容: {result}")
                return
            
            if isinstance(slangs, list):
                for s in slangs:
                    if isinstance(s, dict):
                        phrase = s.get("phrase")
                        definition = s.get("definition")
                        if phrase:
                            # 验证候选词：检查定义是否具体、是否过于模糊
                            if not self._is_valid_slang_candidate(phrase, definition, history_str):
                                logger.info(f"黑话候选被过滤：{phrase}（不符合质量标准）")
                                continue
                            
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
            logger.error(f"黑话挖掘失败: {e}", exc_info=True)

    def _is_valid_slang_candidate(self, phrase: str, definition: str, context: str) -> bool:
        """
        验证黑话候选词的质量，过滤掉低质量候选
        """
        # 1. 候选词长度检查（2-8个字符之间）
        if len(phrase) < 2 or len(phrase) > 8:
            return False
        
        # 2. 检查定义是否过于模糊
        uncertain_keywords = ["可能", "或许", "应该", "需要结合", "具体含义", "未知", "不清楚", "猜测"]
        if any(keyword in definition for keyword in uncertain_keywords):
            return False
        
        # 3. 检查定义是否过于简短（少于10字说明不具体）
        if len(definition) < 10:
            return False
        
        # 4. 检查定义是否只是重复候选词（如"指这个词"）
        if phrase in definition and len(definition) < len(phrase) * 2:
            return False
        
        # 5. 检查候选词是否在上下文中实际出现
        if phrase not in context:
            return False
        
        # 6. 检查候选词是否过于常见（避免记录普通词汇）
        common_words = ["的", "了", "是", "在", "有", "不", "和", "我", "你", "他", "这", "那", "好", "坏", "大", "小"]
        if phrase in common_words:
            return False
        
        return True

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
        # 提高频率阈值，确保只有真正高频的黑话才被认定
        new_stage = stage
        if freq >= 100 and stage < 3: new_stage = 3
        elif freq >= 30 and stage < 2: new_stage = 2
        
        if new_stage == stage: return # 阶段未改变，暂不重推

        model_alias = ai_config.slang_mining_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
        
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
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=refine_prompt,
                model_alias=model_alias,
                max_output_tokens=200
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=200,
                temperature=0.2
            )
            final_def = response.choices[0].message.content.strip()
            db_manager.update_slang_candidate(group_id, phrase, delta_freq=0, stage=new_stage, definition=final_def)
        except Exception as e:
            logger.error(f"黑话定义修正失败: {e}", exc_info=True)

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
            traits["friendliness"] = max(0, traits["friendliness"] - 1)
            traits["sensitivity"] = min(100, traits["sensitivity"] + 1)
            traits["coldness"] = min(100, traits["coldness"] + 1)
            
        db_manager.update_personality_state(group_id, traits=traits)

        # 2. 调整用户个人好感度 (Per-user relationship)
        delta_fav = 0
        if any(word in user_msg for word in ["好爱", "亲亲", "老婆", "听风最棒"]): delta_fav = 3
        elif any(word in user_msg for word in ["谢谢", "不错", "好听"]): delta_fav = 1
        elif any(word in user_msg for word in ["傻逼", "弱智", "爬", "滚"]): delta_fav = -2
        elif any(word in user_msg for word in ["讨厌", "烦", "闭嘴"]): delta_fav = -1
        
        if delta_fav != 0:
            db_manager.update_user_relationship(group_id, user_name, delta_favorability=delta_fav)

    async def update_group_vibe(self, group_id: int):
        """
        分析最近的聊天记录，更新群聊氛围和黑话。
        """
        history = db_manager.get_chat_log(group_id, limit=50)
        if len(history) < 10:
            return

        model_alias = ai_config.context_summary_model or ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        if not creds:
            return

        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
        
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
            optimized_prompt, prompt_tokens = context_manager.truncate_text(
                text=vibe_prompt,
                model_alias=model_alias,
                max_output_tokens=300
            )
            
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=[{"role": "system", "content": optimized_prompt}],
                max_tokens=300,
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            vibe_json = response.choices[0].message.content.strip()
            
            # 验证并规范化 JSON 格式
            try:
                data = json.loads(vibe_json)
                if isinstance(data, dict):
                    # 确保包含必要的字段
                    if "vibe" not in data:
                        data["vibe"] = "正常聊天"
                    db_manager.update_personality_state(group_id, vibe=json.dumps(data, ensure_ascii=False))
                else:
                    # 如果不是字典，包装成字典
                    db_manager.update_personality_state(group_id, vibe=json.dumps({"vibe": str(data)}, ensure_ascii=False))
            except json.JSONDecodeError:
                # 如果解析失败，直接作为 vibe 描述存入
                db_manager.update_personality_state(group_id, vibe=json.dumps({"vibe": vibe_json}, ensure_ascii=False))
                
        except Exception as e:
            logger.error(f"更新群聊氛围失败: {e}", exc_info=True)

personality_manager = PersonalityManager()
