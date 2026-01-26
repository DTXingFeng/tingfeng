from typing import List, Optional
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, GroupMessageEvent
from src.config.config import bot_config

# 常用表情 ID 到文字的映射 (示例，实际可扩充)
FACE_MAP = {
    "124": "呲牙",
    "9": "大哭",
    "14": "微笑",
    "1": "撇嘴",
    "2": "色",
    "3": "发呆",
    "4": "得意",
    "5": "流泪",
    "6": "害羞",
    "7": "闭嘴",
    "8": "睡",
    "10": "尴尬",
    "11": "发怒",
    "12": "调皮",
    "13": "呲牙",
}

async def get_message_abstract(bot: Bot, message_id: int) -> str:
    """获取消息内容的摘要，用于回复显示"""
    try:
        msg_data = await bot.get_msg(message_id=message_id)
        msg_content = msg_data.get("message", "")
        if isinstance(msg_content, str):
            return msg_content[:20] + ("..." if len(msg_content) > 20 else "")
        elif isinstance(msg_content, list):
            # 处理结构化消息段
            abstract = ""
            for seg in msg_content:
                if seg["type"] == "text":
                    abstract += seg["data"]["text"]
                elif seg["type"] == "image":
                    abstract += "[图片]"
                elif seg["type"] == "face":
                    abstract += "[表情]"
                if len(abstract) > 20:
                    break
            return abstract[:20] + ("..." if len(abstract) > 20 else "")
    except Exception:
        return "未知消息"
    return "未知消息"

async def process_message_for_llm(bot: Bot, event: GroupMessageEvent, vlm_func=None) -> str:
    """
    将原始消息序列转换为 LLM 可读的文本
    vlm_func: 一个异步函数，接受 image_url 返回描述文字
    """
    message = event.get_message()
    cleaned_parts = []

    for seg in message:
        if seg.type == "text":
            text = seg.data.get("text", "").strip()
            if text:
                cleaned_parts.append(text)
        
        elif seg.type == "at":
            qq = seg.data.get("qq")
            if qq == "all":
                cleaned_parts.append("@全体成员")
            elif str(qq) == str(bot.self_id) or str(qq) == bot_config.bot_qq:
                cleaned_parts.append("@self")
            else:
                try:
                    member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(qq))
                    name = member_info.get("card") or member_info.get("nickname") or str(qq)
                    cleaned_parts.append(f"@{name}")
                except Exception:
                    cleaned_parts.append(f"@{qq}")
        
        elif seg.type == "face":
            face_id = seg.data.get("id")
            face_name = FACE_MAP.get(str(face_id), f"表情:{face_id}")
            cleaned_parts.append(f"[{face_name}]")
        
        elif seg.type == "image":
            url = seg.data.get("url")
            if vlm_func and url:
                description = await vlm_func(url)
                cleaned_parts.append(f"[图片内容: {description}]")
            else:
                cleaned_parts.append("[图片]")
        
        elif seg.type == "reply":
            reply_id = seg.data.get("id")
            if reply_id:
                abstract = await get_message_abstract(bot, int(reply_id))
                cleaned_parts.append(f"[回复: \"{abstract}\"]")

    return " ".join(cleaned_parts)
