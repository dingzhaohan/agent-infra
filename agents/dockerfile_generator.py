"""
Dockerfile 生成 Agent - 根据分析结果生成 Dockerfile
"""
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from typing import Optional
import json

from config import OPENAI_MODEL, OPENAI_API_BASE
from tools.file_tools import write_dockerfile
from tools.terminal_tools import read_file_content


# Dockerfile 模板
DOCKERFILE_TEMPLATES = {
    "python_pip": '''# 基于 Python 官方镜像
FROM python:{python_version}-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 设置入口点（根据实际情况修改）
# CMD ["python", "main.py"]
''',

    "python_conda": '''# 基于 Conda 镜像
FROM continuumio/miniconda3:latest

# 设置工作目录
WORKDIR /app

# 复制 conda 环境文件
COPY environment.yml .

# 创建 conda 环境
RUN conda env create -f environment.yml && \\
    conda clean -afy

# 激活环境
SHELL ["conda", "run", "-n", "{env_name}", "/bin/bash", "-c"]

# 复制项目文件
COPY . .

# 设置入口点
# CMD ["conda", "run", "-n", "{env_name}", "python", "main.py"]
''',

    "python_poetry": '''# 基于 Python 官方镜像
FROM python:{python_version}-slim

# 安装 Poetry
ENV POETRY_VERSION=1.7.1
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl \\
    build-essential \\
    && curl -sSL https://install.python-poetry.org | python3 - \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY pyproject.toml poetry.lock* ./

# 安装依赖
RUN poetry config virtualenvs.create false \\
    && poetry install --no-interaction --no-ansi --no-root

# 复制项目文件
COPY . .

# 安装项目
RUN poetry install --no-interaction --no-ansi

# 设置入口点
# CMD ["python", "-m", "your_module"]
''',

    "node_npm": '''# 基于 Node.js 官方镜像
FROM node:{node_version}-alpine

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm ci --only=production

# 复制项目文件
COPY . .

# 构建项目（如果需要）
# RUN npm run build

# 暴露端口
EXPOSE 3000

# 启动命令
CMD ["npm", "start"]
''',

    "rust_cargo": '''# 构建阶段
FROM rust:{rust_version} as builder

WORKDIR /app

# 复制项目文件
COPY . .

# 构建发布版本
RUN cargo build --release

# 运行阶段
FROM debian:bookworm-slim

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制二进制文件
COPY --from=builder /app/target/release/{binary_name} /app/

# 设置入口点
CMD ["./{binary_name}"]
''',

    "go_mod": '''# 构建阶段
FROM golang:{go_version}-alpine as builder

WORKDIR /app

# 复制 go.mod 和 go.sum
COPY go.mod go.sum* ./

# 下载依赖
RUN go mod download

# 复制源代码
COPY . .

# 构建
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

# 运行阶段
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /app/main .

CMD ["./main"]
''',

    "cpp_cmake": '''# 构建阶段
FROM ubuntu:22.04 as builder

# 安装构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    cmake \\
    git \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制项目文件
COPY . .

# 构建
RUN mkdir build && cd build && \\
    cmake .. && \\
    make -j$(nproc)

# 运行阶段
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \\
    libstdc++6 \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制二进制文件（根据实际情况修改路径）
# COPY --from=builder /app/build/bin/* /app/

# 设置入口点
# CMD ["./your_binary"]
''',

    "scientific_python": '''# 科学计算 Python 环境
FROM python:{python_version}-slim

# 安装系统级科学计算依赖
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    gfortran \\
    libopenblas-dev \\
    liblapack-dev \\
    libhdf5-dev \\
    libffi-dev \\
    git \\
    wget \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY requirements.txt* setup.py* pyproject.toml* ./

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \\
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi && \\
    if [ -f setup.py ]; then pip install --no-cache-dir -e .; fi

# 复制项目文件
COPY . .

# 可选：安装项目本身
# RUN pip install --no-cache-dir -e .
''',
}


