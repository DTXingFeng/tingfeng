"""
MCP 工具注册中心
统一管理所有可用的 MCP 工具
"""

from typing import Dict, List, Optional, Any
from src.mcp.base_tool import BaseTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    工具注册中心

    功能：
    - 注册工具
    - 查询工具
    - 获取工具列表
    - 执行工具
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool: BaseTool):
        """
        注册工具

        Args:
            tool: BaseTool 工具实例
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"只能注册 BaseTool 的子类，得到的是 {type(tool)}")

        if tool.name in cls._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")

        cls._tools[tool.name] = tool
        logger.info(f"已注册 MCP 工具: {tool.name}")

    @classmethod
    def unregister(cls, tool_name: str):
        """
        注销工具

        Args:
            tool_name: str 工具名称
        """
        if tool_name in cls._tools:
            del cls._tools[tool_name]
            logger.info(f"已注销 MCP 工具: {tool_name}")

    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具

        Args:
            tool_name: str 工具名称

        Returns:
            Optional[BaseTool]: 工具实例，不存在返回 None
        """
        return cls._tools.get(tool_name)

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        列出所有已注册的工具

        Returns:
            List[str]: 工具名称列表
        """
        return list(cls._tools.keys())

    @classmethod
    def get_all_definitions(cls) -> List[Dict[str, Any]]:
        """
        获取所有工具的定义（用于 OpenAI function calling）

        Returns:
            List[Dict]: 工具定义列表
        """
        return [tool.to_function_definition() for tool in cls._tools.values()]

    @classmethod
    async def execute(cls, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Args:
            tool_name: str 工具名称
            **kwargs: 工具参数

        Returns:
            dict: 执行结果
        """
        tool = cls.get_tool(tool_name)
        if tool is None:
            logger.error(f"工具 {tool_name} 不存在")
            return {"success": False, "data": None, "tool": tool_name, "error": f"工具 {tool_name} 不存在"}

        logger.debug(f"执行 MCP 工具: {tool_name}, 参数: {kwargs}")
        return await tool.safe_execute(**kwargs)

    @classmethod
    def clear(cls):
        """
        清空所有已注册的工具（主要用于测试）
        """
        cls._tools.clear()
        logger.info("已清空所有 MCP 工具")


def register_tool(tool_class: type):
    """
    装饰器：自动注册工具类

    使用方式：
        @register_tool
        class MyTool(BaseTool):
            ...
    """

    def decorator(cls):
        if not issubclass(cls, BaseTool):
            raise TypeError(f"{cls.__name__} 必须继承 BaseTool")
        instance = cls()
        ToolRegistry.register(instance)
        return cls

    return decorator


# 全局单例
tool_registry = ToolRegistry()
