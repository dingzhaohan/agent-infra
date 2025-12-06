# 元仓库（Meta-package）检测与处理

## 什么是元仓库？

元仓库是包含多个独立子包/子项目的仓库，通常在根目录使用统一的构建系统（如 CMake）一次性构建所有子包。

### 典型例子

#### SuiteSparse
- **子包**: AMD, BTF, CAMD, CCOLAMD, COLAMD, CHOLMOD, CSparse, CXSparse, GraphBLAS, LAGraph, KLU, LDL, Mongoose, ParU, RBio, SPEX, SPQR, UMFPACK
- **根构建系统**: `CMakeLists.txt` + `Makefile`
- **正确构建**: 从根目录构建所有包

#### Trilinos（未来可能遇到）
- **子包**: Teuchos, Epetra, AztecOO, Belos, Ifpack, ML, NOX 等
- **根构建系统**: CMake
- **正确构建**: 从根目录构建

## 检测标准（泛化方法）

### 判断是否是元仓库

**新版本使用完全泛化的检测逻辑，不依赖硬编码的包名！**

满足以下条件：
1. ✅ 根目录有 `CMakeLists.txt` 或 `Makefile`
2. ✅ **并且**满足以下之一：
   - 至少 **3 个**一级子目录有构建文件（CMakeLists.txt 或 Makefile）
   - 根构建文件引用了至少 **3 个**子目录（通过 `add_subdirectory()` 或 `cd xxx && make`）

### 检测工具

使用 `check_if_metapackage` 工具函数：

```python
from agents.dockerfile_generator import check_if_metapackage

result = check_if_metapackage("/path/to/repo")
# 返回:
{
    "is_metapackage": true,
    "has_root_cmake": true,
    "has_root_makefile": true,
    "subpackages_with_build_files": ["AMD", "CHOLMOD", "GraphBLAS", ...],
    "subpackage_count": 22,
    "referenced_directories": ["AMD", "CHOLMOD", ...],
    "referenced_count": 20,
    "recommendation": "使用 cmake_metapackage 模板从根目录构建所有子包"
}
```

### 泛化特性

- ✅ **自动扫描子目录**：不需要预先知道子包名称
- ✅ **分析构建文件内容**：理解项目结构
- ✅ **排除干扰目录**：自动跳过 `build`, `docs`, `tests` 等
- ✅ **适用于任何项目**：不限于 SuiteSparse

详细说明：[METAPACKAGE_DETECTION_GENERIC.md](METAPACKAGE_DETECTION_GENERIC.md)

## 处理策略

### 对于元仓库

1. **忽略子目录的 Dockerfile**
   - SuiteSparse 的 `LAGraph/Dockerfile` 只构建部分包
   - 应该生成根目录的 Dockerfile

2. **使用 cmake_metapackage 模板**
   - 从根目录构建所有子包
   - 使用根目录的 `CMakeLists.txt`

3. **构建上下文设置为根目录**
   - 不是子包目录

### 对于普通仓库

1. **使用现有 Dockerfile**（如果有）
2. **根据技术栈选择模板**
   - Python: `python_pip` / `scientific_python`
   - Fortran/C/C++: `scientific_computing_fortran`
   - 等等

## cmake_metapackage 模板

专门为元仓库设计的模板：

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    GIT_TERMINAL_PROMPT=0
SHELL ["/bin/bash", "-c"]

