import json
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

    def get_dynamic_identity(self, group_id: int, thoughts: str, mood_desc: str) -> str:
        """
        根据内心独白和心情，动态调整系统提示词。
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
        
        dynamic_prompt = f"""
{bot_config.prompt}

### 此时此刻的你（动态状态）：
- **当前心情**：{mood_desc}
- **内心独白**（仅供参考，严禁在回复中直接输出）：{thoughts}
- **群聊氛围感**：{vibe}

### 本群语言特征（请参考）：
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

    async def evolve_personality(self, group_id: int, user_name: str, user_msg: str, bot_reply: str):
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
