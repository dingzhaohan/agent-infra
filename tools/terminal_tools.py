"""
终端操作工具 - 用于执行 shell 命令、git 操作等
"""
import subprocess
import asyncio
from pathlib import Path
from typing import Optional
from config import REPOS_DIR, GIT_CLONE_DEPTH, GIT_TIMEOUT


def run_shell_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 300,
    capture_output: bool = True
) -> dict:
    """
    执行 shell 命令
    
    Args:
        command: 要执行的命令
        cwd: 工作目录
        timeout: 超时时间（秒）
        capture_output: 是否捕获输出
    
    Returns:
        dict: 包含 success, stdout, stderr, return_code
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            timeout=timeout,
            capture_output=capture_output,
            text=True
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"命令超时（{timeout}秒）",
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "return_code": -1
        }


def git_clone(
    repo_url: str,
    target_dir: Optional[str] = None,
    depth: int = GIT_CLONE_DEPTH,
    branch: Optional[str] = None
) -> dict:
    """
    克隆 Git 仓库
    
    Args:
        repo_url: 仓库 URL
        target_dir: 目标目录名（默认为仓库名）
        depth: 克隆深度（1 为浅克隆）
        branch: 指定分支
    
    Returns:
        dict: 包含 success, path, message
    """
    # 从 URL 提取仓库名
    if target_dir is None:
        target_dir = repo_url.rstrip('/').split('/')[-1]
        if target_dir.endswith('.git'):
            target_dir = target_dir[:-4]
    
    full_path = REPOS_DIR / target_dir
    
    # 检查是否已存在
    if full_path.exists():
        return {
            "success": True,
            "path": str(full_path),
            "message": f"仓库已存在: {full_path}"
        }
    
    # 构建 clone 命令
    cmd_parts = ["git", "clone"]
    
    if depth > 0:
        cmd_parts.extend(["--depth", str(depth)])
    
    if branch:
        cmd_parts.extend(["--branch", branch])
    
    cmd_parts.extend([repo_url, str(full_path)])
    cmd = " ".join(cmd_parts)
    
    result = run_shell_command(cmd, timeout=GIT_TIMEOUT)
    
    if result["success"]:
        return {
            "success": True,
            "path": str(full_path),
            "message": f"成功克隆到: {full_path}"
        }
    else:
        error_output = result.get("stderr", "") + result.get("stdout", "")
        
        # 检测需要认证的错误模式
        auth_error_patterns = [
            "Authentication failed",
            "authentication failed",
            "Access denied",
            "access denied",
            "Permission denied",
            "permission denied",
            "fatal: could not read Username",
            "fatal: could not read Password",
            "private repository",
            "Repository not found",  # 有时是私有仓库
            "HTTP Basic: Access denied",
        ]
        
        is_auth_error = any(pattern in error_output for pattern in auth_error_patterns)
        
        if is_auth_error:
            return {
                "success": False,
                "skipped": True,  # 标记为跳过
                "path": "",
                "error": "需要认证访问（私有仓库/GitLab），已跳过",
                "message": f"跳过需要认证的仓库: {repo_url}",
                "details": error_output[:200]  # 保留部分错误信息用于调试
            }
        else:
            return {
                "success": False,
                "path": "",
                "message": f"克隆失败: {result['stderr']}"
            }


def search_files(
    directory: str,
    pattern: str,
    max_depth: int = 5,
    max_results: int = 50
) -> dict:
    """
    在目录中搜索匹配的文件
    
    Args:
        directory: 搜索目录
        pattern: 文件名模式（如 "Dockerfile*", "*.py"）
        max_depth: 最大搜索深度
        max_results: 最大返回数量
    
    Returns:
        dict: 包含 success, files, count
    """
    try:
        # 使用 find 命令搜索
        cmd = f'find "{directory}" -maxdepth {max_depth} -name "{pattern}" -type f 2>/dev/null | head -n {max_results}'
        result = run_shell_command(cmd)
        
        if result["success"]:
            files = [f.strip() for f in result["stdout"].strip().split('\n') if f.strip()]
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        else:
            return {
                "success": False,
                "files": [],
                "count": 0,
                "error": result["stderr"]
            }
    except Exception as e:
        return {
            "success": False,
            "files": [],
            "count": 0,
            "error": str(e)
        }


def read_file_content(
    file_path: str,
    max_lines: int = 500,
    encoding: str = "utf-8"
) -> dict:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        max_lines: 最大读取行数
        encoding: 文件编码
    
    Returns:
        dict: 包含 success, content, lines_read, truncated
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "content": "",
                "error": f"文件不存在: {file_path}"
            }
        
        if not path.is_file():
            return {
                "success": False,
                "content": "",
                "error": f"不是文件: {file_path}"
            }
        
        # 读取文件
        with open(path, 'r', encoding=encoding, errors='replace') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)
            
            content = ''.join(lines)
            truncated = i >= max_lines - 1
        
        return {
            "success": True,
            "content": content,
            "lines_read": len(lines),
            "truncated": truncated
        }
    except Exception as e:
        return {
            "success": False,
            "content": "",
            "error": str(e)
        }