# 安装完整的科学计算工具链
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl wget git \
    build-essential gcc g++ gfortran make cmake pkg-config \
    autoconf automake libtool \
    openmpi-bin libopenmpi-dev \
    libopenblas-dev liblapack-dev \
    libhdf5-openmpi-dev hdf5-tools \
    libfftw3-dev libmetis-dev \
    vim tree htop ncdu \
    && rm -rf /var/lib/apt/lists/*

# Set MPI environment variables
ENV MPICC=mpicc \
    MPICXX=mpicxx \
    MPIFORT=mpifort \
    MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi

# Copy entire repository (meta-package with all sub-packages)
WORKDIR /src/metapackage
COPY . /src/metapackage

# Build entire meta-package using CMake
RUN set -eux; \
    mkdir -p build && cd build && \
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_STATIC_LIBS=OFF && \
    cmake --build . -j"$(nproc)" && \
    cmake --install . && \
    ldconfig

# Create non-root user
ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME}

# Set library paths
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib/pkgconfig \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib:/usr/lib/x86_64-linux-gnu

WORKDIR /workspace
USER ${USERNAME}
CMD ["/bin/bash"]
```

## 关键特性

### 1. 完整的工具链

包含所有必要的编译工具和科学计算库：
- 编译器：gcc, g++, gfortran
- 构建工具：make, cmake, pkg-config, autoconf, automake, libtool
- MPI：OpenMPI
- 数学库：OpenBLAS, LAPACK, FFTW, METIS

### 2. Git 环境配置

```dockerfile
ENV GIT_TERMINAL_PROMPT=0
```

防止 Docker 构建过程中 git clone 卡住。

### 3. 优化的 CMake 配置

```dockerfile
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \      # 发布版本
    -DCMAKE_INSTALL_PREFIX=/usr/local \  # 安装到标准位置
    -DBUILD_SHARED_LIBS=ON \          # 构建共享库
    -DBUILD_STATIC_LIBS=OFF           # 不构建静态库（减小镜像大小）
```

### 4. 并行构建

```dockerfile
cmake --build . -j"$(nproc)"
```

使用所有可用 CPU 核心加速构建。

## Agent 指令更新

Agent 现在会：

1. **首先检查是否是元仓库**：
   - 使用 `check_if_metapackage` 工具
   - 分析结果

2. **如果是元仓库**：
   - 使用 `cmake_metapackage` 模板
   - 忽略子目录的 Dockerfile
   - 从根目录构建

3. **如果不是元仓库**：
   - 按照常规流程处理
   - 使用现有 Dockerfile 或生成新的

## 使用示例

### 手动检测

```python
from agents.dockerfile_generator import check_if_metapackage

# 检测 SuiteSparse
result = check_if_metapackage("/root/agent-infra/repos/SuiteSparse")
print(result)
# {
#   "is_metapackage": true,
#   "has_root_cmake": true,
#   "found_subpackages": ["AMD", "CHOLMOD", "GraphBLAS", ...],
#   "subpackage_count": 15,
#   "recommendation": "使用 cmake_metapackage 模板..."
# }
```

### 自动处理

```bash
# 重新处理 SuiteSparse（Agent 会自动检测并使用正确的模板）
python main.py --tool "SuiteSparse" --skip-verify
```

Agent 会：
1. 检测到 SuiteSparse 是元仓库
2. 使用 `cmake_metapackage` 模板
3. 生成构建所有子包的 Dockerfile

## 验证

修复后，SuiteSparse 的 Dockerfile 应该：

- ✅ 从根目录构建（不是 LAGraph/ 目录）
- ✅ 构建所有子包（AMD, CHOLMOD, GraphBLAS, LAGraph, UMFPACK, 等）
- ✅ 使用 CMake 统一构建
- ✅ 安装到 /usr/local

## 相关修改

### 修改的文件

1. **agents/dockerfile_generator.py**
   - 添加 `cmake_metapackage` 模板
   - 添加 `check_if_metapackage` 工具函数
   - 更新 Agent 指令

2. **tools/file_tools.py**
   - 改进 `find_dockerfile()` 函数
   - 优先选择根目录的 Dockerfile
   - 改进 `write_dockerfile()` 自动添加 `GIT_TERMINAL_PROMPT=0`

## 总结

通过识别元仓库并使用专门的模板，系统现在可以正确处理 SuiteSparse 这样的复杂仓库，构建所有子包而不仅仅是 LAGraph。

这是一个**鲁棒的解决方案**，因为：
- ✅ 自动检测元仓库特征
- ✅ 使用专门的模板
- ✅ 遵循项目官方的构建方式
- ✅ 适用于其他类似的元仓库（如 Trilinos）

相关文档：
- [BUGFIX_SUITESPARSE_METAPACKAGE.md](BUGFIX_SUITESPARSE_METAPACKAGE.md)
- [DOCKER_GIT_CLONE_FIX.md](DOCKER_GIT_CLONE_FIX.md)

