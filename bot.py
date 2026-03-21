import asyncio
import websockets
from src.logger import log_message, set_log_level
from src.message import process_message, handle_message
from src.config.config import Config
from src.config.ai_config import Config as AIConfig
from src.aimodel.LLMRequest.openai_request import OpenaiRequest
from src.aimodel.image_processing.vlm import get_vlm_description

RETRY_DELAY = 5

async def connect_websocket():
    uri = Config.get('websocket.uri', 'ws://192.168.8.240:3001')
    retry_count = 0
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                log_message(f"WebSocket 连接成功", 'success')
                retry_count = 0
                
                while True:
                    raw_message = await websocket.recv()
                    log_message(f"收到消息：{raw_message}", 'debug')
                    
                    data = process_message(raw_message)
                    if data is None:
                        continue
                    
                    handle_message(data)
                    
        except (websockets.exceptions.WebSocketException, OSError) as e:
            retry_count += 1
            log_message(f"连接断开：{e}，{RETRY_DELAY}秒后重试（第{retry_count}次）", 'warning')
            await asyncio.sleep(RETRY_DELAY)


async def hello():
    uri = Config.get('websocket.uri', 'ws://192.168.8.240:3001')
    log_message(f"正在连接 {uri}", 'info')
    
    await connect_websocket()


asyncio.run(hello())
