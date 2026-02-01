import tiktoken
from typing import List, Dict, Optional, Tuple
from src.config.ai_config import ai_config, ai_config_manager

class ContextManager:
    """
    上下文管理器：负责计算token数量并动态调整上下文长度
    """
    
    def __init__(self):
        self._tokenizer_cache = {}
    
    def _get_tokenizer(self, model_name: str):
        """
        获取指定模型的tokenizer，使用缓存避免重复初始化
        """
        if model_name not in self._tokenizer_cache:
            try:
                if "gpt" in model_name.lower():
                    self._tokenizer_cache[model_name] = tiktoken.encoding_for_model(model_name)
                elif "qwen" in model_name.lower():
                    self._tokenizer_cache[model_name] = tiktoken.get_encoding("cl100k_base")
                else:
                    self._tokenizer_cache[model_name] = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer_cache[model_name] = tiktoken.get_encoding("cl100k_base")
        
        return self._tokenizer_cache[model_name]
    
    def count_tokens(self, text: str, model_name: str = "default") -> int:
        """
        计算文本的token数量
        """
        if not text:
            return 0
        
        try:
            tokenizer = self._get_tokenizer(model_name)
            return len(tokenizer.encode(text))
        except Exception:
            return len(text) // 2
    
    def count_messages_tokens(self, messages: List[Dict], model_name: str = "default") -> int:
        """
        计算消息列表的总token数量
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            total += self.count_tokens(content, model_name)
            total += self.count_tokens(role, model_name)
        return total
    
    def get_model_max_tokens(self, model_alias: str) -> int:
        """
        获取模型的最大上下文token数
        """
        model_cfg = ai_config.models.get(model_alias)
        if model_cfg and hasattr(model_cfg, 'max_context_tokens'):
            return model_cfg.max_context_tokens
        return 4096
    
    def truncate_messages(
        self,
        messages: List[Dict],
        model_alias: str,
        max_output_tokens: int = 500,
        reserve_ratio: float = 0.1
    ) -> Tuple[List[Dict], int]:
        """
        截断消息列表以适应模型的上下文限制
        
        Args:
            messages: 消息列表
            model_alias: 模型别名
            max_output_tokens: 预期输出的最大token数
            reserve_ratio: 预留比例，用于确保不会超过限制
        
        Returns:
            (截断后的消息列表, 实际使用的token数)
        """
        if not messages:
            return [], 0
        
        max_context = self.get_model_max_tokens(model_alias)
        available_tokens = max_context - max_output_tokens - int(max_context * reserve_ratio)
        
        if available_tokens <= 0:
            return [], 0
        
        total_tokens = self.count_messages_tokens(messages, model_alias)
        
        if total_tokens <= available_tokens:
            return messages, total_tokens
        
        truncated_messages = []
        current_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = self.count_tokens(msg.get("content", ""), model_alias)
            
            if current_tokens + msg_tokens <= available_tokens:
                truncated_messages.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return truncated_messages, current_tokens
    
    def truncate_text(
        self,
        text: str,
        model_alias: str,
        max_output_tokens: int = 500,
        reserve_ratio: float = 0.1
    ) -> Tuple[str, int]:
        """
        截断文本以适应模型的上下文限制
        
        Args:
            text: 要截断的文本
            model_alias: 模型别名
            max_output_tokens: 预期输出的最大token数
            reserve_ratio: 预留比例
        
        Returns:
            (截断后的文本, 实际使用的token数)
        """
        if not text:
            return "", 0
        
        max_context = self.get_model_max_tokens(model_alias)
        available_tokens = max_context - max_output_tokens - int(max_context * reserve_ratio)
        
        if available_tokens <= 0:
            return "", 0
        
        total_tokens = self.count_tokens(text, model_alias)
        
        if total_tokens <= available_tokens:
            return text, total_tokens
        
        try:
            tokenizer = self._get_tokenizer(model_alias)
            tokens = tokenizer.encode(text)
            truncated_tokens = tokens[:available_tokens]
            truncated_text = tokenizer.decode(truncated_tokens)
            return truncated_text, len(truncated_tokens)
        except Exception:
            return text[:available_tokens * 2], available_tokens
    
    def optimize_context_for_chat(
        self,
        system_prompt: str,
        history: List[str],
        user_context: List[str],
        model_alias: str,
        max_output_tokens: int = 500
    ) -> Dict[str, any]:
        """
        优化聊天上下文，确保不超过模型限制
        
        Args:
            system_prompt: 系统提示词
            history: 历史消息列表
            user_context: 用户上下文列表（如记忆、画像等）
            model_alias: 模型别名
            max_output_tokens: 预期输出的最大token数
        
        Returns:
            {
                "system_prompt": str,
                "history": List[str],
                "user_context": List[str],
                "total_tokens": int,
                "truncated": bool
            }
        """
        max_context = self.get_model_max_tokens(model_alias)
        available_tokens = max_context - max_output_tokens - int(max_context * 0.1)
        
        if available_tokens <= 0:
            return {
                "system_prompt": "",
                "history": [],
                "user_context": [],
                "total_tokens": 0,
                "truncated": True
            }
        
        system_tokens = self.count_tokens(system_prompt, model_alias)
        remaining_tokens = available_tokens - system_tokens
        
        if remaining_tokens <= 0:
            return {
                "system_prompt": system_prompt[:available_tokens * 2],
                "history": [],
                "user_context": [],
                "total_tokens": system_tokens,
                "truncated": True
            }
        
        truncated_history = []
        history_tokens = 0
        
        for msg in reversed(history):
            msg_tokens = self.count_tokens(msg, model_alias)
            if history_tokens + msg_tokens <= remaining_tokens * 0.7:
                truncated_history.insert(0, msg)
                history_tokens += msg_tokens
            else:
                break
        
        remaining_tokens -= history_tokens
        truncated_context = []
        context_tokens = 0
        
        for ctx in reversed(user_context):
            ctx_tokens = self.count_tokens(ctx, model_alias)
            if context_tokens + ctx_tokens <= remaining_tokens:
                truncated_context.insert(0, ctx)
                context_tokens += ctx_tokens
            else:
                break
        
        total_tokens = system_tokens + history_tokens + context_tokens
        
        return {
            "system_prompt": system_prompt,
            "history": truncated_history,
            "user_context": truncated_context,
            "total_tokens": total_tokens,
            "truncated": len(history) > len(truncated_history) or len(user_context) > len(truncated_context)
        }

context_manager = ContextManager()
