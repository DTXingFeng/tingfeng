import requests
import json
from typing import Generator
from src.logger import log_message
from src.config.ai_config import Config as AIConfig


class OpenaiRequest:
    def __init__(self, model_alias: str):
        self.request = AIConfig.get_body_info(model_alias)
        if self.request is None:
            raise ValueError("get_body_info 返回了空值，请检查 model_alias 配置")
        
        self.platforms_info = AIConfig.get_platforms_info(model_alias)
        if self.platforms_info is None:
            raise ValueError("get_platforms_info 返回了空值，请检查 model_alias 配置")
    
    def chat(self,messages: list[dict],) -> str:
        
        self.request['messages'] = messages
        response = requests.post(
            self.platforms_info['base_url'].rstrip('/') + '/chat/completions',
            headers={
                'Authorization': f'Bearer {self.platforms_info["api_key"]}',
                'Content-Type': 'application/json'
            },
            json=self.request
        )
        
        if response.status_code == 200:
            log_message(f"OpenAI API 调用成功，响应内容：{response.json()}", 'info')
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"OpenAI API 调用失败，状态码：{response.status_code}，响应内容：{response.text}")

