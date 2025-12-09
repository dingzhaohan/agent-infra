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
from tools.web_search import (
    web_search,
    search_dockerfile_example,
    search_error_solution,
    format_search_results_for_llm
)


# Dockerfile 模板
DOCKERFILE_TEMPLATES = {
    "python_pip": '''# 基于 Python 官方镜像
FROM python:{python_version}-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括 bash）
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    git \\
    bash \\
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 默认启动 bash，方便交互式使用
# 如需运行特定程序，使用: docker run image python main.py
CMD ["/bin/bash"]
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

# 复制项目文件
COPY . .

# 配置 bash 以自动激活 conda 环境
RUN echo "source activate {env_name}" >> ~/.bashrc

# 默认启动 bash（会自动激活 conda 环境）
CMD ["/bin/bash"]
''',

    "python_poetry": '''# 基于 Python 官方镜像
FROM python:{python_version}-slim

# 安装 Poetry 和 bash
ENV POETRY_VERSION=1.7.1
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl \\
    build-essential \\
    bash \\
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

# 默认启动 bash
CMD ["/bin/bash"]
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
    bash \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制二进制文件（根据实际情况修改路径）
# COPY --from=builder /app/build/bin/* /app/

# 默认启动 bash，方便交互式使用
CMD ["/bin/bash"]
''',

    "scientific_python": '''# 科学计算 Python 环境
FROM python:{python_version}-slim

# 安装系统级科学计算依赖和 bash
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    gfortran \\
    gcc \\
    g++ \\
    make \\
    cmake \\
    pkg-config \\
    libopenblas-dev \\
    liblapack-dev \\
    libhdf5-dev \\
    libffi-dev \\
    git \\
    wget \\
    curl \\
    bash \\
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

# 默认使用 bash，方便用户交互式使用
CMD ["/bin/bash"]
''',
    
    "scientific_computing_fortran": '''# 科学计算环境（Fortran/C/C++）- 基于最佳实践
FROM ubuntu:22.04

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础工具和编译器
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    gfortran \\
    gcc \\
    g++ \\
    make \\
    cmake \\
    pkg-config \\
    build-essential \\
    software-properties-common \\
    supervisor \\
    net-tools \\
    openssh-server \\
    lsb-release \\
    curl \\
    unzip \\
    emacs \\
    vim \\
    libgomp1 \\
    tree \\
    zsh \\
    wget \\
    git \\
    htop \\
    ncdu \\
    && rm -rf /var/lib/apt/lists/*

# 安装 MPI 支持
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    openmpi-bin \\
    libopenmpi-dev \\
    && rm -rf /var/lib/apt/lists/*

# 安装科学计算库
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    libopenblas-dev \\
    liblapack-dev \\
    libhdf5-openmpi-dev \\
    hdf5-tools \\
    libfftw3-dev \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# 设置环境变量
ENV MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi
ENV PATH=$MPI_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$MPI_HOME/lib:$LD_LIBRARY_PATH

# 默认使用 bash
CMD ["/bin/bash"]
''',

    "scientific_computing_intel": '''# 科学计算环境 - Intel OneAPI 工具链
FROM ubuntu:22.04

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础工具
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    wget \\
    curl \\
    build-essential \\
    software-properties-common \\
    supervisor \\
    net-tools \\
    openssh-server \\
    lsb-release \\
    unzip \\
    cmake \\
    emacs \\
    vim \\
    libgomp1 \\
    tree \\
    zsh \\
    git \\
    htop \\
    ncdu \\
    bash \\
    && rm -rf /var/lib/apt/lists/*

# 安装 Intel OneAPI BaseKit (MKL, VTune)
RUN wget https://hpc-profiling-example.oss-cn-beijing.aliyuncs.com/software/intel/l_BaseKit_p_2022.1.2.146_offline.sh && \\
    bash l_BaseKit_p_2022.1.2.146_offline.sh -a -s --eula accept --components intel.oneapi.lin.mkl.devel:intel.oneapi.lin.vtune && \\
    rm -rf l_BaseKit_p_2022.1.2.146_offline.sh

# 安装 Intel OneAPI HPCKit (ifort, icx, MPI)
RUN wget https://hpc-profiling-example.oss-cn-beijing.aliyuncs.com/software/intel/l_HPCKit_p_2022.1.2.117_offline.sh && \\
    bash l_HPCKit_p_2022.1.2.117_offline.sh -a -s --eula accept --components intel.oneapi.lin.ifort-compiler:intel.oneapi.lin.dpcpp-cpp-compiler-pro:intel.oneapi.lin.mpi.devel && \\
    rm -rf l_HPCKit_p_2022.1.2.117_offline.sh

WORKDIR /workspace

# 设置环境变量
ENV INTEL_HOME=/opt/intel/oneapi
RUN echo "source /opt/intel/oneapi/setvars.sh" >> ~/.bashrc && \\
    echo "ulimit -s unlimited && ulimit -m unlimited" >> ~/.bashrc

# 默认使用 bash（会自动加载 Intel 环境）
CMD ["/bin/bash", "-l"]
''',
    
    # CMake 元仓库模板（用于 SuiteSparse 等）
    'cmake_metapackage': '''
# Dockerfile for CMake meta-package (e.g., SuiteSparse)
# Meta-package: repository containing multiple sub-packages built together
# Build approach: use root-level CMakeLists.txt to build entire suite

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \\
    GIT_TERMINAL_PROMPT=0
SHELL ["/bin/bash", "-c"]

# Install complete scientific computing toolchain
# Includes: C/C++/Fortran compilers, build tools, MPI, BLAS/LAPACK, HDF5, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \\
    bash ca-certificates curl wget git \\
    # Core build toolchain
    build-essential gcc g++ gfortran make cmake pkg-config autoconf automake libtool \\
    # MPI (OpenMPI)
    openmpi-bin libopenmpi-dev \\
    # Linear algebra and numerics
    libopenblas-dev liblapack-dev \\
    # HDF5 with MPI support
    libhdf5-openmpi-dev hdf5-tools \\
    # Additional scientific libraries
    libfftw3-dev libmetis-dev \\
    # Utilities
    vim tree htop ncdu \\
    && rm -rf /var/lib/apt/lists/*

# Set MPI environment variables
ENV MPICC=mpicc \\
    MPICXX=mpicxx \\
    MPIFORT=mpifort \\
    MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi

# Copy entire repository (meta-package with all sub-packages)
WORKDIR /src/metapackage
COPY . /src/metapackage

# Build entire meta-package using CMake
# Strategy:
# 1. Create out-of-source build directory
# 2. Configure with cmake (auto-detects all sub-packages)
# 3. Build with all available cores
# 4. Install to /usr/local
# 5. Update library cache
RUN set -eux; \\
    mkdir -p build && cd build && \\
    cmake .. \\
        -DCMAKE_BUILD_TYPE=Release \\
        -DCMAKE_INSTALL_PREFIX=/usr/local \\
        -DBUILD_SHARED_LIBS=ON \\
        -DBUILD_STATIC_LIBS=OFF && \\
    cmake --build . -j"$(nproc)" && \\
    cmake --install . && \\
    ldconfig

# Create non-root user for safer operation
ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} && \\
    useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME}

# Set library and pkg-config paths
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib/pkgconfig \\
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib:/usr/lib/x86_64-linux-gnu

WORKDIR /workspace
USER ${USERNAME}

# Default to interactive bash shell
CMD ["/bin/bash"]
''',
}


