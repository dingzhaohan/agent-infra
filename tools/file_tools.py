"""
文件操作工具 - 用于分析项目结构、查找关键文件等
"""
import os
import json
from pathlib import Path
from typing import Optional
from tools.terminal_tools import run_shell_command, search_files, read_file_content


def find_dockerfile(repo_path: str) -> dict:
    """
    在仓库中查找 Dockerfile
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        dict: 包含 found, paths, primary_dockerfile
    """
    dockerfile_patterns = [
        "Dockerfile",
        "Dockerfile.*",
        "*.dockerfile",
        "docker/Dockerfile*",
        ".docker/Dockerfile*"
    ]
    
    all_dockerfiles = []
    
    for pattern in dockerfile_patterns:
        result = search_files(repo_path, pattern, max_depth=5)
        if result["success"] and result["files"]:
            all_dockerfiles.extend(result["files"])
    
    # 去重
    all_dockerfiles = list(set(all_dockerfiles))
    
    # 确定主 Dockerfile（优先根目录）
    primary = None
    if all_dockerfiles:
        # 按路径长度排序，优先选择根目录的
        all_dockerfiles.sort(key=lambda x: len(x))
        primary = all_dockerfiles[0]
    
    return {
        "found": len(all_dockerfiles) > 0,
        "paths": all_dockerfiles,
        "primary_dockerfile": primary,
        "count": len(all_dockerfiles)
    }


def find_readme(repo_path: str) -> dict:
    """
    在仓库中查找 README 文件
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        dict: 包含 found, path, content
    """
    readme_patterns = ["README.md", "README.rst", "README.txt", "README", "readme.md"]
    
    for pattern in readme_patterns:
        readme_path = Path(repo_path) / pattern
        if readme_path.exists():
            content_result = read_file_content(str(readme_path), max_lines=300)
            return {
                "found": True,
                "path": str(readme_path),
                "content": content_result.get("content", "") if content_result["success"] else ""
            }
    
    # 搜索子目录
    result = search_files(repo_path, "README*", max_depth=2)
    if result["success"] and result["files"]:
        readme_path = result["files"][0]
        content_result = read_file_content(readme_path, max_lines=300)
        return {
            "found": True,
            "path": readme_path,
            "content": content_result.get("content", "") if content_result["success"] else ""
        }
    
    return {
        "found": False,
        "path": None,
        "content": ""
    }


def find_dependency_files(repo_path: str) -> dict:
    """
    在仓库中查找依赖管理文件
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        dict: 包含 language, files, details
    """
    dependency_patterns = {
        # Python
        "requirements.txt": {"language": "python", "type": "pip"},
        "requirements*.txt": {"language": "python", "type": "pip"},
        "setup.py": {"language": "python", "type": "setuptools"},
        "setup.cfg": {"language": "python", "type": "setuptools"},
        "pyproject.toml": {"language": "python", "type": "pyproject"},
        "Pipfile": {"language": "python", "type": "pipenv"},
        "environment.yml": {"language": "python", "type": "conda"},
        "environment.yaml": {"language": "python", "type": "conda"},
        "conda.yml": {"language": "python", "type": "conda"},
        
        # JavaScript/Node
        "package.json": {"language": "javascript", "type": "npm"},
        "yarn.lock": {"language": "javascript", "type": "yarn"},
        "pnpm-lock.yaml": {"language": "javascript", "type": "pnpm"},
        
        # Rust
        "Cargo.toml": {"language": "rust", "type": "cargo"},
        
        # Go
        "go.mod": {"language": "go", "type": "gomod"},
        
        # Java/Kotlin
        "pom.xml": {"language": "java", "type": "maven"},
        "build.gradle": {"language": "java", "type": "gradle"},
        "build.gradle.kts": {"language": "kotlin", "type": "gradle"},
        
        # C/C++
        "CMakeLists.txt": {"language": "c/c++", "type": "cmake"},
        "Makefile": {"language": "c/c++", "type": "make"},
        "configure.ac": {"language": "c/c++", "type": "autoconf"},
        "meson.build": {"language": "c/c++", "type": "meson"},
        
        # R
        "DESCRIPTION": {"language": "r", "type": "r-package"},
        
        # Julia
        "Project.toml": {"language": "julia", "type": "julia-pkg"},
    }
    
    found_files = []
    languages_detected = set()
    
    for pattern, info in dependency_patterns.items():
        if "*" in pattern:
            result = search_files(repo_path, pattern, max_depth=3)
            if result["success"] and result["files"]:
                for f in result["files"]:
                    found_files.append({
                        "path": f,
                        "language": info["language"],
                        "type": info["type"]
                    })
                    languages_detected.add(info["language"])
        else:
            file_path = Path(repo_path) / pattern
            if file_path.exists():
                found_files.append({
                    "path": str(file_path),
                    "language": info["language"],
                    "type": info["type"]
                })
                languages_detected.add(info["language"])
    
    # 确定主要语言
    primary_language = None
    if languages_detected:
        # 简单的优先级判断
        priority = ["python", "javascript", "rust", "go", "java", "c/c++", "r", "julia"]
        for lang in priority:
            if lang in languages_detected:
                primary_language = lang
                break
    
    return {
        "found": len(found_files) > 0,
        "files": found_files,
        "languages": list(languages_detected),
        "primary_language": primary_language,
        "count": len(found_files)
    }


