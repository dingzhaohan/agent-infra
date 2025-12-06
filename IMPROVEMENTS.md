# Agent-Infra 改进方案

## 改进概述

本次改进主要解决以下问题：
1. verifier_agent 发现错误但没有正确反馈，导致标记为成功
2. 缺少科学计算工具的最佳实践模板
3. 缺少自动修复机制

## 主要改进

### 1. 新增科学计算 Dockerfile 模板

新增了三个专业的科学计算模板，集成了手工验证的最佳实践：

#### 1.1 `scientific_computing_fortran` - Fortran/C/C++ 科学计算环境
- **基础镜像**: Ubuntu 22.04
- **编译工具链**: gfortran, gcc, g++, make, cmake
- **MPI 支持**: openmpi-bin, libopenmpi-dev
- **科学计算库**: 
  - OpenBLAS/LAPACK（线性代数）
  - HDF5 MPI 版（数据 I/O）
  - FFTW（快速傅里叶变换）
- **开发工具**: vim, emacs, git, htop, ncdu 等
- **适用场景**: Nek5000, OpenFOAM, LAMMPS 等需要从源码编译的工具

#### 1.2 `scientific_computing_intel` - Intel OneAPI 工具链
- **基础镜像**: Ubuntu 22.04
- **Intel OneAPI BaseKit**: 
  - MKL（高性能数学库）
  - VTune（性能分析工具）
- **Intel OneAPI HPCKit**:
  - ifort（Intel Fortran 编译器）
  - icx（Intel C/C++ 编译器）
  - Intel MPI
- **环境配置**: 自动加载 Intel 环境变量
- **适用场景**: VASP, Quantum ESPRESSO 等需要 Intel 编译器优化的工具

#### 1.3 `scientific_python` - 增强版
- 新增了完整的编译工具链：gcc, g++, gfortran, make, cmake
- 确保能够编译包含 C/Fortran 扩展的 Python 包

### 2. 改进 verifier_agent 验证逻辑

#### 2.1 新增结构化验证报告

新增 `report_verification_result` 工具，要求 agent 明确报告：
- `build_success`: 镜像构建是否成功
- `container_running`: 容器是否运行
- `functional_test_success`: **功能测试是否通过**（新增！）
- `overall_status`: 总体状态（success/failed/needs_fix）
- `missing_dependencies`: 缺失的依赖列表
- `fix_suggestions`: 修复建议

#### 2.2 强化功能性测试要求

更新 agent 指令，要求必须进行功能性测试：
```markdown
## 科学计算工具的关键检查项
对于科学计算/HPC 工具，必须验证以下依赖是否可用：
- **编译器**：gfortran（Fortran）、gcc（C）、g++（C++）
- **构建工具**：make、cmake
- **MPI 支持**：mpicc、mpifort、mpirun（如果需要并行计算）
- **科学库**：检查 HDF5、BLAS/LAPACK 等库的编译器包装器（h5pcc、h5fc）
- **环境变量**：检查必要的环境变量是否设置（如 NEK_SOURCE_ROOT）
```

#### 2.3 明确的判断标准

**验证成功的标准**（所有条件必须满足）：
- ✅ 镜像构建成功
- ✅ 容器可以运行
- ✅ 所有关键工具/编译器存在且可用
- ✅ 能够成功编译简单的测试程序

**验证失败的标准**（任何一项不满足）：
- ❌ 镜像构建失败
- ❌ 容器无法运行
- ❌ 缺少关键编译器或工具（**即使镜像构建成功**）
- ❌ 无法编译测试程序

### 3. workflow 自动修复机制

#### 3.1 读取验证结果

workflow 现在能够读取 verifier_agent 生成的结构化报告：
```python
verification_result = json.load(temp_file)
overall_status = verification_result.get("overall_status", "failed")
```

#### 3.2 自动触发修复

当 `overall_status == "needs_fix"` 时：
1. 提取错误信息和缺失依赖
2. 调用 `generator_agent` 修复 Dockerfile
3. 重新验证

修复提示示例：
```python
fix_prompt = f"""
请修复 Dockerfile 以解决以下问题：
**验证发现的问题**: {error_summary}
**缺失的依赖**: {', '.join(missing_deps)}
**修复建议**: {fix_suggestions}

请使用 patch_dockerfile 工具获取当前 Dockerfile，然后生成修复后的版本。
"""
```

#### 3.3 重试机制

- 最大重试次数由 `max_retries` 控制
- 每次重试都会尝试修复 Dockerfile
- 避免无限循环修复

### 4. generator_agent 增强

#### 4.1 新增 `patch_dockerfile` 工具

支持增量修复 Dockerfile：
```python
@tool
def patch_dockerfile(
    dockerfile_path: str,
    issue_description: str,
    fix_instructions: str
) -> str:
    """根据验证失败的问题修复 Dockerfile"""
```

#### 4.2 更新生成指令

新增模板选择策略：
- 如果项目主要是 Python + 少量编译代码：使用 `scientific_python`
- 如果项目需要从源码编译 Fortran/C/C++：使用 `scientific_computing_fortran`
- 如果项目明确需要 Intel 编译器或性能优化：使用 `scientific_computing_intel`
- 对于 Nek5000、VASP、OpenFOAM 等：优先 `scientific_computing_fortran` 或 `scientific_computing_intel`

