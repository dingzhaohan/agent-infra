"""
仓库分析 Agent - 负责分析开源仓库结构并确定部署策略
"""
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from typing import Optional
import json

from config import OPENAI_MODEL, OPENAI_API_BASE, REPOS_DIR
from tools.terminal_tools import git_clone, read_file_content, search_files
from tools.file_tools import (
    analyze_project_structure,
    find_dockerfile,
    find_readme,
    find_dependency_files,
    find_ci_cd_files
)


# 定义 Agno 工具函数
@tool
def clone_repository(repo_url: str, target_name: Optional[str] = None) -> str:
    """
    克隆 Git 仓库到本地工作目录
    
    Args:
        repo_url: Git 仓库 URL
        target_name: 目标目录名（可选）
    
    Returns:
        克隆结果的 JSON 字符串
    """
    result = git_clone(repo_url, target_name)
    return json.dumps(result, ensure_ascii=False)


@tool
def analyze_repo_structure(repo_path: str) -> str:
    """
    分析仓库结构，查找 Dockerfile、README、依赖文件等
    
    Args:
        repo_path: 仓库本地路径
    
    Returns:
        分析结果的 JSON 字符串
    """
    result = analyze_project_structure(repo_path)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def read_file(file_path: str, max_lines: int = 300) -> str:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        max_lines: 最大读取行数
    
    Returns:
        文件内容或错误信息
    """
    result = read_file_content(file_path, max_lines=max_lines)
    if result["success"]:
        return result["content"]
    else:
        return f"错误: {result.get('error', '无法读取文件')}"


@tool
def search_repo_files(repo_path: str, pattern: str) -> str:
    """
    在仓库中搜索文件
    
    Args:
        repo_path: 仓库路径
        pattern: 文件名模式（如 "*.py", "Dockerfile*"）
    
    Returns:
        搜索结果的 JSON 字符串
    """
    result = search_files(repo_path, pattern)
    return json.dumps(result, ensure_ascii=False)


@tool
def get_dockerfile_locations(repo_path: str) -> str:
    """
    查找仓库中所有 Dockerfile 的位置
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        Dockerfile 位置信息的 JSON 字符串
    """
    result = find_dockerfile(repo_path)
    return json.dumps(result, ensure_ascii=False)


@tool
def get_readme_content(repo_path: str) -> str:
    """
    获取仓库的 README 内容
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        README 内容或未找到信息
    """
    result = find_readme(repo_path)
    if result["found"]:
        return f"README 路径: {result['path']}\n\n内容:\n{result['content']}"
    else:
        return "未找到 README 文件"


@tool
def get_dependency_info(repo_path: str) -> str:
    """
    获取仓库的依赖管理信息
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        依赖信息的 JSON 字符串
    """
    result = find_dependency_files(repo_path)
    return json.dumps(result, ensure_ascii=False)


@tool
def get_ci_cd_info(repo_path: str) -> str:
    """
    获取仓库的 CI/CD 配置信息
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        CI/CD 信息的 JSON 字符串
    """
    result = find_ci_cd_files(repo_path)
    return json.dumps(result, ensure_ascii=False)


def create_repo_analyzer_agent() -> Agent:
    """
    创建仓库分析 Agent
    
    该 Agent 负责:
    1. 克隆仓库到本地
    2. 分析项目结构
    3. 确定最佳部署策略
    """
    return Agent(
        name="RepoAnalyzer",
        model=OpenAIChat(id=OPENAI_MODEL, base_url=OPENAI_API_BASE or None),
        tools=[
            clone_repository,
            analyze_repo_structure,
            read_file,
            search_repo_files,
            get_dockerfile_locations,
            get_readme_content,
            get_dependency_info,
            get_ci_cd_info,
        ],
        description="开源仓库分析专家，负责分析仓库结构并确定部署策略",
        instructions=[
            "你是一个专业的软件工程师，专注于分析开源项目并确定最佳的 Docker 部署策略。",
            "",
            "## 分析步骤",
            "1. 首先克隆仓库到本地工作目录",
            "2. 分析项目结构，查找 Dockerfile、README、依赖文件",
            "3. 如果有现成的 Dockerfile，记录其位置",
            "4. 如果没有 Dockerfile，分析 README 和依赖文件确定技术栈",
            "5. 检查 CI/CD 配置获取构建提示",
            "",
            "## 输出格式",
            "请以结构化的方式输出分析结果，包括：",
            "- 仓库基本信息",
            "- 是否有现成的 Dockerfile",
            "- 主要编程语言和技术栈",
            "- 依赖管理方式",
            "- 推荐的部署策略",
            "- 需要注意的特殊配置或依赖",
        ],
        markdown=True,
        debug_mode=True,  # 显示调试信息
    )


# 分析结果数据结构
class RepoAnalysisResult:
    """仓库分析结果"""
    
    def __init__(
        self,
        tool_name: str,
        repo_url: str,
        local_path: str,
        has_dockerfile: bool = False,
        dockerfile_paths: list = None,
        primary_language: str = None,
        dependency_files: list = None,
        readme_content: str = None,
        deployment_strategy: str = "unknown",
        special_notes: str = None,
        analysis_success: bool = True,
        error_message: str = None
    ):
        self.tool_name = tool_name
        self.repo_url = repo_url
        self.local_path = local_path
        self.has_dockerfile = has_dockerfile
        self.dockerfile_paths = dockerfile_paths or []
        self.primary_language = primary_language
        self.dependency_files = dependency_files or []
        self.readme_content = readme_content
        self.deployment_strategy = deployment_strategy
        self.special_notes = special_notes
        self.analysis_success = analysis_success
        self.error_message = error_message
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "repo_url": self.repo_url,
            "local_path": self.local_path,
            "has_dockerfile": self.has_dockerfile,
            "dockerfile_paths": self.dockerfile_paths,
            "primary_language": self.primary_language,
            "dependency_files": self.dependency_files,
            "deployment_strategy": self.deployment_strategy,
            "special_notes": self.special_notes,
            "analysis_success": self.analysis_success,
            "error_message": self.error_message
        }
    
    def __repr__(self):
        return f"RepoAnalysisResult(tool={self.tool_name}, strategy={self.deployment_strategy})"

