"""
配置文件 - 用于管理工作流的各种配置参数
"""
import os
from pathlib import Path
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Docker 配置
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "600"))  # 10分钟
DOCKER_MEMORY_LIMIT = os.getenv("DOCKER_MEMORY_LIMIT", "4g")

# Git 配置
GIT_CLONE_DEPTH = int(os.getenv("GIT_CLONE_DEPTH", "1"))  # 浅克隆
GIT_TIMEOUT = int(os.getenv("GIT_TIMEOUT", "300"))  # 5分钟

# 工作流配置
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_CONCURRENT_TOOLS = int(os.getenv("MAX_CONCURRENT_TOOLS", "2"))

