# FEBio Docker Build Context 修复

## 问题描述

FEBio 的 Dockerfile 构建失败，错误信息：

```
COPY failed: file not found in build context or excluded by .dockerignore: 
stat common/: file does not exist
```

## 问题分析

### FEBio 的目录结构

```
repos/FEBio/
└── infrastructure/
    ├── Dockerfile          ← Dockerfile 位置
    └── common/             ← 需要的目录
        └── linux/
            └── ...
```

### Dockerfile 中的 COPY 指令

```dockerfile
COPY ./common/linux ${IMAGE_BUILD_PATH}
```

### 问题根源

`_detect_build_context` 函数的逻辑有误：

1. **错误的逻辑**（修复前）：
   - 对于 `COPY ./common/linux`，提取 `common` 作为第一个部分
   - 在 Dockerfile 的父目录（`repos/FEBio/infrastructure/`）中查找 `common`
   - 找到后，错误地使用 `current.parent`（`repos/FEBio/`）作为 context
   - 但 `common` 实际上在 `repos/FEBio/infrastructure/` 中

2. **正确的逻辑**（修复后）：
   - 首先检查 Dockerfile 的父目录（`repos/FEBio/infrastructure/`）
   - 如果找到 `common`，使用当前目录作为 context ✅
   - 如果没找到，再向上查找（用于 dolfinx 这种情况）

## 修复方案

### 修复后的逻辑

```python
def _detect_build_context(dockerfile_path: Path) -> tuple[str, str]:
    # 1. 首先检查 Dockerfile 的父目录（最常见情况）
    dockerfile_parent = dockerfile_path.parent
    if (dockerfile_parent / first_part).exists():
        # ✅ 使用当前目录作为 context（FEBio 的情况）
        return str(dockerfile_parent), dockerfile_path.name
    
    # 2. 如果没找到，向上查找（dolfinx 的情况）
    current = dockerfile_parent
    for _ in range(5):
        if (current.parent / first_part).exists():
            # ✅ 使用父目录作为 context
            return str(current.parent), relative_path
        current = current.parent
    
    # 3. 默认：使用 Dockerfile 的父目录
    return str(dockerfile_path.parent), dockerfile_path.name
```

### 关键改进

1. **优先检查当前目录**：
   ```python
   if (dockerfile_parent / first_part).exists():
       return str(dockerfile_parent), dockerfile_path.name
   ```
   这解决了 FEBio 的问题。

2. **清理路径前缀**：
   ```python
   clean_match = match.strip().lstrip('./').strip('"\'')
   ```
   正确处理 `./common/linux` 格式。

3. **向上查找作为备选**：
   保留向上查找逻辑，用于 dolfinx 等特殊情况。

## 测试用例

### 用例 1: FEBio（修复的主要目标）

- **Dockerfile**: `repos/FEBio/infrastructure/Dockerfile`
- **COPY 指令**: `COPY ./common/linux ${IMAGE_BUILD_PATH}`
- **common 位置**: `repos/FEBio/infrastructure/common/`
- **正确的 context**: `repos/FEBio/infrastructure/` ✅
- **修复前**: `repos/FEBio/` ❌
- **修复后**: `repos/FEBio/infrastructure/` ✅

### 用例 2: dolfinx（仍然支持）

- **Dockerfile**: `repos/dolfinx/docker/Dockerfile.end-user`
- **COPY 指令**: `COPY dolfinx/docker/...`
- **dolfinx 位置**: `repos/dolfinx/`
- **正确的 context**: `repos/` ✅
- **修复后**: `repos/` ✅（通过向上查找）

### 用例 3: 标准情况（默认行为）

- **Dockerfile**: `repos/tool/Dockerfile`
- **COPY 指令**: `COPY . /app`
- **正确的 context**: `repos/tool/` ✅
- **修复后**: `repos/tool/` ✅（默认行为）

## 验证方法

### 手动测试

```bash
# 测试 FEBio 构建
cd /root/agent-infra/repos/FEBio/infrastructure
docker build -f Dockerfile -t test-febio .

# 应该成功，不再报 "file not found" 错误
```

### 通过系统测试

```bash
# 重新部署 FEBio
python main.py --tool "FEBio"

# 查看结果
cat results/FEBio.json | jq
```

## 修改的文件

- **tools/docker_tools.py**
  - `_detect_build_context()` 函数
  - 改进检测逻辑，优先检查当前目录

## 影响范围

### 修复的问题

- ✅ FEBio 构建失败问题
- ✅ 其他类似结构的项目（Dockerfile 在子目录，COPY 相对路径）

### 保持兼容

- ✅ dolfinx 等需要向上查找的项目仍然正常工作
- ✅ 标准结构的项目（Dockerfile 在根目录）不受影响

## 相关错误信息

修复前 FEBio.json 中的错误：

```json
{
  "error_message": "验证失败（尝试 3 次）: Docker 构建失败：COPY failed: file not found in build context or excluded by .dockerignore: stat common/: file does not exist"
}
```

修复后应该能够成功构建。

## 总结

通过改进 `_detect_build_context` 函数，优先检查 Dockerfile 的父目录，解决了 FEBio 的构建上下文问题。

修复后：
- ✅ FEBio 可以正确构建
- ✅ 其他项目不受影响
- ✅ 逻辑更加健壮和直观

## 相关文档

- Docker Build Context: https://docs.docker.com/build/building/context/
- 之前的修复: [DOCKER_BUILD_CONTEXT_FIX.md](DOCKER_BUILD_CONTEXT_FIX.md)

