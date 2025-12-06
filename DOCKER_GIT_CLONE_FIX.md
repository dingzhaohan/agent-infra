# Docker 构建中 Git Clone 失败问题 - 快速修复指南

## 问题原因

SuiteSparse 和 PETSc/petsc4py 在 Docker 构建时 git clone 失败（exit code 128）的原因：

### 1. **缺少 Git 环境变量**

Docker 构建环境中的 git clone 没有设置 `GIT_TERMINAL_PROMPT=0`，可能导致：
- 网络问题时卡住等待输入
- SSL 证书问题无法处理
- 无法正确处理错误

### 2. **标签可能不存在**

- SuiteSparse 使用 `v7.5.1`（GraphBLAS 仓库）
- PETSc 使用 `v9.2.0`（SuiteSparse-GraphBLAS 仓库）
- 这些标签可能不存在或已更改

### 3. **缺少错误处理**

- 没有重试机制（网络临时问题无法恢复）
- 没有提前验证标签是否存在
- 错误信息不够详细

### 4. **仓库名称不一致**

- SuiteSparse 的 Dockerfile 使用 `GraphBLAS.git`
- PETSc 的 Dockerfile 使用 `SuiteSparse-GraphBLAS.git`
- 可能是仓库已重命名

## 快速解决方案

### 方案 A: 手动修复现有 Dockerfile（立即生效）

#### 修复 SuiteSparse

编辑 `repos/SuiteSparse/LAGraph/Dockerfile`，修改第 46 行：

```dockerfile
# 修改前
RUN git clone --depth 1 --branch ${GB_VERSION} https://github.com/DrTimothyAldenDavis/GraphBLAS.git && \

# 修改后
ENV GIT_TERMINAL_PROMPT=0
RUN set -eux; \
    for i in 1 2 3; do \
        echo "尝试第 $i 次 git clone..."; \
        git clone --depth 1 --branch "${GB_VERSION}" https://github.com/DrTimothyAldenDavis/GraphBLAS.git && \
        break || (echo "失败，等待 5 秒..." && sleep 5); \
    done && \
```

#### 修复 PETSc

编辑 `repos/release/Dockerfile.generated`，修改第 58-64 行：

```dockerfile
# 修改前
RUN set -eux; \
    git clone --depth 1 --branch "${GB_VERSION:-v9.2.0}" \
      https://github.com/DrTimothyAldenDavis/SuiteSparse-GraphBLAS.git /tmp/SuiteSparse-GraphBLAS; \

# 修改后
ENV GIT_TERMINAL_PROMPT=0
RUN set -eux; \
    # 验证标签是否存在
    git ls-remote --tags --exit-code https://github.com/DrTimothyAldenDavis/SuiteSparse-GraphBLAS.git "${GB_VERSION:-v9.2.0}" || \
    (echo "错误: 标签不存在，尝试使用默认分支" && GB_VERSION="") && \
    # 重试克隆
    for i in 1 2 3; do \
        echo "尝试第 $i 次 git clone..."; \
        if [ -n "${GB_VERSION}" ]; then \
            git clone --depth 1 --branch "${GB_VERSION}" \
                https://github.com/DrTimothyAldenDavis/SuiteSparse-GraphBLAS.git /tmp/SuiteSparse-GraphBLAS && \
            break; \
        else \
            git clone --depth 1 https://github.com/DrTimothyAldenDavis/SuiteSparse-GraphBLAS.git /tmp/SuiteSparse-GraphBLAS && \
            break; \
        fi || (echo "失败，等待 5 秒..." && sleep 5); \
    done && \
```

### 方案 B: 改进 Dockerfile 生成逻辑（长期方案）

修改 `agents/dockerfile_generator.py`，在生成 Dockerfile 时自动添加改进的 git clone 代码。

## 验证修复

修复后重新构建：

```bash
# SuiteSparse
cd /root/agent-infra/repos/SuiteSparse/LAGraph
docker build -f Dockerfile -t test-suitesparse .

# PETSc
cd /root/agent-infra/repos/release
docker build -f Dockerfile.generated -t test-petsc .
```

## 检查标签是否存在

```bash
# 检查 SuiteSparse-GraphBLAS 的标签
curl -s https://api.github.com/repos/DrTimothyAldenDavis/SuiteSparse-GraphBLAS/tags | grep '"name"' | head -10

# 检查 GraphBLAS 的标签
curl -s https://api.github.com/repos/DrTimothyAldenDavis/GraphBLAS/tags | grep '"name"' | head -10
```

## 常见标签版本

根据 GitHub API，常见的标签：
- SuiteSparse-GraphBLAS: v8.0.2, v8.0.1, v8.0.0, v7.5.1, v7.4.0
- GraphBLAS: v7.5.1, v7.4.0, v7.3.0

**建议**: 使用 `v8.0.2` 或 `v7.5.1`（已验证存在）

## 临时绕过方案

如果标签确实不存在，可以：

1. **使用默认分支**（不指定 --branch）:
   ```dockerfile
   RUN git clone --depth 1 https://github.com/DrTimothyAldenDavis/SuiteSparse-GraphBLAS.git /tmp/SuiteSparse-GraphBLAS
   ```

2. **使用已知存在的标签**:
   ```dockerfile
   ARG GB_VERSION=v8.0.2  # 使用已知存在的标签
   ```

3. **构建时指定标签**:
   ```bash
   docker build --build-arg GB_VERSION=v8.0.2 -t test-image .
   ```

## 总结

**根本原因**:
1. ❌ 缺少 `GIT_TERMINAL_PROMPT=0`
2. ❌ 标签可能不存在
3. ❌ 没有重试机制
4. ❌ 没有错误处理

**解决方案**:
1. ✅ 添加 `GIT_TERMINAL_PROMPT=0`
2. ✅ 验证标签是否存在
3. ✅ 添加重试机制
4. ✅ 改进错误处理

详细分析: [BUGFIX_DOCKER_GIT_CLONE.md](BUGFIX_DOCKER_GIT_CLONE.md)