## 工作流程对比

### 改进前

```
1. 分析仓库
2. 生成 Dockerfile
3. 构建镜像 → 成功
4. 运行容器 → 成功
5. 标记为 SUCCESS ✅
   (但实际上缺少 gfortran/gcc/make，无法编译！)
```

### 改进后

```
1. 分析仓库
2. 生成 Dockerfile（使用增强的科学计算模板）
3. 构建镜像 → 成功
4. 运行容器 → 成功
5. 功能性测试 → 发现缺少 gfortran/gcc/make ❌
6. verifier_agent 报告：overall_status='needs_fix'
7. workflow 调用 generator_agent 修复 Dockerfile
8. 重新验证
9. 功能性测试 → 所有工具可用 ✅
10. 标记为 SUCCESS ✅
```

## 针对 Nek5000 案例的解决方案

根据您提供的 Nek5000 验证报告，问题是：
- 镜像构建成功 ✅
- 容器运行成功 ✅
- **但缺少**: gfortran, gcc, make, cmake, h5pcc/h5fc ❌

### 使用改进后的系统

1. **第一次生成**：
   - generator_agent 识别 Nek5000 是 Fortran 科学计算工具
   - 选择 `scientific_computing_fortran` 模板
   - 生成包含完整工具链的 Dockerfile

2. **验证阶段**：
   - verifier_agent 构建并运行容器
   - 执行功能测试：`which gfortran gcc make cmake`
   - 所有工具存在，报告 SUCCESS ✅

3. **如果仍有遗漏**：
   - verifier_agent 发现缺少某些工具
   - 报告 `needs_fix` 和缺失列表
   - workflow 触发修复
   - generator_agent 使用 `patch_dockerfile` 添加缺失依赖
   - 重新验证

## 最佳实践集成

### Intel OneAPI 安装模板

```dockerfile
# 安装 Intel OneAPI BaseKit (MKL, VTune)
RUN wget https://hpc-profiling-example.oss-cn-beijing.aliyuncs.com/software/intel/l_BaseKit_p_2022.1.2.146_offline.sh && \
    bash l_BaseKit_p_2022.1.2.146_offline.sh -a -s --eula accept --components intel.oneapi.lin.mkl.devel:intel.oneapi.lin.vtune && \
    rm -rf l_BaseKit_p_2022.1.2.146_offline.sh

# 安装 Intel OneAPI HPCKit (ifort, icx, MPI)
RUN wget https://hpc-profiling-example.oss-cn-beijing.aliyuncs.com/software/intel/l_HPCKit_p_2022.1.2.117_offline.sh && \
    bash l_HPCKit_p_2022.1.2.117_offline.sh -a -s --eula accept --components intel.oneapi.lin.ifort-compiler:intel.oneapi.lin.dpcpp-cpp-compiler-pro:intel.oneapi.lin.mpi.devel && \
    rm -rf l_HPCKit_p_2022.1.2.117_offline.sh
```

### 基础工具集模板

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gfortran gcc g++ make cmake pkg-config \
    build-essential software-properties-common \
    supervisor net-tools openssh-server \
    lsb-release curl unzip emacs vim \
    libgomp1 tree zsh wget git htop ncdu \
    bash \
    && rm -rf /var/lib/apt/lists/*
```

## 使用方法

### 测试改进

重新部署 Nek5000 以测试改进：

```python
from workflow import deploy_single_tool

# 部署单个工具
result = deploy_single_tool(
    tool_name="Nek5000",
    skip_verification=False  # 进行完整验证
)
```

### 批量部署科学计算工具

```python
from workflow import deploy_batch_tools

# 批量部署所有科学计算工具
stats = deploy_batch_tools(
    filter_domain="科学计算",
    concurrent=True,
    max_workers=4
)
```

## 预期效果

1. **验证准确性提升**：
   - 不再将"构建成功但功能不可用"标记为成功
   - 明确报告缺失的依赖和工具

2. **自动修复率提升**：
   - 大多数依赖缺失问题可以自动修复
   - 减少手工干预需求

3. **模板质量提升**：
   - 科学计算工具第一次生成就包含完整工具链
   - 减少重试次数

4. **错误报告改进**：
   - 结构化的错误报告（JSON 格式）
   - 明确的修复建议

## 文件变更清单

1. **agents/dockerfile_generator.py**
   - 新增 3 个科学计算模板
   - 新增 `patch_dockerfile` 工具
   - 更新生成指令和模板选择策略

2. **agents/verifier.py**
   - 新增 `report_verification_result` 工具
   - 更新验证流程和判断标准
   - 强化功能性测试要求

3. **workflow.py**
   - 更新 `_verify_deployment` 方法
   - 新增自动修复逻辑
   - 读取结构化验证报告

## 未来改进方向

1. **增强测试覆盖**：
   - 添加更多特定工具的测试用例
   - 支持自定义测试脚本

2. **智能模板选择**：
   - 基于仓库内容自动识别最佳模板
   - 学习历史成功案例

3. **验证报告持久化**：
   - 保存详细的验证日志
   - 支持验证结果对比

4. **并行验证优化**：
   - 支持并发验证多个容器
   - 资源隔离和限制

