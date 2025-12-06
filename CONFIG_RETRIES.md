# 重试次数配置说明

## 概述

系统支持配置 Dockerfile 生成和验证的重试次数，以提高自动修复的成功率。

## 配置参数

### MAX_RETRIES

**用途**: 控制 Dockerfile 生成和验证的最大重试次数

**默认值**: 10 次

**配置方式**:

```bash
# 方式 1: 环境变量（推荐）
export MAX_RETRIES=10

# 方式 2: .env 文件
echo "MAX_RETRIES=10" >> .env

# 方式 3: 直接修改 config.py
# MAX_RETRIES = 10
```

**使用场景**: 在 `workflow.py` 的 `_verify_deployment` 方法中使用

## 重试机制工作流程

```
尝试 1: 使用原始或生成的 Dockerfile
  ├─ verifier 构建并测试
  └─ 如果失败 → 返回诊断信息

尝试 2: generator 根据诊断修复 Dockerfile
  ├─ verifier 重新构建并测试
  └─ 如果失败 → 返回新的诊断信息

尝试 3-10: 继续修复和验证循环
  └─ 直到成功或达到 MAX_RETRIES

结果:
  - 成功: 部署完成
  - 失败: 记录最后一次的错误信息
```

## 重试次数建议

### 场景分析

| 场景 | 建议重试次数 | 原因 |
|------|-------------|------|
| **科学计算工具** | 10-15 次 | 依赖复杂，可能需要多次调整 |
| **简单应用** | 3-5 次 | 依赖简单，快速失败 |
| **测试环境** | 20+ 次 | 允许充分尝试，发现边界情况 |
| **生产环境** | 5-10 次 | 平衡成功率和时间成本 |
| **调试模式** | 1-2 次 | 快速失败，便于人工介入 |

### 当前设置（默认 10 次）

**优点**:
- ✅ 对于复杂的科学计算工具有足够的尝试次数
- ✅ 可以处理多层依赖问题（如 GAP/QUIP 的包名问题）
- ✅ 平衡了成功率和时间成本

**考虑因素**:
- 每次重试包括：
  - Docker 镜像构建（可能需要几分钟）
  - 容器启动和测试
  - LLM API 调用（分析和修复）
- 10 次重试的总时间可能达到 30-60 分钟

## 与其他配置的关系

### MAX_CONCURRENT_TOOLS

并发模式下，每个工具都有独立的重试计数：

```python
# 并发处理 4 个工具，每个最多重试 10 次
python main.py --batch --concurrent --workers 4
```

**总重试次数** = `工具数量 × MAX_RETRIES`（最坏情况）

### DOCKER_TIMEOUT

Docker 构建超时与重试次数相关：

```bash
# 如果 Docker 构建超时，会触发重试
DOCKER_TIMEOUT=600  # 10 分钟
MAX_RETRIES=10
```

**建议**: `DOCKER_TIMEOUT × MAX_RETRIES` 不应超过合理的总时间预算

## 实际案例

### GAP/QUIP 案例

**问题**: 需要多次修复才能成功
1. 尝试 1: 编译 OpenBLAS 失败
2. 尝试 2: 改用 apt 安装，但包名错误（libopenblas0-openmp）
3. 尝试 3: 需要修正包名为 libopenblas0-pthread

**如果只有 3 次重试**: 第 3 次仍然失败，标记为 failed
**使用 10 次重试**: 有足够空间继续尝试，最终可能成功

### SuiteSparse 案例

**问题**: 元仓库构建复杂
1. 尝试 1: 使用子目录 Dockerfile（只构建部分）
2. 尝试 2: 检测到元仓库，生成新 Dockerfile
3. 尝试 3-5: 调整依赖和构建参数

**10 次重试**: 足够完成整个修复流程

## 监控和调试

### 查看重试情况

```bash
# 查看某个工具的重试次数
grep "retry_count" results/YourTool.json

# 查看日志中的重试信息
grep "尝试第" logs/*.log
```

### 统计重试次数

```bash
# 统计所有工具的平均重试次数
python << 'EOF'
import json
from pathlib import Path

retry_counts = []
for f in Path("results").glob("*.json"):
    data = json.load(f.open())
    if "retry_count" in data:
        retry_counts.append(data["retry_count"])

if retry_counts:
    avg = sum(retry_counts) / len(retry_counts)
    print(f"平均重试次数: {avg:.1f}")
    print(f"最大重试次数: {max(retry_counts)}")
    print(f"最小重试次数: {min(retry_counts)}")
EOF
```

## 性能优化建议

### 如果重试次数经常达到上限

1. **改进 Verifier 的诊断质量**
   - 提供更准确的错误分析
   - 给出更具体的修复建议

2. **改进 Generator 的修复能力**
   - 添加常见问题的知识库
   - 使用更强大的 LLM 模型

3. **添加早期失败检测**
   - 如果连续 3 次修复相同的问题，可能需要人工介入
   - 避免无效的重试

### 如果重试次数很少使用

1. **可以降低 MAX_RETRIES**
   - 减少等待时间
   - 更快地失败并人工介入

2. **优先处理高质量的 Dockerfile**
   - 对已有 Dockerfile 的项目，重试次数可以更少

## 命令行覆盖

虽然默认值在 `config.py` 中设置，你可以通过环境变量临时覆盖：

```bash
# 单次运行使用 20 次重试
MAX_RETRIES=20 python main.py --tool "ComplexTool"

# 批量运行使用 5 次重试（快速失败）
MAX_RETRIES=5 python main.py --batch --limit 10
```

## 更新历史

- **2025-12-06**: 默认值从 3 次增加到 10 次
  - 原因: 提高复杂科学计算工具的成功率
  - 测试: GAP/QUIP、SuiteSparse 等工具需要更多重试

## 相关文档

- [workflow.py](workflow.py) - 重试逻辑实现
- [config.py](config.py) - 配置定义
- [IMPROVEMENTS.md](IMPROVEMENTS.md) - 自动修复机制说明

## 总结

**当前配置（10 次）**适合大多数场景，特别是复杂的科学计算工具。如果你的使用场景不同，可以根据上述建议调整。

**关键原则**: 平衡成功率和时间成本，根据实际情况动态调整。

