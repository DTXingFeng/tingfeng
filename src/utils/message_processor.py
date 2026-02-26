from typing import List, Optional
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, GroupMessageEvent
from src.config.config import bot_config

import re

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


def split_text_to_segments(text: str, max_segments: int = 5) -> List[str]:
    """
    将文本按换行符拆分为多个段落，用于分段发送。
    AI 主动决定是否分段（通过换行符），代码不做强制截断。

    Args:
        text: 待拆分的文本
        max_segments: 最大段数（防止刷屏）
    """
    if not text:
        return []

    # 只按换行符分段，保留AI的主动分段意图
    segments = [line.strip() for line in text.split("\n") if line.strip()]

    # 限制最大段数（防止AI输出太多换行导致刷屏）
    if len(segments) > max_segments:
        # 超出限制时，保留前 max_segments-1 段，剩余的合并为最后一段
        merged = "".join(segments[max_segments - 1 :])
        segments = segments[: max_segments - 1] + [merged]

    return segments


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

    # 如果是艾特机器人，确保文本开头有 @self (NoneBot 可能会在 get_message 中移除艾特段)
    if event.is_tome():
        # 检查是否已经有 @self 了，避免重复
        has_at_self = False
        for seg in message:
            if seg.type == "at" and (
                str(seg.data.get("qq")) == str(bot.self_id) or str(seg.data.get("qq")) == bot_config.bot_qq
            ):
                has_at_self = True
                break
        if not has_at_self:
            cleaned_parts.append("@self")

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
            file = seg.data.get("file")
            # 这里的 sub_type=1 通常代表表情包
            is_sticker = str(seg.data.get("sub_type", "0")) == "1"

            if vlm_func and url:
                description = await vlm_func(url, is_sticker=is_sticker, file_id=file)
                cleaned_parts.append(f"[图片内容: {description}]")
            else:
                cleaned_parts.append("[图片]")

        elif seg.type == "reply":
            reply_id = seg.data.get("id")
            if reply_id:
                try:
                    msg_data = await bot.get_msg(message_id=int(reply_id))
                    msg_content = msg_data.get("message", "")

                    if isinstance(msg_content, str):
                        content_preview = msg_content[:20] + ("..." if len(msg_content) > 20 else "")
                    elif isinstance(msg_content, list):
                        abstract = ""
                        for msg_seg in msg_content:
                            if msg_seg["type"] == "text":
                                abstract += msg_seg["data"]["text"]
                            elif msg_seg["type"] == "image":
                                abstract += "[图片]"
                            elif msg_seg["type"] == "face":
                                abstract += "[表情]"
                            if len(abstract) > 20:
                                break
                        content_preview = abstract[:20] + ("..." if len(abstract) > 20 else "")
                    else:
                        content_preview = "未知消息"

                    sender_id = msg_data.get("sender_id", msg_data.get("user_id"))
                    sender_name = None

                    if sender_id:
                        try:
                            member_info = await bot.get_group_member_info(
                                group_id=event.group_id, user_id=int(sender_id)
                            )
                            sender_name = member_info.get("card") or member_info.get("nickname")
                        except Exception:
                            pass

                    if sender_name:
                        cleaned_parts.append(f'[回复@{sender_name}: "{content_preview}"]')
                    else:
                        cleaned_parts.append(f'[回复: "{content_preview}"]')
                except Exception as e:
                    abstract = await get_message_abstract(bot, int(reply_id))
                    cleaned_parts.append(f'[回复: "{abstract}"]')

        elif seg.type == "forward":
            forward_id = seg.data.get("id")
            if forward_id:
                cleaned_parts.append(f"[合并转发消息 ID:{forward_id}]")
                cleaned_parts.append(f"(你可以使用 get_forward_message 工具来查看此合并转发的详细内容)")

    return " ".join(cleaned_parts)