@tool
def check_if_metapackage(repo_path: str) -> str:
    """
    通用的元仓库检测（不依赖硬编码的包名）
    
    元仓库特征：
    1. 根目录有 CMakeLists.txt 或 Makefile
    2. 包含多个子目录，每个都有自己的构建文件
    3. 根目录的构建文件引用这些子目录
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        检查结果的 JSON 字符串
    """
    from pathlib import Path
    import re
    
    repo_path_obj = Path(repo_path).resolve()
    
    # 1. 检查根目录构建文件
    root_cmake_path = repo_path_obj / "CMakeLists.txt"
    root_makefile_path = repo_path_obj / "Makefile"
    
    has_root_cmake = root_cmake_path.exists()
    has_root_makefile = root_makefile_path.exists()
    
    if not (has_root_cmake or has_root_makefile):
        return json.dumps({
            "is_metapackage": False,
            "reason": "根目录没有构建文件"
        }, ensure_ascii=False, indent=2)
    
    # 2. 扫描所有一级子目录，查找有构建文件的子包
    subpackages_with_cmake = []
    subpackages_with_makefile = []
    
    try:
        for item in repo_path_obj.iterdir():
            if not item.is_dir():
                continue
            
            # 跳过常见的非子包目录
            skip_dirs = {
                '.git', '.github', '.gitlab', '.vscode', '.idea',
                'build', 'builds', '_build', 'cmake-build-debug', 'cmake-build-release',
                'dist', 'out', 'output', 'bin', 'lib', 'include',
                'docs', 'doc', 'documentation', 'examples', 'tests', 'test',
                'node_modules', 'venv', '.venv', 'env', '__pycache__',
                'target', '.mvn', '.gradle'
            }
            
            if item.name.lower() in skip_dirs or item.name.startswith('.'):
                continue
            
            # 检查是否有 CMakeLists.txt
            if (item / "CMakeLists.txt").exists():
                subpackages_with_cmake.append(item.name)
            
            # 检查是否有 Makefile
            if (item / "Makefile").exists():
                subpackages_with_makefile.append(item.name)
    except Exception as e:
        return json.dumps({
            "is_metapackage": False,
            "error": f"扫描子目录失败: {str(e)}"
        }, ensure_ascii=False, indent=2)
    
    # 合并有构建文件的子包列表
    all_subpackages = sorted(set(subpackages_with_cmake + subpackages_with_makefile))
    
    # 3. 分析根目录的构建文件，验证是否引用子目录
    references_subdirs = False
    referenced_dirs = []
    
    if has_root_cmake:
        try:
            cmake_content = root_cmake_path.read_text(encoding='utf-8', errors='ignore')
            # 查找 add_subdirectory() 命令
            subdirs = re.findall(r'add_subdirectory\s*\(\s*([^)]+)\s*\)', cmake_content, re.IGNORECASE)
            referenced_dirs.extend([d.strip().strip('"').strip("'") for d in subdirs])
            if subdirs:
                references_subdirs = True
        except:
            pass
    
    if has_root_makefile:
        try:
            makefile_content = root_makefile_path.read_text(encoding='utf-8', errors='ignore')
            # 查找 cd xxx && make 或 $(MAKE) -C xxx 模式
            cd_patterns = re.findall(r'cd\s+([^\s;&|]+)\s+&&', makefile_content)
            make_c_patterns = re.findall(r'\$\(MAKE\)\s+-C\s+([^\s;&|]+)', makefile_content)
            referenced_dirs.extend(cd_patterns + make_c_patterns)
            if cd_patterns or make_c_patterns:
                references_subdirs = True
        except:
            pass
    
    referenced_dirs = sorted(set(d.strip() for d in referenced_dirs if d.strip()))
    
    # 4. 判断是否是元仓库
    # 标准：
    # - 有根构建文件
    # - 有多个（>= 3）子包目录有构建文件
    # - 或者根构建文件引用了多个子目录
    subpackage_count = len(all_subpackages)
    referenced_count = len(referenced_dirs)
    
    is_meta = (
        (has_root_cmake or has_root_makefile) and
        (subpackage_count >= 3 or (references_subdirs and referenced_count >= 3))
    )
    
    result = {
        "is_metapackage": is_meta,
        "has_root_cmake": has_root_cmake,
        "has_root_makefile": has_root_makefile,
        "subpackages_with_build_files": all_subpackages,
        "subpackage_count": subpackage_count,
        "references_subdirs_in_root": references_subdirs,
        "referenced_directories": referenced_dirs[:10] if len(referenced_dirs) > 10 else referenced_dirs,  # 限制输出
        "referenced_count": referenced_count,
        "detection_logic": (
            f"检测到 {subpackage_count} 个子包有构建文件，"
            f"根构建文件引用了 {referenced_count} 个子目录"
        ),
        "recommendation": (
            "使用 cmake_metapackage 模板从根目录构建所有子包" 
            if is_meta else "使用常规模板"
        )
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def get_dockerfile_template(template_name: str) -> str:
    """
    获取 Dockerfile 模板
    
    Args:
        template_name: 模板名称
        可用模板:
        - python_pip: Python pip 项目
        - python_conda: Python conda 项目
        - python_poetry: Python poetry 项目
        - node_npm: Node.js npm 项目
        - rust_cargo: Rust cargo 项目
        - go_mod: Go modules 项目
        - cmake_metapackage: CMake 元仓库（如 SuiteSparse）
        - cpp_cmake: C++ CMake 项目
        - scientific_python: 科学计算 Python 环境
        - scientific_computing_fortran: 科学计算 Fortran/C/C++ 环境（包含 MPI、HDF5）
        - scientific_computing_intel: 科学计算 Intel OneAPI 环境（包含 ifort、MKL）
    
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


@tool
def patch_dockerfile(
    dockerfile_path: str,
    issue_description: str,
    fix_instructions: str
) -> str:
    """
    根据验证失败的问题修复 Dockerfile
    
    Args:
        dockerfile_path: Dockerfile 路径
        issue_description: 问题描述（如"缺少 gfortran 编译器"）
        fix_instructions: 修复指导（如"需要添加 gfortran 到依赖安装中"）
    
    Returns:
        修复结果 JSON
    """
    # 读取当前 Dockerfile
    result = read_file_content(dockerfile_path)
    if not result["success"]:
        return json.dumps({
            "success": False,
            "error": f"无法读取 Dockerfile: {result.get('error')}"
        }, ensure_ascii=False)
    
    current_content = result["content"]
    
    # 返回当前内容和修复建议，让 agent 决定如何修改
    return json.dumps({
        "success": True,
        "current_content": current_content,
        "issue": issue_description,
        "fix_instructions": fix_instructions,
        "message": "请分析当前 Dockerfile 并根据问题和修复指导生成新的版本，使用 save_dockerfile 保存"
    }, ensure_ascii=False)


@tool
def search_web_for_dockerfile(query: str, count: int = 3) -> str:
    """
    在网上搜索 Dockerfile 示例和最佳实践
    
    Args:
        query: 搜索关键词
        count: 返回结果数量（默认3条）
    
    Returns:
        格式化的搜索结果
    
    示例用法：
        search_web_for_dockerfile("LAMMPS dockerfile example")
        search_web_for_dockerfile("python scientific computing dockerfile best practices")
    """
    result = web_search(query, count)
    
    if result["success"]:
        formatted = format_search_results_for_llm(result["results"])
        return f"找到 Dockerfile 相关资料：\n\n{formatted}"
    else:
        return f"搜索失败: {result['message']}"


@tool
def search_dockerfile_examples(tool_name: str, language: str = "") -> str:
    """
    搜索特定工具的 Dockerfile 示例
    
    Args:
        tool_name: 工具名称
        language: 主要编程语言（可选）
    
    Returns:
        格式化的搜索结果
    """
    result = search_dockerfile_example(tool_name, language)
    
    if result["success"]:
        formatted = format_search_results_for_llm(result["results"])
        return f"找到 {tool_name} 的 Dockerfile 示例：\n\n{formatted}"
    else:
        return f"搜索失败: {result['message']}"


def create_dockerfile_generator_agent() -> Agent:
    """
    创建 Dockerfile 生成 Agent
    
    该 Agent 负责:
    1. 根据项目分析结果选择合适的模板
    2. 自定义和优化 Dockerfile
    3. 处理特殊依赖和配置
    4. 可通过 web 搜索查找 Dockerfile 示例和最佳实践
    """
    return Agent(
        name="DockerfileGenerator",
        model=OpenAIChat(id=OPENAI_MODEL, base_url=OPENAI_API_BASE or None),
        tools=[
            check_if_metapackage,
            get_dockerfile_template,
            save_dockerfile,
            read_existing_dockerfile,
            read_dependency_file,
            patch_dockerfile,
            search_web_for_dockerfile,
            search_dockerfile_examples,
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
            "**必须包含完整的编译工具链**：",
            "- Fortran 编译器 (gfortran) - 很多科学计算代码用 Fortran 编写",
            "- C/C++ 编译器 (gcc, g++) - 基础编译器",
            "- make, cmake - 构建工具",
            "- pkg-config - 包配置工具",
            "- BLAS/LAPACK 库 - 线性代数运算",
            "- HDF5 支持 (libhdf5-openmpi-dev, hdf5-tools) - 数据 I/O",
            "- MPI 并行支持 (openmpi-bin, libopenmpi-dev) - 并行计算",
            "- FFTW - 快速傅里叶变换",
            "- GPU 支持（如需要，使用 NVIDIA 基础镜像）",
            "",
            "## 可用的专业模板",
            "针对科学计算工具，我们有三个专业模板：",
            "1. **scientific_python**: Python 科学计算环境",
            "2. **scientific_computing_fortran**: Fortran/C/C++ 科学计算环境（包含 MPI、HDF5、OpenBLAS）",
            "3. **scientific_computing_intel**: Intel OneAPI 环境（包含 ifort、MKL、Intel MPI）",
            "",
            "## 模板选择策略",
            "- **如果是元仓库（根目录有 CMakeLists.txt 且多个子包）：使用 cmake_metapackage**",
            "- 如果项目主要是 Python + 少量编译代码：使用 scientific_python",
            "- 如果项目需要从源码编译 Fortran/C/C++：使用 scientific_computing_fortran",
            "- 如果项目明确需要 Intel 编译器或性能优化：使用 scientific_computing_intel",
            "- 对于 Nek5000、VASP、OpenFOAM 等计算流体力学/材料模拟工具：优先 scientific_computing_fortran 或 scientific_computing_intel",
            "",
            "## 交互性要求（重要！）",
            "**科学计算工具镜像必须支持用户交互式使用**：",
            "1. 确保安装 bash：`apt-get install -y bash` 或 `apk add bash`",
            "2. 使用 CMD 而不是 ENTRYPOINT（除非有特殊需求）",
            "3. 默认 CMD 应设置为：`CMD [\"/bin/bash\"]` 或 `CMD [\"/bin/bash\", \"-l\"]`（如需加载环境）",
            "4. 这样用户可以：",
            "   - 运行 `docker run -it image /bin/bash` 进入交互式 shell",
            "   - 运行 `docker exec -it container /bin/bash` 进入正在运行的容器",
            "   - 自由执行各种命令和脚本",
            "5. 避免使用限制性的 ENTRYPOINT，因为它会阻止用户覆盖启动命令",
            "",
            "## Dockerfile 修复流程",
            "当收到修复请求时（通过 patch_dockerfile 工具）：",
            "1. 使用 patch_dockerfile 获取当前 Dockerfile 内容和问题描述",
            "2. 分析问题根因（如缺少编译器、库版本不兼容等）",
            "3. 生成修复后的完整 Dockerfile",
            "4. 使用 save_dockerfile 保存修复后的版本",
            "5. 在注释中说明修复了什么问题",
            "",
            "## 输出要求",
            "生成完整、可直接使用的 Dockerfile，包含：",
            "- 基础镜像选择说明",
            "- 完整的系统依赖安装（包括编译工具链、bash）",
            "- 项目依赖安装",
            "- 设置 CMD [\"/bin/bash\"] 用于交互式使用",
            "- 必要的环境变量",
            "- 避免使用 ENTRYPOINT（除非是 web 服务等特殊场景）",
        ],
        markdown=True,
        debug_mode=True,  # 显示调试信息
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

