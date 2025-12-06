# 快速参考指南

## 新增的 Dockerfile 模板

### 1. scientific_computing_fortran
**适用场景**: Fortran/C/C++ 科学计算工具（Nek5000, OpenFOAM, LAMMPS 等）

**包含内容**:
```dockerfile
- 编译器: gfortran, gcc, g++
- 构建工具: make, cmake, pkg-config
- MPI: openmpi-bin, libopenmpi-dev
- 科学库: libopenblas-dev, liblapack-dev, libhdf5-openmpi-dev, libfftw3-dev
- 开发工具: vim, emacs, git, htop, ncdu 等
```

### 2. scientific_computing_intel
**适用场景**: 需要 Intel 编译器优化的工具（VASP, Quantum ESPRESSO 等）

**包含内容**:
```dockerfile
- Intel OneAPI BaseKit: MKL, VTune
- Intel OneAPI HPCKit: ifort, icx, Intel MPI
- 自动加载 Intel 环境变量
- 基础开发工具
```

### 3. scientific_python（增强版）
**适用场景**: Python 科学计算 + C/Fortran 扩展

**包含内容**:
```dockerfile
- Python 3.x
- 编译器: gfortran, gcc, g++
- 构建工具: make, cmake
- 科学库: OpenBLAS, LAPACK, HDF5
```

## 关键改进点

### ✅ Verifier Agent 现在会检查

| 检查项 | 说明 |
|--------|------|
| 镜像构建 | Docker build 是否成功 |
| 容器运行 | Docker run 是否成功 |
| **功能测试** | **关键工具是否真正可用**（新增！） |
| 编译器 | gfortran, gcc, g++ 是否存在 |
| 构建工具 | make, cmake 是否存在 |
| MPI 工具 | mpicc, mpifort, mpirun 是否存在 |
| 环境变量 | 必要的环境变量是否设置 |

### ✅ 自动修复流程

```
验证失败 → 分析问题 → 生成修复方案 → 修复 Dockerfile → 重新验证
```

### ✅ 结构化错误报告

```json
{
  "build_success": true,
  "container_running": true,
  "functional_test_success": false,
  "overall_status": "needs_fix",
  "missing_dependencies": ["gfortran", "gcc", "make"],
  "fix_suggestions": [
    "添加 apt-get install gfortran gcc make",
    "设置环境变量 NEK_SOURCE_ROOT"
  ]
}
```

## 常见问题解决方案

### 问题 1: 缺少 Fortran 编译器

**症状**: `ERROR: Cannot find a supported compiler!`

**解决方案**:
```dockerfile
RUN apt-get update && apt-get install -y \
    gfortran \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*
```

**或使用模板**: `scientific_computing_fortran`

### 问题 2: 缺少 MPI 支持

**症状**: `mpicc: command not found`

**解决方案**:
```dockerfile
RUN apt-get update && apt-get install -y \
    openmpi-bin \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*
```

**或使用模板**: `scientific_computing_fortran` 或 `scientific_computing_intel`

### 问题 3: 缺少 HDF5 支持

**症状**: `h5pcc: command not found`

**解决方案**:
```dockerfile
RUN apt-get update && apt-get install -y \
    libhdf5-openmpi-dev \
    hdf5-tools \
    && rm -rf /var/lib/apt/lists/*
```

**或使用模板**: `scientific_computing_fortran`

### 问题 4: 环境变量未设置

**症状**: 工具找不到源代码路径

**解决方案**:
```dockerfile
ENV NEK_SOURCE_ROOT=/opt/Nek5000
ENV PATH=/opt/Nek5000/bin:$PATH
```

## 快速命令

### 部署单个工具（带完整验证）
```python
from workflow import deploy_single_tool

result = deploy_single_tool(
    tool_name="Nek5000",
    skip_verification=False
)
```

### 批量部署科学计算工具
```python
from workflow import deploy_batch_tools

stats = deploy_batch_tools(
    filter_domain="科学计算",
    concurrent=True,
    max_workers=4
)
```

