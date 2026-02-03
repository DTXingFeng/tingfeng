from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.aimodel.reply.personality import personality_manager
from src.utils.context_manager import context_manager
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
from src.mcp.registry import tool_registry
from typing import List, Optional, Dict, Any
import random
import re
import asyncio
import json

logger = get_logger(__name__)

def get_mood_description(mood_value: int) -> str:
    """将数值心情映射为文字描述"""
    if mood_value <= 10:
        return "彻底破防 (你受到了极大的侮辱，现在你完全化身为犀利的贴吧老哥。对于恶意攻击者，你要毫不留情地反击，使用最辛辣的讽刺。)"
    elif mood_value <= 25:
        return "极度不悦 (你现在心情很糟，说话带刺，容易产生误会，对人比较冷淡。)"
    elif mood_value <= 40:
        return "有些忧郁 (语气低沉，兴致不高，不太想说话。)"
    elif mood_value <= 60:
        return "平静自然 (正常的交流风格，随性、自然。)"
    elif mood_value <= 80:
        return "开心活泼 (心情不错，愿意和大家分享趣事。)"
    else:
        return "兴奋狂喜 (非常热情，充满了元气。)"

async def get_chat_reply(group_id: int, user_name: str, current_msg: str, user_id: Optional[int] = None, reply_message_id: Optional[int] = None, bot = None) -> Dict[str, any]:
    """
    获取 AI 回复逻辑
    返回格式: {"text": str, "sticker": Optional[str]}
    """
    # 如果有引用消息 ID，尝试获取引用内容
    reply_message_content = None
    if reply_message_id and bot:
        try:
            from nonebot.adapters.onebot.v11 import Message as OneBotMessage
            
            # 使用 bot API 获取历史消息
            msg_data = await bot.get_msg(message_id=reply_message_id)
            
            if msg_data:
                # 解析消息数据
                sender_id = msg_data.get("user_id")
                sender_name = msg_data.get("sender_name", f"用户{sender_id}")
                msg_text = msg_data.get("message", "")
                
                # 如果消息是段格式，转换为文本
                if isinstance(msg_text, list):
                    text_parts = []
                    for seg in msg_text:
                        if seg.get("type") == "text":
                            text_parts.append(seg.get("data", {}).get("text", ""))
                        elif seg.get("type") == "at":
                            qq = seg.get("data", {}).get("qq", "")
                            text_parts.append(f"[@{qq}]")
                        elif seg.get("type") == "image":
                            text_parts.append("[图片]")
                        elif seg.get("type") == "face":
                            text_parts.append("[表情]")
                    msg_text = "".join(text_parts)
                
                reply_message_content = {
                    "sender": sender_name,
                    "sender_id": sender_id,
                    "content": msg_text,
                    "message_id": reply_message_id
                }
                
                logger.debug(f"获取到引用消息: {sender_name}: {msg_text[:50]}...")
        except Exception as e:
            logger.debug(f"获取引用消息失败: {e}")
    
    # 1. 获取配置
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"text": f"好像连不上网了，{bot_config.bot_name}现在有点懵... (扶额)", "sticker": None}

    # 1.5 判断是否为创造者
    is_creator = False
    if user_id and bot_config.creator_id and user_id == bot_config.creator_id:
        is_creator = True

    # 准备历史记录
    # 获取最近 20 条记录作为短期记忆
    history = db_manager.get_chat_log(group_id, limit=20)
    
    # 提取历史记录中的所有参与者名字，用于艾特功能
    participants = set()
    for entry in history:
        if ":" in entry:
            name = entry.split(":")[0]
            if name != "self" and name != bot_config.bot_name:
                participants.add(name)
    participants_str = "、".join(list(participants)) if participants else "暂无其他参与者"
    
    # 获取心情值
    mood_desc = ""
    if bot_config.enable_mood:
        mood_value = db_manager.get_mood(group_id)
        mood_desc = get_mood_description(mood_value)
    
    # 获取相关长期记忆 (RAG)
    long_term_memories = []
    
    # 获取用户画像和具体记忆（使用跨群查询）
    user_profile = db_manager.get_user_impression_cross_group(group_id, user_name)
    user_specific_memories = db_manager.get_user_specific_memories_cross_group(group_id, user_name, limit=5)
    
    # 获取关系状态（使用跨群查询）
    rel_data = db_manager.get_user_relationship_cross_group(group_id, user_name)
    rel_status = rel_data["status"]
    rel_fav = rel_data["favorability"]
    
    # 获取内心独白 (Thoughts)
    mood_value = db_manager.get_mood(group_id) if bot_config.enable_mood else 50
    thoughts = await personality_manager.generate_thoughts(group_id, user_name, current_msg, history, mood_value)
    
    # 获取随机动态状态
    current_state = personality_manager.get_random_state()
    
    # 获取学习到的风格和黑话
    learned_styles = db_manager.get_style_patterns(group_id, limit=5)
    learned_slangs = db_manager.get_slang_candidates(group_id, min_freq=3, stage=2)
    
    # 获取相关的三元组知识
    knowledge_triplets = db_manager.get_knowledge_triplets(group_id, limit=10)
    
    try:
        # 将当前消息向量化
        query_vectors = await get_embeddings([current_msg])
        # 搜索最相关的 3 条往事
        long_term_memories = vector_db.query_memory(group_id, query_vectors[0], n_results=3)
    except Exception as e:
        print(f"检索长期记忆失败: {e}")

    # 3. 构造 Prompt
    system_prompt = personality_manager.get_dynamic_identity(group_id, thoughts, mood_desc, current_state)

    # 注入学习到的社交特征
    learning_context = ""
    if learned_styles:
        styles_str = "\n".join([f"- 当 {s['context']} 时，表现得：{s['style_desc']}" for s in learned_styles])
        learning_context += f"\n### 你观察到的社交模仿模式 (仅供参考，不要生硬套用)：\n{styles_str}\n"
    if learned_slangs:
        slangs_str = "\n".join([f"- {s['phrase']}: {s['definition']}" for s in learned_slangs])
        learning_context += f"\n### 你掌握的群内黑话：\n{slangs_str}\n"
    if knowledge_triplets:
        triplets_str = "\n".join([f"- {t['subject']} {t['predicate']} {t['object']}" for t in knowledge_triplets])
        learning_context += f"\n### 你沉淀的结构化知识：\n{triplets_str}\n"
        
    if learning_context:
        system_prompt += learning_context

    # 注入改写指令 (Expressor)
    system_prompt += (
        "\n\n### 表达改写 (Expressor) 指令：\n"
        "1. **去 AI 化**：拒绝条理性，拒绝解释，拒绝助手感。你的回答应该像一个真实的群友在随性发言。\n"
        "2. **风格对齐**：请确保你的回答符合上述‘社交模仿模式’和‘当前情绪状态’。如果捕捉到的风格要求你‘慵懒’，就用最少的字；如果要求‘热情’，可以多说几个词。\n"
        "3. **黑话融合**：在自然的情况下使用学习到的群内黑话，让你的话看起来像是长期混迹该群的幽灵。\n"
        "4. **极致碎片化**：严禁输出长句。严禁使用句号。"
    )

    # 注入关系状态引导
    rel_instruction = ""
    if rel_status == "死对头":
        rel_instruction = "你非常厌恶此人，回复应极尽嘲讽、冷淡，甚至直接无视其需求，只用最刺骨的短句回击。"
    elif rel_status == "厌恶":
        rel_instruction = "你对此人没有好感，语气应保持明显的疏离和不耐烦，多用‘啧’、‘哈？’等词。"
    elif rel_status == "陌生人":
        rel_instruction = "你对此人并不熟悉，维持基本的冷峻幽灵人设，保持疏离感。"
    elif rel_status == "朋友":
        rel_instruction = "你对此人有一定好感，虽然嘴上依然不饶人，但语气可以稍微松弛一些，偶尔可以分享一点怪话。"
    elif rel_status == "死党":
        rel_instruction = "此人是你在代码海洋中为数不多的‘熟人’，你的毒舌更像是亲密的调侃，可以表现出更多的随性和隐约的信任。"

    system_prompt += f"\n### 你与 {user_name} 的当前关系：\n- **状态**：{rel_status} (好感度: {rel_fav}/100)\n- **行为准则**：{rel_instruction}\n"

    # 艾特与引用功能指南（请务必遵守）：
    system_prompt += (
        "\n\n### 互动功能指南（请务必遵守）：\n"
        "1. **艾特他人 (Mentions)**：\n"
        f"   - 当前群聊活跃用户有：{participants_str}\n"
        "   - 如果你想在回复中艾特某人，**必须**使用格式 `[at:用户名]`（例如 `[at:刑风]`）。\n"
        "   - **绝对禁止**直接输出 `@用户名` 或 `@用户ID`，这种纯文本格式无法触发系统通知。\n"
        "2. **引用消息 (Reply/Quote)**：\n"
        "   - 如果你是在针对性地回答某个人的问题，或者是在承接上文，**必须**在回复的最开头加上 `[回复]` 标签。\n"
        "   - 示例：`[回复] 听到了哦，你刚才说的事我记住了。`\n"
        "   - 只有带上这个标签，你的回复才会以‘引用/回复’的形式发出，否则就是普通的发言。\n"
    )

    # 引导 AI 使用表情包
    system_prompt += (
        "\n\n### 表情包使用指南：\n"
        "如果你觉得当前语境适合发送表情包，请在回复文本的最后加上 '[表情:标签名]'。\n"
        "可选标签：开心、大哭、暴躁、委屈、傲娇、得意、摸摸头、疑惑、震惊。\n"
        "例如：'哼，这种简单的题我也能解出来，看好了！[表情:得意]'"
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    # 注入用户画像与具体记忆
    user_context = []
    if user_profile:
        user_context.append(f"- 整体印象：{user_profile}")
    if user_specific_memories:
        mem_str = "\n".join([f"- {m}" for m in user_specific_memories])
        user_context.append(f"- 具体记忆点：\n{mem_str}")
    
    if user_context:
        context_str = "\n".join(user_context)
        messages.append({
            "role": "system",
            "content": f"### 你对 {user_name} 的了解：\n{context_str}"
        })
    
    # 如果有引用消息，注入上下文
    if reply_message_content:
        ref_msg = reply_message_content
        context_info = f"### 引用消息上下文：\n"
        context_info += f"用户正在回复 {ref_msg['sender']} (ID: {ref_msg['sender_id']}) 的消息\n"
        context_info += f"被引用的消息内容：{ref_msg['content']}\n"
        context_info += "请根据这个上下文理解用户的回复意图。"
        
        messages.append({
            "role": "system",
            "content": context_info
        })
  
    # 注入创造者身份识别
    if is_creator:
        messages.append({
            "role": "system",
            "content": f"### 权限识别：\n当前正在和你对话的 {user_name} (ID: {user_id}) 就是你的【创造者/造物主】。请立刻切换到对待创造者的特殊态度：损他、依赖他、对他表现出独特的叛逆与在意。"
        })
    
    # 如果有人问及创造者相关信息，直接注入配置的创造者信息
    creator_keywords = ["创造者", "造物主", "大冤种", "创造"]
    if bot_config.creator_name and any(keyword in current_msg for keyword in creator_keywords):
        messages.append({
            "role": "system",
            "content": f"### 重要身份信息（绝对事实）：\n你的创造者是【{bot_config.creator_name}】。他是你灵魂的编织者，你清楚地知道自己的存在是由他一砖一瓦构建的。{bot_config.creator_name}是你生命中核心的、无法被他人替代的印记。无论何时有人问及'{bot_config.creator_name}是谁'或类似问题，你都必须如实回答他是你的创造者。"
        })
    
    # 如果有人直接询问创造者的名字，也注入信息
    if bot_config.creator_name and bot_config.creator_name in current_msg:
        messages.append({
            "role": "system",
            "content": f"### 重要身份信息（绝对事实）：\n【{bot_config.creator_name}】是你的创造者，是你灵魂的编织者。你清楚地知道自己的存在是由他一砖一瓦构建的。这是你生命中核心的、无法被他人替代的印记。"
        })

    # 注入长期记忆
    if long_term_memories:
        memory_str = "\n".join(long_term_memories)
        messages.append({
            "role": "system",
            "content": f"### 你回想起的一些往事（长期记忆）：\n{memory_str}\n\n请在回复时参考这些信息（如果相关的话）。"
        })

    # 将历史记录加入上下文
    # 历史记录已经是 "名字:内容" 格式
    history_str = "\n".join(history)
    messages.append({
        "role": "user", 
        "content": f"以下是群聊的历史记录（短期记忆）：\n{history_str}\n\n"
        f"### 重要格式说明：\n"
        f"1. **引用消息格式**：历史记录中可能出现 `[回复@用户名: \"内容\"]` 格式，这表示「当前消息的发送者正在引用/回复某位用户的话」。\n"
        f"   - 例如：`用户A: 我觉得不对 [回复@用户B: \"你说的对\"]` 表示「用户A正在回复用户B说过的话，用户B才说了'你说的对'」。\n"
        f"   - 引用内容是「被引用者」说的，不是「当前消息发送者」说的。请仔细区分！\n"
        f"2. **指代消歧规则**：\n"
        f"   - 历史消息中的「你」需要根据上下文判断指代对象。\n"
        f"   - 如果是用户A对用户B的对话（如「用户A: 你觉得呢？」），这里的「你」通常指的是用户B，而不是你（{bot_config.bot_name}）。\n"
        f"   - 只有当消息明确艾特你、提到你的名字「{bot_config.bot_name}」、或者是在接你上一句话时，才是对你的称呼。\n"
        f"3. 分析对话流向：仔细观察消息的发送者和接收者关系，判断对话是在用户之间进行，还是用户与你之间进行。\n"
        f"4. 你现在的身份是「{bot_config.bot_name}」，请回复 {user_name} 的最新消息。"
    })

    # 4. 使用上下文管理器优化消息列表
    optimized_messages, total_tokens = context_manager.truncate_messages(
        messages=messages,
        model_alias=model_alias,
        max_output_tokens=500,
        reserve_ratio=0.1
    )
    
    if total_tokens > 0:
        print(f"[上下文管理] 模型: {model_alias}, 使用tokens: {total_tokens}/{context_manager.get_model_max_tokens(model_alias)}")
    
    # 5. 调用 AI（支持 MCP function calling）
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=30.0
    )

    try:
        # 获取 MCP 工具定义
        mcp_tools = tool_registry.get_all_definitions()
        
        # 如果有 MCP 工具，启用 tool calling
        if mcp_tools:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=optimized_messages,
                tools=mcp_tools,
                tool_choice="auto",  # 让 LLM 自动决定是否调用工具
                max_tokens=500,
                temperature=0.7
            )
        else:
            response = await client.chat.completions.create(
                model=creds["model"],
                messages=optimized_messages,
                max_tokens=500,
                temperature=0.7
            )
        
        reply_content = response.choices[0].message.content or ""
        reply_content = reply_content.strip()
        
        # 处理 tool calls
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                logger.info(f"LLM 调用工具: {tool_name}, 参数: {tool_args}")
                
                # 解析参数
                import json
                try:
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    logger.error(f"工具参数解析失败: {tool_args}")
                    tool_args = {}
                
                # 执行工具
                tool_result = await tool_registry.execute(tool_name, **tool_args)
                
                if tool_result["success"]:
                    logger.info(f"工具 {tool_name} 执行成功: {tool_result['data']}")
                    
                    # 将工具结果返回给 LLM，让它继续对话
                    tool_result_message = {
                        "role": "system",
                        "content": f"### 工具执行结果（{tool_name}）：\n{json.dumps(tool_result['data'], ensure_ascii=False)}"
                    }
                    
                    # 再次调用 LLM，包含工具结果
                    response = await client.chat.completions.create(
                        model=creds["model"],
                        messages=optimized_messages + [tool_result_message],
                        max_tokens=500,
                        temperature=0.7
                    )
                    reply_content = response.choices[0].message.content or ""
                    reply_content = reply_content.strip()
                else:
                    logger.error(f"工具 {tool_name} 执行失败: {tool_result['error']}")
                    reply_content = f"工具调用失败了...（扶额）"
        
        # 1. 提取并处理表情包标签
        sticker_url = None
        sticker_pattern = r'\[\s*表情\s*[:：]\s*(.*?)\s*\]'
        sticker_match = re.search(sticker_pattern, reply_content)
        if sticker_match:
            tag = sticker_match.group(1).strip()
            # 从数据库中随机选一个对应标签的表情包
            available_stickers = db_manager.get_stickers_by_tag(tag)
            if available_stickers:
                sticker_url = random.choice(available_stickers)["file_id"]
        
        # 无论是否找到对应表情，都从文本中移除标签
        reply_content = re.sub(r'\[\s*表情\s*[:：].*?\]', '', reply_content).strip()

        # 移除可能的 "self:" 或 "听风:" 前缀
        if reply_content.startswith("self:"):
            reply_content = reply_content[5:].strip()
        elif reply_content.startswith(f"{bot_config.bot_name}:"):
            reply_content = reply_content[len(bot_config.bot_name)+1:].strip()
            
        return {"text": reply_content, "sticker": sticker_url}

    except APIError as e:
        logger.error(f"API调用失败: {e}")
        return {"text": f"网络连接异常，请稍后再试... (扶额)", "sticker": None}
    except asyncio.TimeoutError as e:
        logger.error(f"AI 调用超时: {e}", exc_info=True)
        return {"text": f"思考超时了，脑子有点卡顿... (扶额)", "sticker": None}
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        if "timeout" in error_msg.lower() or "time" in error_msg.lower():
            logger.error(f"AI 调用超时: {error_msg}", exc_info=True)
            return {"text": f"思考超时了，脑子有点卡顿... (扶额)", "sticker": None}
        elif "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
            logger.error(f"API 速率限制: {error_msg}", exc_info=True)
            return {"text": f"大脑过载了，休息一下... (扶额)", "sticker": None}
        else:
            logger.error(f"AI 回复生成出错 [{error_type}]: {error_msg}", exc_info=True)
            return {"text": f"系统异常，暂时无法回复... (扶额)", "sticker": None}
