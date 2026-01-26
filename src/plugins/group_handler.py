from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from src.utils.message_processor import process_message_for_llm
from src.aimodel.image_processing.vlm import get_vlm_description
from src.config.config import bot_config
import random

# 创建一个响应所有消息的响应器
# 因为已经在 bot.py 做了全局过滤，所以这里的 on_message() 实际上只会收到群消息
group_msg_matcher = on_message()

@group_msg_matcher.handle()
async def handle_group_message(bot: Bot, event: GroupMessageEvent):
    """
    当接收到群消息时，NoneBot 会调用这个方法。
    """
    # 1. 基础信息
    message_id = event.message_id        # 消息 ID
    message_text = event.get_plaintext() # 纯文本内容
    group_id = event.group_id            # 群号
    user_id = event.user_id              # 发送者 QQ 号
    
    # 2. 发送者详细信息
    sender = event.sender
    nickname = sender.nickname
    card = sender.card or nickname
    role = sender.role
    
    # 3. 提取各种消息段
    normal_images = []  # 普通图片 URL
    stickers = []       # 表情包 URL (sub_type=1)
    flash_images = []    # 闪照 URL (type=flash)
    faces = []          # 系统表情 ID (例如: 124 代表 [呲牙])
    
    for segment in event.get_message():
        # 处理图片
        if segment.type == "image":
            url = segment.data.get("url")
            sub_type = str(segment.data.get("sub_type", "0"))
            img_type = segment.data.get("type")
            
            if img_type == "flash":
                flash_images.append(url)
            elif sub_type == "1":
                stickers.append(url)
            else:
                normal_images.append(url)
                
        # 处理系统表情
        elif segment.type == "face":
            face_id = segment.data.get("id")
            if face_id:
                faces.append(face_id)
    
    # 4. 原始消息对象
    raw_message = event.get_message()
    
    # 5. 生成供 LLM 使用的清洗后文本
    llm_text = await process_message_for_llm(bot, event, vlm_func=get_vlm_description)
    
    # 6. 回复率过滤 (如果不是艾特我，则根据回复率决定是否处理)
    is_at_me = "@self" in llm_text or event.is_tome()
    if not is_at_me and random.random() > bot_config.reply_rate:
        # print(f"  - 随机过滤: 回复率 {bot_config.reply_rate}，本次跳过")
        return

    # --- 调用处理逻辑 ---
    await process_my_logic(
        bot=bot,
        event=event,
        message_id=message_id,
        text=message_text,
        llm_text=llm_text,
        normal_images=normal_images,
        stickers=stickers,
        flash_images=flash_images,
        faces=faces,
        group_id=group_id,
        user_id=user_id,
        nickname=nickname,
        card=card,
        role=role,
        raw_msg=raw_message
    )

async def process_my_logic(
    bot: Bot, 
    event: GroupMessageEvent, 
    message_id: int,
    text: str, 
    llm_text: str,
    normal_images: list[str], # 普通图片
    stickers: list[str],      # 表情包
    flash_images: list[str],   # 闪照
    faces: list[str],         # 系统表情 ID
    group_id: int, 
    user_id: int,
    nickname: str,
    card: str,
    role: str,
    raw_msg: any
):
    """
    这就是您要编写代码的方法。
    """
    # 打印分类信息
    print(f"[{role}] {card}({user_id}) 在群 {group_id} 发送了:")
    if text: print(f"  - 原始文字: {text}")
    if llm_text: print(f"  - 清洗后文本 (LLM): {llm_text}")
    print(f"  - 使用提示词: {bot_config.prompt[:20]}...")
    if normal_images: print(f"  - 普通图片: {len(normal_images)} 张")
    if stickers: print(f"  - 表情包: {len(stickers)} 个")
    if flash_images: print(f"  - 闪照: {len(flash_images)} 张")
    if faces: print(f"  - 系统表情 ID 列表: {faces}")
    
    # 在这里开始写您的代码...
    pass
    
