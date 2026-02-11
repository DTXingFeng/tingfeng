"""
MCP 工具基类
所有 MCP 工具都应继承此类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """
    MCP 工具基类

    所有工具需要实现：
    - name: 工具名称
    - description: 工具描述
    - parameters: 参数定义
    - execute: 执行方法
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def __init__(self):
        self.validate_definition()

    def validate_definition(self):
        """验证工具定义是否完整"""
        if not self.name:
            raise ValueError(f"{self.__class__.__name__}: name 不能为空")
        if not self.description:
            raise ValueError(f"{self.__class__.__name__}: description 不能为空")
        if not isinstance(self.parameters, dict):
            raise ValueError(f"{self.__class__.__name__}: parameters 必须是字典")

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            dict: 执行结果，必须包含：
                - success: bool 是否成功
                - data: Any 返回数据
                - error: Optional[str] 错误信息（如果失败）
        """
        pass

    async def safe_execute(self, **kwargs) -> Dict[str, Any]:
        """
        安全执行工具（带异常捕获）

        Returns:
            dict: 标准化的执行结果
        """
        try:
            # 过滤掉不在工具参数定义中的额外参数
            filtered_kwargs = {}
            for key, value in kwargs.items():
                if key in self.parameters:
                    filtered_kwargs[key] = value
                else:
                    logger.debug(f"工具 {self.name} 忽略未定义的参数: {key}={value}")
            
            result = await self.execute(**filtered_kwargs)
            return {"success": True, "data": result, "tool": self.name, "error": None}
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {e}", exc_info=True)
            return {"success": False, "data": None, "tool": self.name, "error": str(e)}

    def to_function_definition(self) -> Dict[str, Any]:
        """
        转换为 OpenAI function calling 格式

        Returns:
            dict: 符合 OpenAI function calling 规范的定义
        """
        properties = {}
        required = []

        for param_name, param_def in self.parameters.items():
            properties[param_name] = {
                "type": param_def.get("type", "string"),
                "description": param_def.get("description", ""),
            }

            if param_def.get("required", False):
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }
