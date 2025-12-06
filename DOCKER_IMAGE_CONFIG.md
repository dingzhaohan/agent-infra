# Docker 镜像命名配置

## 概述

系统支持自定义 Docker 镜像的命名格式，包括镜像仓库、命名空间和标签。

## 默认配置

镜像格式：`registry.dp.tech/davinci/{tool-name}:latest`

**示例**：
- `registry.dp.tech/davinci/scikit-fem:latest`
- `registry.dp.tech/davinci/abinit:latest`
- `registry.dp.tech/davinci/calculix:latest`

## 配置参数

### 1. DOCKER_REGISTRY

**用途**: Docker 镜像仓库地址

**默认值**: `registry.dp.tech`

**配置方式**:
```bash
# 环境变量
export DOCKER_REGISTRY="registry.dp.tech"

# .env 文件
echo "DOCKER_REGISTRY=registry.dp.tech" >> .env

# 使用其他仓库
export DOCKER_REGISTRY="docker.io"  # Docker Hub
export DOCKER_REGISTRY="ghcr.io"     # GitHub Container Registry
```

### 2. DOCKER_NAMESPACE

**用途**: Docker 镜像命名空间（组织/项目）

**默认值**: `davinci`

**配置方式**:
```bash
# 环境变量
export DOCKER_NAMESPACE="davinci"

# .env 文件
echo "DOCKER_NAMESPACE=myorg" >> .env
```

### 3. DOCKER_TAG

**用途**: Docker 镜像标签

**默认值**: `latest`

**配置方式**:
```bash
# 环境变量
export DOCKER_TAG="latest"

# 使用版本号
export DOCKER_TAG="v1.0.0"

# 使用日期标签
export DOCKER_TAG="20251206"
```

## 镜像名称生成逻辑

### 代码实现（workflow.py）

```python
# 生成镜像名称
safe_name = tool.repo_name.lower().replace(' ', '-').replace('/', '-')
image_name = f"{DOCKER_REGISTRY}/{DOCKER_NAMESPACE}/{safe_name}"
image_tag = DOCKER_TAG
image_full = f"{image_name}:{image_tag}"

# 示例：
# tool.repo_name = "scikit-fem"
# → image_full = "registry.dp.tech/davinci/scikit-fem:latest"

# tool.repo_name = "GAP / QUIP"
# → safe_name = "gap---quip"
# → image_full = "registry.dp.tech/davinci/gap---quip:latest"
```

### 名称规范化

工具名会被自动转换为 Docker 友好的格式：

| 原始名称 | 转换后 | 完整镜像名 |
|---------|--------|-----------|
| `scikit-fem` | `scikit-fem` | `registry.dp.tech/davinci/scikit-fem:latest` |
| `GAP / QUIP` | `gap---quip` | `registry.dp.tech/davinci/gap---quip:latest` |
| `PETSc / petsc4py` | `petsc---petsc4py` | `registry.dp.tech/davinci/petsc---petsc4py:latest` |
| `deal.II` | `deal.ii` | `registry.dp.tech/davinci/deal.ii:latest` |

转换规则：
- 全部转为小写
- 空格 ` ` → `-`
- 斜杠 `/` → `-`

## 使用示例

### 默认配置

```bash
# 使用默认配置
python main.py --tool "scikit-fem"

# 生成镜像: registry.dp.tech/davinci/scikit-fem:latest
```

### 自定义仓库

```bash
# 使用 Docker Hub
export DOCKER_REGISTRY="docker.io"
export DOCKER_NAMESPACE="myusername"
python main.py --tool "scikit-fem"

# 生成镜像: docker.io/myusername/scikit-fem:latest
```

### 自定义标签

```bash
# 使用版本号标签
export DOCKER_TAG="v1.0.0"
python main.py --tool "scikit-fem"

# 生成镜像: registry.dp.tech/davinci/scikit-fem:v1.0.0
```

### 批量部署

```bash
# 批量构建并推送到自定义仓库
export DOCKER_REGISTRY="myregistry.com"
export DOCKER_NAMESPACE="scientific-tools"
export DOCKER_TAG="2025-12-06"

python main.py --batch --limit 10

# 生成镜像:
# - myregistry.com/scientific-tools/tool1:2025-12-06
# - myregistry.com/scientific-tools/tool2:2025-12-06
# - ...
```

## 镜像推送

构建完成后，可以推送到仓库：

```bash
# 登录仓库
docker login registry.dp.tech

# 推送镜像
docker push registry.dp.tech/davinci/scikit-fem:latest

# 批量推送所有镜像
docker images --format "{{.Repository}}:{{.Tag}}" | \
  grep "registry.dp.tech/davinci/" | \
  xargs -I {} docker push {}
```

## 镜像管理

### 查看已构建的镜像

```bash
# 查看所有 davinci 命名空间的镜像
docker images registry.dp.tech/davinci/*

# 查看特定工具的镜像
docker images registry.dp.tech/davinci/scikit-fem

# 查看镜像大小
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | \
  grep "registry.dp.tech/davinci/"
```

### 清理镜像

```bash
# 删除特定镜像
docker rmi registry.dp.tech/davinci/scikit-fem:latest

# 删除所有 davinci 命名空间的镜像
docker images --format "{{.Repository}}:{{.Tag}}" | \
  grep "registry.dp.tech/davinci/" | \
  xargs docker rmi

# 清理未使用的镜像
docker image prune -a
```

## 高级用法

### 多环境支持

```bash
# 开发环境
export DOCKER_TAG="dev"
python main.py --batch --limit 5

# 测试环境
export DOCKER_TAG="test"
python main.py --batch --limit 5

# 生产环境
export DOCKER_TAG="prod"
python main.py --batch --limit 5
```

### 版本管理

```bash
# 使用 Git 提交哈希作为标签
export DOCKER_TAG="$(git rev-parse --short HEAD)"
python main.py --tool "scikit-fem"

# 生成: registry.dp.tech/davinci/scikit-fem:a1b2c3d
```

### 自动标签

可以在 `config.py` 中实现自动标签：

```python
# 自动使用日期作为标签
from datetime import datetime
DOCKER_TAG = os.getenv("DOCKER_TAG", datetime.now().strftime("%Y%m%d"))

# 或使用 Git 信息
import subprocess
try:
    git_hash = subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'],
        stderr=subprocess.DEVNULL
    ).decode().strip()
    DOCKER_TAG = os.getenv("DOCKER_TAG", git_hash)
except:
    DOCKER_TAG = os.getenv("DOCKER_TAG", "latest")
```

## 与 CI/CD 集成

### GitHub Actions

```yaml
- name: Build and Push Docker Images
  env:
    DOCKER_REGISTRY: registry.dp.tech
    DOCKER_NAMESPACE: davinci
    DOCKER_TAG: ${{ github.sha }}
  run: |
    python main.py --batch --limit 10
    docker images --format "{{.Repository}}:{{.Tag}}" | \
      grep "registry.dp.tech/davinci/" | \
      xargs -I {} docker push {}
```

### GitLab CI

```yaml
build:
  script:
    - export DOCKER_REGISTRY=registry.dp.tech
    - export DOCKER_NAMESPACE=davinci
    - export DOCKER_TAG=$CI_COMMIT_SHORT_SHA
    - python main.py --batch --limit 10
    - docker push registry.dp.tech/davinci/*:$CI_COMMIT_SHORT_SHA
```

## 配置验证

```bash
# 检查当前配置
python -c "
from config import DOCKER_REGISTRY, DOCKER_NAMESPACE, DOCKER_TAG
print(f'Registry:  {DOCKER_REGISTRY}')
print(f'Namespace: {DOCKER_NAMESPACE}')
print(f'Tag:       {DOCKER_TAG}')
print()
print('示例镜像:')
print(f'{DOCKER_REGISTRY}/{DOCKER_NAMESPACE}/example-tool:{DOCKER_TAG}')
"
```

## 最佳实践

### 1. 使用语义化版本标签

```bash
# 开发版本
DOCKER_TAG="dev-$(date +%Y%m%d)"

# 发布版本
DOCKER_TAG="v1.2.3"

# 预发布版本
DOCKER_TAG="v1.2.3-rc1"
```

### 2. 保持 latest 标签

```bash
# 构建并打上 latest 标签
python main.py --tool "scikit-fem"

# 同时打上版本标签
docker tag registry.dp.tech/davinci/scikit-fem:latest \
           registry.dp.tech/davinci/scikit-fem:v1.0.0

# 推送两个标签
docker push registry.dp.tech/davinci/scikit-fem:latest
docker push registry.dp.tech/davinci/scikit-fem:v1.0.0
```

### 3. 使用不可变标签

对于生产环境，使用不可变标签（如 SHA 或版本号）而不是 `latest`：

```bash
export DOCKER_TAG="$(date +%Y%m%d)-$(git rev-parse --short HEAD)"
# 生成: registry.dp.tech/davinci/tool:20251206-a1b2c3d
```

## 相关文档

- [config.py](config.py) - 配置定义
- [workflow.py](workflow.py) - 镜像名称生成逻辑
- [README.md](README.md) - 系统使用说明

## 更新历史

- **2025-12-06**: 从 `scitools/{tool}` 改为 `registry.dp.tech/davinci/{tool}:latest`
  - 支持自定义仓库、命名空间和标签
  - 通过环境变量配置
  - 向后兼容

