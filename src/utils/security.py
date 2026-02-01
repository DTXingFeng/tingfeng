import re
from typing import Optional, List, Dict, Any
from .logger import get_logger
from .error_handler import ValidationError

logger = get_logger(__name__)

class InputValidator:
    """输入验证器"""
    
    # 危险命令和关键词列表
    DANGEROUS_PATTERNS = [
        r'drop\s+table',
        r'delete\s+from',
        r'truncate\s+table',
        r'exec\s*\(',
        r'eval\s*\(',
        r'__import__',
        r'__builtins__',
        r'\$\([^)]*\)',
    ]
    
    # 敏感词汇过滤（可根据需要调整）
    SENSITIVE_KEYWORDS = [
        '自杀', '自残', '杀', '死', '爆炸', '炸弹',
    ]
    
    @staticmethod
    def validate_text(text: str, max_length: int = 5000) -> Dict[str, Any]:
        """
        验证文本输入
        
        Args:
            text: 待验证的文本
            max_length: 最大长度限制
        
        Returns:
            {"valid": bool, "sanitized": str, "reason": Optional[str]}
        """
        if not text:
            return {"valid": True, "sanitized": "", "reason": None}
        
        # 检查长度
        if len(text) > max_length:
            logger.warning(f"文本过长，拒绝处理: {len(text)} > {max_length}")
            return {
                "valid": False,
                "sanitized": text[:max_length],
                "reason": f"文本长度超过限制 ({max_length} 字符)"
            }
        
        # 检查危险模式
        for pattern in InputValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"检测到危险模式: {pattern}")
                return {
                    "valid": False,
                    "sanitized": "",
                    "reason": "包含非法字符或命令"
                }
        
        # 检查敏感词（仅警告，不阻止）
        sensitive_found = []
        for keyword in InputValidator.SENSITIVE_KEYWORDS:
            if keyword in text:
                sensitive_found.append(keyword)
        
        if sensitive_found:
            logger.warning(f"检测到敏感关键词: {sensitive_found}")
        
        return {
            "valid": True,
            "sanitized": text,
            "reason": None
        }
    
    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """
        验证用户名
        
        Args:
            username: 用户名
        
        Returns:
            {"valid": bool, "sanitized": str, "reason": Optional[str]}
        """
        if not username:
            return {"valid": False, "sanitized": "匿名用户", "reason": "用户名为空"}
        
        # 移除控制字符
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', username)
        
        # 限制长度
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        return {
            "valid": True,
            "sanitized": sanitized,
            "reason": None
        }
    
    @staticmethod
    def validate_group_id(group_id: int) -> bool:
        """
        验证群组 ID
        
        Args:
            group_id: 群组 ID
        
        Returns:
            是否有效
        """
        return isinstance(group_id, int) and group_id > 0 and group_id < 9999999999
    
    @staticmethod
    def validate_json(json_str: str) -> Dict[str, Any]:
        """
        验证 JSON 字符串
        
        Args:
            json_str: JSON 字符串
        
        Returns:
            {"valid": bool, "data": Optional[Dict], "reason": Optional[str]}
        """
        import json
        
        try:
            data = json.loads(json_str)
            return {
                "valid": True,
                "data": data,
                "reason": None
            }
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "data": None,
                "reason": f"JSON 格式错误: {str(e)}"
            }

class SecurityMiddleware:
    """安全中间件"""
    
    def __init__(self):
        self.blocked_users = set()
        self.suspicious_patterns = {}
    
    def is_user_blocked(self, user_id: int) -> bool:
        """检查用户是否被阻止"""
        return user_id in self.blocked_users
    
    def block_user(self, user_id: int, reason: str = ""):
        """阻止用户"""
        self.blocked_users.add(user_id)
        logger.warning(f"用户 {user_id} 已被阻止: {reason}")
    
    def unblock_user(self, user_id: int):
        """解除用户阻止"""
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            logger.info(f"用户 {user_id} 已解除阻止")
    
    def check_suspicious_pattern(self, user_id: int, pattern: str):
        """
        检查可疑模式
        
        Args:
            user_id: 用户 ID
            pattern: 检测到的模式
        
        Returns:
            是否可疑
        """
        if user_id not in self.suspicious_patterns:
            self.suspicious_patterns[user_id] = {}
        
        patterns = self.suspicious_patterns[user_id]
        patterns[pattern] = patterns.get(pattern, 0) + 1
        
        # 如果某个模式出现超过 5 次，标记为可疑
        if patterns[pattern] >= 5:
            logger.warning(f"用户 {user_id} 检测到可疑行为: {pattern} (次数: {patterns[pattern]})")
            return True
        
        return False
    
    def reset_user_patterns(self, user_id: int):
        """重置用户模式记录"""
        if user_id in self.suspicious_patterns:
            del self.suspicious_patterns[user_id]

# 全局单例
security_middleware = SecurityMiddleware()

def validate_input(**validators):
    """
    输入验证装饰器
    
    Args:
        **validators: 参数名到验证函数的映射
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    result = validator(kwargs[param_name])
                    if not result["valid"]:
                        raise ValidationError(f"参数 '{param_name}' 验证失败: {result.get('reason')}")
                    
                    kwargs[param_name] = result.get("sanitized", kwargs[param_name])
            
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    result = validator(kwargs[param_name])
                    if not result["valid"]:
                        raise ValidationError(f"参数 '{param_name}' 验证失败: {result.get('reason')}")
                    
                    kwargs[param_name] = result.get("sanitized", kwargs[param_name])
            
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

import asyncio