def find_ci_cd_files(repo_path: str) -> dict:
    """
    查找 CI/CD 配置文件（可能包含构建信息）
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        dict: 包含 found, files
    """
    ci_patterns = [
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
        ".gitlab-ci.yml",
        ".travis.yml",
        "Jenkinsfile",
        "azure-pipelines.yml",
        ".circleci/config.yml",
        "tox.ini",
    ]
    
    found_files = []
    
    for pattern in ci_patterns:
        if "*" in pattern:
            # 处理通配符
            dir_part = str(Path(repo_path) / Path(pattern).parent)
            file_pattern = Path(pattern).name
            result = search_files(dir_part, file_pattern, max_depth=1)
            if result["success"] and result["files"]:
                found_files.extend(result["files"])
        else:
            file_path = Path(repo_path) / pattern
            if file_path.exists():
                found_files.append(str(file_path))
    
    return {
        "found": len(found_files) > 0,
        "files": found_files,
        "count": len(found_files)
    }


def write_dockerfile(
    repo_path: str,
    dockerfile_content: str,
    filename: str = "Dockerfile.generated"
) -> dict:
    """
    写入 Dockerfile 到仓库
    
    Args:
        repo_path: 仓库路径
        dockerfile_content: Dockerfile 内容
        filename: 文件名
    
    Returns:
        dict: 包含 success, path, error
    """
    try:
        dockerfile_path = Path(repo_path) / filename
        
        with open(dockerfile_path, 'w', encoding='utf-8') as f:
            f.write(dockerfile_content)
        
        return {
            "success": True,
            "path": str(dockerfile_path),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "path": None,
            "error": str(e)
        }


def analyze_project_structure(repo_path: str) -> dict:
    """
    分析项目结构，返回综合信息
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        dict: 包含完整的项目分析结果
    """
    # 查找各类文件
    dockerfile_info = find_dockerfile(repo_path)
    readme_info = find_readme(repo_path)
    dependency_info = find_dependency_files(repo_path)
    ci_cd_info = find_ci_cd_files(repo_path)
    
    # 统计文件
    file_stats = {}
    cmd = f'find "{repo_path}" -type f -name "*.py" | wc -l'
    result = run_shell_command(cmd)
    file_stats['python_files'] = int(result['stdout'].strip()) if result['success'] else 0
    
    cmd = f'find "{repo_path}" -type f -name "*.js" -o -name "*.ts" | wc -l'
    result = run_shell_command(cmd)
    file_stats['js_ts_files'] = int(result['stdout'].strip()) if result['success'] else 0
    
    cmd = f'find "{repo_path}" -type f \\( -name "*.c" -o -name "*.cpp" -o -name "*.h" \\) | wc -l'
    result = run_shell_command(cmd)
    file_stats['c_cpp_files'] = int(result['stdout'].strip()) if result['success'] else 0
    
    # 判断部署策略建议
    deployment_strategy = "unknown"
    if dockerfile_info["found"]:
        deployment_strategy = "use_existing_dockerfile"
    elif dependency_info["primary_language"] == "python":
        deployment_strategy = "generate_python_dockerfile"
    elif dependency_info["primary_language"] == "javascript":
        deployment_strategy = "generate_node_dockerfile"
    elif dependency_info["primary_language"] == "rust":
        deployment_strategy = "generate_rust_dockerfile"
    elif dependency_info["primary_language"] == "go":
        deployment_strategy = "generate_go_dockerfile"
    elif dependency_info["primary_language"] in ["c/c++", "java"]:
        deployment_strategy = "generate_compiled_dockerfile"
    elif ci_cd_info["found"]:
        deployment_strategy = "analyze_ci_cd"
    
    return {
        "repo_path": repo_path,
        "has_dockerfile": dockerfile_info["found"],
        "dockerfile_info": dockerfile_info,
        "has_readme": readme_info["found"],
        "readme_info": readme_info,
        "dependency_info": dependency_info,
        "ci_cd_info": ci_cd_info,
        "file_stats": file_stats,
        "deployment_strategy": deployment_strategy,
        "primary_language": dependency_info.get("primary_language")
    }

