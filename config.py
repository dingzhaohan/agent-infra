"""
配置文件 - 用于管理工作流的各种配置参数
"""
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 基础路径配置
BASE_DIR = Path(__file__).parent
REPOS_DIR = BASE_DIR / "repos"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"

# 确保目录存在
REPOS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# LLM 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")  # 自定义 API 地址，留空则使用官方地址
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Docker 配置
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "600"))  # 10分钟
DOCKER_MEMORY_LIMIT = os.getenv("DOCKER_MEMORY_LIMIT", "4g")

# Git 配置
GIT_CLONE_DEPTH = int(os.getenv("GIT_CLONE_DEPTH", "1"))  # 浅克隆
GIT_TIMEOUT = int(os.getenv("GIT_TIMEOUT", "300"))  # 5分钟

# Git 认证配置（用于克隆私有仓库）
# 注意：用户名和密码会被 URL 编码，可以包含特殊字符（如 @ 符号）
# 只对需要认证的域名（如 GitLab）注入认证信息，GitHub 等公开仓库不会注入
GIT_USERNAME = os.getenv("GIT_USERNAME", "")  # Git 用户名（如: wangyi01@dp.tech）
GIT_PASSWORD = os.getenv("GIT_PASSWORD", "")  # Git 密码或访问令牌

# 工作流配置
# MAX_RETRIES: Dockerfile 生成和验证的最大重试次数
# - 当 verifier 检测到问题时，会调用 generator 修复 Dockerfile
# - 然后重新验证，最多重试 MAX_RETRIES 次
# - 默认 10 次，可以通过环境变量 MAX_RETRIES 配置
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))

# MAX_CONCURRENT_TOOLS: 并发处理工具的最大数量
# - 在批量部署模式下使用
# - 默认 2，可以通过环境变量 MAX_CONCURRENT_TOOLS 配置
MAX_CONCURRENT_TOOLS = int(os.getenv("MAX_CONCURRENT_TOOLS", "2"))

# Docker 镜像配置
# DOCKER_REGISTRY: Docker 镜像仓库地址
# DOCKER_NAMESPACE: Docker 镜像命名空间
# DOCKER_TAG: Docker 镜像标签（默认使用时间戳，避免缓存问题）
DOCKER_REGISTRY = os.getenv("DOCKER_REGISTRY", "registry.dp.tech")
DOCKER_NAMESPACE = os.getenv("DOCKER_NAMESPACE", "davinci")

# 生成时间戳标签（格式: 20251209-143022）
# 如果环境变量中设置了 DOCKER_TAG，则使用环境变量的值
_default_tag = datetime.now().strftime("%Y%m%d-%H%M%S")
DOCKER_TAG = os.getenv("DOCKER_TAG", _default_tag)

