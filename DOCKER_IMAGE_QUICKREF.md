# Docker 镜像配置 - 快速参考

## 默认镜像格式

```
registry.dp.tech/davinci/{tool-name}:latest
```

## 示例

| 工具名 | 镜像名称 |
|--------|---------|
| scikit-fem | `registry.dp.tech/davinci/scikit-fem:latest` |
| abinit | `registry.dp.tech/davinci/abinit:latest` |
| GAP / QUIP | `registry.dp.tech/davinci/gap---quip:latest` |

## 快速配置

### 使用默认配置（无需任何操作）

```bash
python main.py --tool "scikit-fem"
# 生成: registry.dp.tech/davinci/scikit-fem:latest
```

### 自定义仓库

```bash
# 方式 1: 临时环境变量
DOCKER_REGISTRY="docker.io" python main.py --tool "scikit-fem"

# 方式 2: .env 文件
echo "DOCKER_REGISTRY=docker.io" >> .env
echo "DOCKER_NAMESPACE=myuser" >> .env
echo "DOCKER_TAG=v1.0.0" >> .env

python main.py --tool "scikit-fem"
# 生成: docker.io/myuser/scikit-fem:v1.0.0
```

## 三个配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DOCKER_REGISTRY` | `registry.dp.tech` | 镜像仓库地址 |
| `DOCKER_NAMESPACE` | `davinci` | 命名空间 |
| `DOCKER_TAG` | `latest` | 镜像标签 |

## 推送镜像

```bash
# 登录
docker login registry.dp.tech

# 推送单个
docker push registry.dp.tech/davinci/scikit-fem:latest

# 批量推送
docker images | grep "registry.dp.tech/davinci/" | \
  awk '{print $1":"$2}' | xargs -I {} docker push {}
```

## 常见配置

### Docker Hub

```bash
export DOCKER_REGISTRY="docker.io"
export DOCKER_NAMESPACE="yourusername"
```

### GitHub Container Registry

```bash
export DOCKER_REGISTRY="ghcr.io"
export DOCKER_NAMESPACE="your-org"
```

### 阿里云容器镜像服务

```bash
export DOCKER_REGISTRY="registry.cn-hangzhou.aliyuncs.com"
export DOCKER_NAMESPACE="your-namespace"
```

## 验证配置

```bash
python -c "
from config import DOCKER_REGISTRY, DOCKER_NAMESPACE, DOCKER_TAG
print(f'{DOCKER_REGISTRY}/{DOCKER_NAMESPACE}/example:{DOCKER_TAG}')
"
```

## 详细文档

- [DOCKER_IMAGE_CONFIG.md](DOCKER_IMAGE_CONFIG.md) - 完整配置说明
- [README.md](README.md) - 系统使用指南