@tool
def get_dockerfile_template(template_name: str) -> str:
    """
    获取 Dockerfile 模板
    
    Args:
        template_name: 模板名称 (python_pip, python_conda, node_npm, rust_cargo, go_mod, cpp_cmake, scientific_python)
    
    Returns:
        模板内容
    """
    if template_name in DOCKERFILE_TEMPLATES:
        return DOCKERFILE_TEMPLATES[template_name]
    else:
        return f"未找到模板: {template_name}\n可用模板: {list(DOCKERFILE_TEMPLATES.keys())}"


@tool
def save_dockerfile(repo_path: str, content: str, filename: str = "Dockerfile.generated") -> str:
    """
    保存生成的 Dockerfile 到仓库目录
    
    Args:
        repo_path: 仓库路径
        content: Dockerfile 内容
        filename: 文件名
    
    Returns:
        保存结果
    """
    result = write_dockerfile(repo_path, content, filename)
    return json.dumps(result, ensure_ascii=False)


@tool
def read_existing_dockerfile(dockerfile_path: str) -> str:
    """
    读取现有的 Dockerfile 内容
    
    Args:
        dockerfile_path: Dockerfile 路径
    
    Returns:
        Dockerfile 内容
    """
    result = read_file_content(dockerfile_path, max_lines=200)
    if result["success"]:
        return result["content"]
    else:
        return f"错误: {result.get('error', '无法读取文件')}"


@tool
def read_dependency_file(file_path: str) -> str:
    """
    读取依赖文件内容（requirements.txt, package.json 等）
    
    Args:
        file_path: 依赖文件路径
    
    Returns:
        文件内容
    """
    result = read_file_content(file_path, max_lines=200)
    if result["success"]:
        return result["content"]
    else:
        return f"错误: {result.get('error', '无法读取文件')}"


def create_dockerfile_generator_agent() -> Agent:
    """
    创建 Dockerfile 生成 Agent
    
    该 Agent 负责:
    1. 根据项目分析结果选择合适的模板
    2. 自定义和优化 Dockerfile
    3. 处理特殊依赖和配置
    """
    return Agent(
        name="DockerfileGenerator",
        model=OpenAIChat(id=OPENAI_MODEL, base_url=OPENAI_API_BASE or None),
        tools=[
            get_dockerfile_template,
            save_dockerfile,
            read_existing_dockerfile,
            read_dependency_file,
        ],
        description="Dockerfile 生成专家，根据项目分析生成最优的 Dockerfile",
        instructions=[
            "你是一个 Docker 和容器化专家，专注于为科学计算工具生成高质量的 Dockerfile。",
            "",
            "## 生成原则",
            "1. 优先使用官方基础镜像",
            "2. 遵循 Docker 最佳实践（多阶段构建、层缓存优化）",
            "3. 最小化镜像大小",
            "4. 确保安全性（非 root 用户、最小权限）",
            "5. 添加清晰的注释",
            "",
            "## 科学计算工具特殊考虑",
            "- 可能需要 Fortran 编译器 (gfortran)",
            "- 可能需要 BLAS/LAPACK 库",
            "- 可能需要 HDF5 支持",
            "- 可能需要 MPI 并行支持",
            "- GPU 支持（如需要，使用 NVIDIA 基础镜像）",
            "",
            "## 输出要求",
            "生成完整、可直接使用的 Dockerfile，包含：",
            "- 基础镜像选择说明",
            "- 系统依赖安装",
            "- 项目依赖安装",
            "- 合适的入口点配置",
            "- 必要的环境变量",
        ],
        show_tool_calls=True,
        markdown=True,
    )


class DockerfileGenerationResult:
    """Dockerfile 生成结果"""
    
    def __init__(
        self,
        tool_name: str,
        dockerfile_path: str,
        dockerfile_content: str,
        base_image: str,
        template_used: str = None,
        generation_success: bool = True,
        notes: str = None,
        error_message: str = None
    ):
        self.tool_name = tool_name
        self.dockerfile_path = dockerfile_path
        self.dockerfile_content = dockerfile_content
        self.base_image = base_image
        self.template_used = template_used
        self.generation_success = generation_success
        self.notes = notes
        self.error_message = error_message
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "dockerfile_path": self.dockerfile_path,
            "base_image": self.base_image,
            "template_used": self.template_used,
            "generation_success": self.generation_success,
            "notes": self.notes,
            "error_message": self.error_message
        }

