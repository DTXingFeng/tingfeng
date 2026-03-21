import json
from src.logger import log_message
from src.config import Config


class Sender:
    def __init__(self, data: dict):
        self.card = data.get("card", "")
        self.nickname = data.get("nickname", "")
        self.user_id = data.get("user_id", 0)
        self.role = data.get("role", "")


class Message:
    def __init__(self, data: dict):
        self.sender = Sender(data["sender"])
        self.message_id = data.get("message_id", 0)
        self.message_seq = data.get("message_seq", 0)
        self.message_type = data.get("message_type", "")
        self.raw_message = data.get("raw_message", "")
        self.group_id = data.get("group_id", None)
        self.post_type = data.get("post_type", None)
        self.self_id = data.get("self_id", 0)
    
    
    def has_cq_code(self) -> bool:
        return "[CQ:" in self.raw_message and self.raw_message.find("]", self.raw_message.find("[CQ:")) > 0

    
    def render_cq_code(self) -> str:
        """
        把cq码渲染成llm可以理解的格式
        支持多个CQ码和CQ码与文字混合的消息
        参考: https://docs.go-cqhttp.org/cqcode
        """
        import re
        message = self.raw_message
        
        cq_pattern = r'\[CQ:([^,\]]+)(?:,([^\]]+))?\]'
        
        def parse_params(params_str: str) -> dict:
            param_dict = {}
            if params_str:
                parts = []
                current = ""
                in_escape = False
                for char in params_str:
                    if in_escape:
                        if char == '#':
                            current += char
                            in_escape = False
                        else:
                            current += char
                            in_escape = False
                    elif char == '&':
                        in_escape = True
                    elif char == ',':
                        parts.append(current)
                        current = ""
                    else:
                        current += char
                if current:
                    parts.append(current)
                
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        param_dict[key] = value
            return param_dict
        
        def replace_cq(match):
            cq_type = match.group(1)
            params_str = match.group(2) or ""
            params = parse_params(params_str)
            
            if cq_type == 'face':
                return f'[表情:{params.get("id", "未知")}]'
            elif cq_type == 'record':
                file_val = params.get("file")
                return f'[语音:{file_val[:20]}...]' if file_val else '[语音]'
            elif cq_type == 'at':
                qq = params.get('qq')
                if qq == str(self.self_id):
                    return '@self'
                else:
                    pass
                return '@全体成员' if qq == 'all' else f'@{qq or "未知"}'
            elif cq_type == 'image':
                return self._render_image_cq(params)
            elif cq_type == 'reply':
                id =  params.get("id")
                return f'[回复:{id}]'
            elif cq_type == 'share':
                return f'[链接:{params.get("title", "分享")}]'
            elif cq_type == 'location':
                title = params.get("title")
                if title:
                    return f'[位置:{title}]'
                lat = params.get("lat", "")
                lon = params.get("lon", "")
                return f'[位置:({lat},{lon})]' if lat or lon else '[位置]'
            elif cq_type == 'music':
                return f'[音乐:{params.get("id", "未知")}]'
            elif cq_type == 'redbag':
                return f'[红包:{params.get("title", "祝福语")}]'
            elif cq_type == 'poke':
                return f'[戳一戳:{params.get("qq", "未知")}]'
            elif cq_type == 'gift':
                return f'[礼物:{params.get("qq", "未知")}]'
            elif cq_type == 'contact':
                return '[推荐好友/群]' if params.get('type') == 'qq' else '[推荐群]'
            elif cq_type == 'rps':
                return '[猜拳]'
            elif cq_type == 'dice':
                return '[掷骰子]'
            elif cq_type == 'shake':
                return '[窗口抖动]'
            elif cq_type == 'anonymous':
                return '[匿名消息]'
            elif cq_type == 'video':
                return '[短视频]'
            elif cq_type == 'forward':
                return '[合并转发]'
            elif cq_type == 'node':
                return '[转发消息节点]'
            elif cq_type == 'xml':
                return '[XML消息]'
            elif cq_type == 'json':
                return '[JSON消息]'
            elif cq_type == 'cardimage':
                return '[卡片图片]'
            elif cq_type == 'tts':
                return '[文本转语音]'
            else:
                return f'[{cq_type}]'
        
        return re.sub(cq_pattern, replace_cq, message)
    
    def _render_image_cq(self, params: dict) -> str:
        """渲染图片 CQ 码，返回 file/url 供 VLM 处理"""
        img_type = params.get('type', '')
        sub_type = params.get('subType', '0')
        effect_id = params.get('id', '40000')
        
        file_val = params.get('file', '')
        url_val = params.get('url', '')
        image_source = file_val or url_val
        
        if img_type == 'flash':
            return f'[闪照:{image_source}]'
        elif img_type == 'show':
            effect_names = {
                '40000': '普通', '40001': '幻影', '40002': '抖动',
                '40003': '生日', '40004': '爱你', '40005': '征友'
            }
            return f'[秀图:{effect_names.get(effect_id, effect_id)}:{image_source}]'
        else:
            sub_type_names = {
                '0': '正常图片', '1': '表情包', '2': '热图',
                '3': '斗图', '4': '智图', '7': '贴图',
                '8': '自拍', '9': '贴图广告'
            }
            if sub_type == '1':
                # 表情包,看看有没有缓存，没有就
                return f'[表情:{image_source}]'
            if sub_type == '0':
                # 普通图片，直接给到 VLM 处理
                return f'[图片:{image_source}]'
            type_desc = sub_type_names.get(sub_type, '图片')
            return f'[{type_desc}:{image_source}]'
        

def process_message(raw_message: str) -> Message | None:
    try:
        data = json.loads(raw_message)
        if data["post_type"] == "message":
            msg = Message(data)
            log_message(f"收到{msg.message_type}消息{'，群聊ID：' + str(msg.group_id) if msg.group_id else ''}，发送者：{msg.sender.nickname}({msg.sender.user_id})，消息内容：{msg.raw_message}", 'info')
            return msg
        return None
    except json.JSONDecodeError as e:
        log_message(f"JSON 解析失败: {e}", 'error')
        return None


def handle_message(data: Message):
    if data.post_type == 'message':
        handle_chat(data)
    elif data.post_type == 'command':
        handle_command(data)
    else:
        log_message(f"未知消息类型: {data.post_type}", 'warning')


def handle_chat(data: Message):
    if data.message_type == "group":
        if data.group_id in Config.get("allowed_groups", []):
            print("该群聊在配置文件中，处理消息")
    elif data.message_type == "private":
        pass


def handle_command(data: Message):
    pass
