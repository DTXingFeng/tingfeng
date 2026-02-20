"""
MCP 工具加载器
自动注册所有 MCP 工具
"""

from src.mcp.tools.memory import MemorySearchTool, GetUserMemoriesTool, AddMemoryTool
from src.mcp.tools.user import UserProfileTool, GetCreatorInfoTool, UpdateRelationshipTool
from src.mcp.tools.knowledge import KnowledgeQueryTool, GetCreatorKnowledgeTool, AddKnowledgeTool
from src.mcp.tools.utility import GetCurrentTimeTool, IsWithinScheduleTool, FormatTextTool, CountWordsTool
from src.mcp.tools.message import GetRecentMessagesTool, GetMessageContextTool
from src.mcp.tools.system import GetSystemResourceTool, GetNetworkInfoTool, GetBootTimeTool, GetRaspberryPiInfoTool
from src.mcp.tools.forward import GetForwardMessageTool, ParseForwardMessageTool, FormatForwardMessagesTool
from src.mcp.tools.web_search import WebSearchTool
from src.mcp.registry import tool_registry
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_all_tools():
    """
    加载并注册所有 MCP 工具

    这应该在 bot 启动时调用一次
    注意：这是一个同步函数
    """
    logger.info("开始加载 MCP 工具...")

    # 记忆相关工具
    tool_registry.register(MemorySearchTool())
    tool_registry.register(GetUserMemoriesTool())
    tool_registry.register(AddMemoryTool())

    # 用户相关工具
    tool_registry.register(UserProfileTool())
    tool_registry.register(GetCreatorInfoTool())
    tool_registry.register(UpdateRelationshipTool())

    # 知识相关工具
    tool_registry.register(KnowledgeQueryTool())
    tool_registry.register(GetCreatorKnowledgeTool())
    tool_registry.register(AddKnowledgeTool())

    # 实用工具
    tool_registry.register(GetCurrentTimeTool())
    tool_registry.register(IsWithinScheduleTool())
    tool_registry.register(FormatTextTool())
    tool_registry.register(CountWordsTool())

    # 消息相关工具
    tool_registry.register(GetRecentMessagesTool())
    tool_registry.register(GetMessageContextTool())

    # 系统监控工具
    tool_registry.register(GetSystemResourceTool())
    tool_registry.register(GetNetworkInfoTool())
    tool_registry.register(GetBootTimeTool())
    tool_registry.register(GetRaspberryPiInfoTool())

    # 合并转发消息工具
    tool_registry.register(GetForwardMessageTool())
    tool_registry.register(ParseForwardMessageTool())
    tool_registry.register(FormatForwardMessagesTool())

    # 网络搜索工具
    tool_registry.register(WebSearchTool())

    logger.info(f"MCP 工具加载完成！共注册 {len(tool_registry.list_tools())} 个工具")

    # 输出已注册的工具列表
    for tool_name in tool_registry.list_tools():
        logger.debug(f"  - {tool_name}")


def get_tools_summary() -> dict:
    """
    获取所有工具的摘要信息

    Returns:
        dict: 工具摘要，按类别分组
    """
    tools = tool_registry.list_tools()

    summary = {
        "total": len(tools),
        "memory": [],
        "user": [],
        "knowledge": [],
        "utility": [],
        "message": [],
        "system": [],
        "forward": [],
        "web": [],
    }

    for tool_name in tools:
        tool = tool_registry.get_tool(tool_name)
        if tool_name.startswith("memory") or tool_name.startswith("get_user"):
            summary["memory"].append(tool_name)
        elif tool_name.startswith("user") or tool_name.startswith("get_creator"):
            summary["user"].append(tool_name)
        elif tool_name.startswith("knowledge"):
            summary["knowledge"].append(tool_name)
        elif (
            tool_name.startswith("get_")
            and "forward" in tool_name
            or tool_name.startswith("forward")
            or "forward" in tool_name
        ):
            summary["forward"].append(tool_name)
        elif tool_name.startswith("get_") and (
            "system" in tool_name or "network" in tool_name or "boot" in tool_name or "raspberry" in tool_name
        ):
            summary["system"].append(tool_name)
        elif tool_name.startswith("get_") and "message" in tool_name or tool_name.startswith("message"):
            summary["message"].append(tool_name)
        elif tool_name.startswith("web") or "search" in tool_name:
            summary["web"].append(tool_name)
        else:
            summary["utility"].append(tool_name)

    return summary


if __name__ == "__main__":
    import asyncio

    async def test():
        load_all_tools()
        summary = get_tools_summary()
        print("\n=== MCP 工具摘要 ===")
        print(f"总计: {summary['total']} 个工具")
        print(f"\n记忆工具 ({len(summary['memory'])}):")
        for t in summary["memory"]:
            print(f"  - {t}")
        print(f"\n用户工具 ({len(summary['user'])}):")
        for t in summary["user"]:
            print(f"  - {t}")
        print(f"\n知识工具 ({len(summary['knowledge'])}):")
        for t in summary["knowledge"]:
            print(f"  - {t}")
        print(f"\n实用工具 ({len(summary['utility'])}):")
        for t in summary["utility"]:
            print(f"  - {t}")
        print(f"\n消息工具 ({len(summary['message'])}):")
        for t in summary["message"]:
            print(f"  - {t}")
        print(f"\n系统监控工具 ({len(summary['system'])}):")
        for t in summary["system"]:
            print(f"  - {t}")
        print(f"\n合并转发工具 ({len(summary['forward'])}):")
        for t in summary["forward"]:
            print(f"  - {t}")
        print(f"\n网络搜索工具 ({len(summary['web'])}):")
        for t in summary["web"]:
            print(f"  - {t}")

        print("\n测试工具调用...")
        result = await tool_registry.execute("get_current_time")
        print(f"get_current_time: {result}")

    asyncio.run(test())
