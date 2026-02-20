"""
网络搜索 MCP 工具
提供 Bing 网络搜索功能
"""

from typing import Dict, Any
from src.mcp.base_tool import BaseTool
from src.utils.logger import get_logger
import re
import html


logger = get_logger(__name__)


def parse_bing_results(html_content: str, max_results: int = 10) -> list:
    """
    使用正则表达式解析 Bing 搜索结果
    这种方法更可靠，不依赖 HTML 结构的精确匹配

    Args:
        html_content: Bing 搜索页面的 HTML 内容
        max_results: 最大返回结果数

    Returns:
        list: 解析后的搜索结果列表
    """
    results = []

    # Bing 搜索结果的模式
    # 匹配包含链接、标题和描述的搜索结果块
    pattern = r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>.*?</li>'
    matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)

    for match in matches[:max_results]:
        result = {}

        # 提取链接
        url_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', match, re.IGNORECASE)
        if url_match:
            url = url_match.group(1)
            # 清理 URL（移除 Bing 跟踪参数）
            url = re.sub(r'^https://cc\.bingj\.com/cache\.aspx\?.*?&(u=[^&]+)', r'https://\1', url)
            url = html.unescape(url)
            result["url"] = url

        # 提取标题
        title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', match, re.DOTALL | re.IGNORECASE)
        if title_match:
            title = title_match.group(1)
            # 移除 HTML 标签
            title = re.sub(r'<[^>]+>', '', title)
            title = html.unescape(title)
            title = ' '.join(title.split())
            result["title"] = title

        # 提取描述
        snippet_patterns = [
            r'<div[^>]*class="[^"]*b_caption[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*>(.*?)</p>',
        ]
        for snippet_pattern in snippet_patterns:
            snippet_match = re.search(snippet_pattern, match, re.DOTALL | re.IGNORECASE)
            if snippet_match:
                snippet = snippet_match.group(1)
                # 移除 HTML 标签
                snippet = re.sub(r'<[^>]+>', '', snippet)
                snippet = html.unescape(snippet)
                snippet = ' '.join(snippet.split())
                if len(snippet) > 20:
                    result["snippet"] = snippet
                    break

        # 如果有链接，添加到结果中
        if "url" in result and "title" in result:
            if "snippet" not in result:
                result["snippet"] = "无描述"
            results.append(result)

        if len(results) >= max_results:
            break

    return results


class WebSearchTool(BaseTool):
    """
    Bing 网络搜索工具
    使用 Bing 搜索引擎进行网络搜索并返回清洗后的结果
    """

    name = "web_search"
    description = (
        "使用 Bing 搜索引擎进行网络搜索，返回相关的网页标题、链接和描述。适用于查找最新信息、技术文档、新闻等内容。"
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "搜索关键词或问题",
            "required": True,
        },
        "num_results": {
            "type": "integer",
            "description": "返回结果数量，默认 5 条，最多 10 条",
            "required": False,
        },
    }

    async def execute(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """
        执行网络搜索

        Args:
            query: 搜索关键词
            num_results: 返回结果数量（最多 10 条）

        Returns:
            dict: 搜索结果
        """
        try:
            import httpx
        except ImportError:
            return {
                "error": "httpx 库未安装，请运行: pip install httpx",
                "results": [],
                "query": query,
            }

        if not query or not query.strip():
            return {
                "error": "搜索关键词不能为空",
                "results": [],
                "query": query,
            }

        num_results = min(max(1, num_results), 10)

        try:
            search_url = f"https://cn.bing.com/search?q={query}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(search_url, headers=headers)
                response.raise_for_status()

                html_content = response.text

                results = parse_bing_results(html_content, max_results=num_results)

                return {
                    "query": query,
                    "total_results": len(results),
                    "results": results,
                }

        except httpx.TimeoutException:
            return {
                "error": "搜索请求超时，请稍后重试",
                "results": [],
                "query": query,
            }
        except httpx.HTTPStatusError as e:
            return {
                "error": f"搜索请求失败，状态码: {e.response.status_code}",
                "results": [],
                "query": query,
            }
        except Exception as e:
            logger.error(f"网络搜索失败: {e}", exc_info=True)
            return {
                "error": f"搜索失败: {str(e)}",
                "results": [],
                "query": query,
            }
