"""
Web 搜索工具 - 用于搜索文档、解决方案等
"""
import requests
import logging
from typing import Optional, List, Dict
from config import SEARCH_KEY, SEARCH_BASE_URL

logger = logging.getLogger(__name__)


def web_search(
    query: str,
    count: int = 5,
    timeout: int = 10
) -> dict:
    """
    使用 SearchAPI 进行 Google 搜索
    
    Args:
        query: 搜索关键词
        count: 返回结果数量（最多10条）
        timeout: 请求超时时间（秒）
    
    Returns:
        dict: 包含 success, results, message
    """
    if not SEARCH_KEY:
        return {
            "success": False,
            "results": [],
            "message": "未配置 SEARCH_KEY"
        }
    
    url = f"{SEARCH_BASE_URL}api/v1/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SEARCH_KEY,
        "num": min(count, 10)  # 最多10条
    }
    
    try:
        response = requests.get(
            url,
            params=params,
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 提取有用的信息
            results = []
            organic_results = data.get("organic_results", [])
            
            for item in organic_results[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            
            logger.info(f"搜索成功: {query}, 找到 {len(results)} 条结果")
            
            return {
                "success": True,
                "results": results,
                "message": f"找到 {len(results)} 条结果",
                "raw_data": data  # 保留原始数据
            }
        else:
            logger.warning(f"搜索失败. Status: {response.status_code}")
            return {
                "success": False,
                "results": [],
                "message": f"搜索失败: HTTP {response.status_code}"
            }
            
    except requests.Timeout:
        logger.warning(f"搜索超时: {query}")
        return {
            "success": False,
            "results": [],
            "message": f"搜索超时（{timeout}秒）"
        }
    except Exception as e:
        logger.warning(f"搜索异常: {e}")
        return {
            "success": False,
            "results": [],
            "message": f"搜索异常: {str(e)}"
        }


def search_installation_guide(
    tool_name: str,
    language: str = ""
) -> dict:
    """
    搜索工具的安装指南
    
    Args:
        tool_name: 工具名称
        language: 主要编程语言（可选）
    
    Returns:
        dict: 搜索结果
    """
    # 构建更精确的搜索查询
    query_parts = [tool_name, "installation guide", "how to install"]
    if language:
        query_parts.append(language)
    
    query = " ".join(query_parts)
    
    return web_search(query, count=5)


def search_error_solution(
    error_message: str,
    context: str = ""
) -> dict:
    """
    搜索错误解决方案
    
    Args:
        error_message: 错误信息
        context: 上下文信息（如工具名称、操作系统等）
    
    Returns:
        dict: 搜索结果
    """
    # 清理错误信息（去掉路径等特定信息）
    cleaned_error = error_message.split('\n')[0][:200]  # 只取第一行，最多200字符
    
    query_parts = [cleaned_error]
    if context:
        query_parts.append(context)
    query_parts.append("solution")
    
    query = " ".join(query_parts)
    
    return web_search(query, count=3)


def search_dockerfile_example(
    tool_name: str,
    language: str = ""
) -> dict:
    """
    搜索 Dockerfile 示例
    
    Args:
        tool_name: 工具名称
        language: 主要编程语言（可选）
    
    Returns:
        dict: 搜索结果
    """
    query_parts = [tool_name, "dockerfile", "example"]
    if language:
        query_parts.append(language)
    
    query = " ".join(query_parts)
    
    return web_search(query, count=3)


def format_search_results_for_llm(results: List[Dict]) -> str:
    """
    将搜索结果格式化为适合 LLM 阅读的文本
    
    Args:
        results: 搜索结果列表
    
    Returns:
        str: 格式化后的文本
    """
    if not results:
        return "未找到相关结果"
    
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. **{result['title']}**")
        formatted.append(f"   链接: {result['link']}")
        formatted.append(f"   摘要: {result['snippet']}")
        formatted.append("")
    
    return "\n".join(formatted)