### 手动验证现有镜像
```python
from agents.verifier import create_verifier_agent

verifier = create_verifier_agent()
response = verifier.run("""
请验证 scitools/nek5000:latest 镜像
- 运行容器
- 检查 gfortran, gcc, make, cmake 是否可用
- 必须调用 report_verification_result
""")
```

### 手动修复 Dockerfile
```python
from agents.dockerfile_generator import create_dockerfile_generator_agent

generator = create_dockerfile_generator_agent()
response = generator.run("""
修复 /path/to/Dockerfile.generated
缺失依赖: gfortran, gcc, make
请使用 patch_dockerfile 获取当前内容并修复
""")
```

## 调试技巧

### 1. 查看 Agent 调试信息
两个 Agent 都启用了 `debug_mode=True`，会输出详细的执行日志。

### 2. 查看验证结果
```python
import json
with open('/tmp/verifier_result.json', 'r') as f:
    result = json.load(f)
print(json.dumps(result, indent=2, ensure_ascii=False))
```

### 3. 手动测试容器
```bash
# 构建
docker build -t test-image -f /path/to/Dockerfile.generated .

# 运行
docker run -it --name test-container test-image /bin/bash

# 容器内测试
which gfortran gcc g++ make cmake
gfortran --version
mpicc --version
```

### 4. 查看构建日志
```python
from tools.docker_tools import build_docker_image

result = build_docker_image(
    dockerfile_path="/path/to/Dockerfile",
    image_name="test-image"
)
print(result.get('output', ''))
```

## 最佳实践

### 1. 模板选择
- **纯 Python 项目**: `python_pip` 或 `scientific_python`
- **Fortran/C/C++ 科学计算**: `scientific_computing_fortran`（首选）
- **需要 Intel 优化**: `scientific_computing_intel`
- **Node.js 项目**: `node_npm`
- **Rust 项目**: `rust_cargo`
- **Go 项目**: `go_mod`

### 2. 验证策略
- 开发阶段: `skip_verification=True`（快速迭代）
- 生产部署: `skip_verification=False`（完整验证）
- 重要工具: 设置 `max_retries=3` 允许自动修复

### 3. 并发控制
- 小型项目（< 10 工具）: `concurrent=False`（串行）
- 大型项目（> 10 工具）: `concurrent=True, max_workers=4`
- 注意 Docker 守护进程负载

### 4. 错误处理
- 始终检查返回的 `status` 字段
- 查看 `error_message` 了解失败原因
- 查看 `verification_notes` 了解详细信息
- 查看 `retry_count` 了解重试次数

## 性能优化

### 1. 减少镜像大小
- 使用 `--no-install-recommends`
- 清理 apt 缓存: `rm -rf /var/lib/apt/lists/*`
- 合并 RUN 命令减少层数
- 使用多阶段构建（如适用）

### 2. 加速构建
- 利用 Docker 层缓存
- 先复制依赖文件，后复制源代码
- 使用 `.dockerignore` 排除不必要的文件

### 3. 加速验证
- 使用轻量级测试（如 `which` 命令）
- 避免重复构建（检查镜像是否已存在）
- 并发验证多个工具

## 故障排查

### Agent 超时
```python
# 增加超时时间
from config import DOCKER_TIMEOUT
# 修改 config.py 中的 DOCKER_TIMEOUT 值
```

### 镜像构建失败
```bash
# 手动构建查看完整日志
docker build --no-cache -t test -f Dockerfile.generated .
```

### 容器无法启动
```bash
# 检查容器日志
docker logs <container_id>

# 交互式运行
docker run -it <image> /bin/bash
```

### 验证报告不准确
- 检查 verifier_agent 是否调用了 `report_verification_result`
- 查看 `/tmp/verifier_result.json` 是否存在
- 查看 agent 日志确认功能测试是否执行

## 更多帮助

- 详细改进说明: [IMPROVEMENTS.md](IMPROVEMENTS.md)
- 使用示例: [example_improved_workflow.py](example_improved_workflow.py)
- 并发部署: [CONCURRENT_DEPLOYMENT.md](CONCURRENT_DEPLOYMENT.md)
- 主文档: [README.md](README.md)

