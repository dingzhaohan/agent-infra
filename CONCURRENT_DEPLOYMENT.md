# 并发部署功能说明

## 概述

`BatchDeploymentWorkflow` 现在支持多进程并发部署，可以显著加快批量处理多个工具的速度。

## 功能特性

- ✅ **多进程并发**: 使用 `ProcessPoolExecutor` 实现真正的并行处理
- ✅ **可配置并发数**: 通过环境变量或参数控制最大并发进程数
- ✅ **向后兼容**: 保留原有的串行模式，通过 `concurrent` 参数切换
- ✅ **实时进度反馈**: 即使在并发模式下也能看到每个工具的处理进度
- ✅ **独立进程隔离**: 每个工具在独立进程中运行，互不影响

## 快速开始

### 1. 配置并发数

在 `.env` 文件中设置最大并发数：

```bash
MAX_CONCURRENT_TOOLS=3  # 同时处理 3 个工具
```

### 2. 使用便捷函数

```python
from workflow import deploy_batch_tools

# 并发部署
result = deploy_batch_tools(
    limit=10,              # 处理前 10 个工具
    concurrent=True,       # 启用并发模式
    max_workers=3          # 最多 3 个并发进程
)
```

### 3. 使用工作流类

```python
from workflow import BatchDeploymentWorkflow

workflow = BatchDeploymentWorkflow(max_workers=4)

for msg in workflow.run(
    limit=20,
    skip_verification=False,
    concurrent=True  # 并发模式
):
    print(msg.content)
```

## 使用场景对比

### 串行模式 (Serial)

**适用场景**:
- 资源受限的环境（内存、CPU）
- 需要严格按顺序处理
- 调试和排查问题
- 工具数量较少（< 5 个）

**使用方法**:
```python
workflow = BatchDeploymentWorkflow()
for msg in workflow.run(concurrent=False):
    print(msg.content)
```

### 并发模式 (Concurrent)

**适用场景**:
- 批量处理大量工具（> 10 个）
- 资源充足的服务器环境
- 对处理速度有要求
- 工具之间相互独立

**使用方法**:
```python
workflow = BatchDeploymentWorkflow(max_workers=5)
for msg in workflow.run(concurrent=True):
    print(msg.content)
```

## 性能提升

理论加速比取决于：
- 并发进程数
- 每个工具的处理时间
- 系统资源（CPU、内存、磁盘 I/O）

**预期性能**:
```
串行模式:  工具1 -> 工具2 -> 工具3 -> ... (总时间 = sum(每个工具时间))
并发模式:  工具1 ┐
          工具2 ├─> 并行处理 (总时间 ≈ max(每个工具时间) / 并发数)
          工具3 ┘
```

**示例场景**:
- 10 个工具，每个耗时 5 分钟
- 串行模式: 50 分钟
- 并发模式 (3 workers): ~17 分钟
- **加速比: ~3x**

## API 参考

### BatchDeploymentWorkflow

```python
class BatchDeploymentWorkflow:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TOOLS):
        """
        初始化批量部署工作流
        
        Args:
            max_workers: 最大并发工作进程数
        """
    
    def run(
        self,
        tools: list[Tool] = None,
        limit: int = None,
        skip_verification: bool = False,
        filter_domain: str = None,
        concurrent: bool = False
    ) -> Generator[WorkflowMessage, None, dict]:
        """
        批量执行部署工作流
        
        Args:
            tools: 工具列表（如果为空，从 list.md 读取）
            limit: 限制处理数量
            skip_verification: 是否跳过验证
            filter_domain: 按领域过滤
            concurrent: 是否使用并发模式
        
        Yields:
            WorkflowMessage: 工作流进度消息
            
        Returns:
            dict: 统计结果
        """
```

### 便捷函数

```python
def deploy_batch_tools(
    limit: int = None,
    skip_verification: bool = False,
    filter_domain: str = None,
    concurrent: bool = False,
    max_workers: int = MAX_CONCURRENT_TOOLS
) -> dict:
    """批量部署工具的便捷函数"""
```

## 注意事项

### 资源消耗

并发模式会同时运行多个进程，每个进程都会：
- 初始化独立的 Agent（LLM 连接）
- 克隆 Git 仓库
- 构建 Docker 镜像（如果启用验证）
- 占用系统资源（CPU、内存、磁盘）

**建议配置**:
```
并发数 = min(CPU 核心数, 可用内存(GB) / 4, 5)

示例:
- 4 核 8GB: max_workers=2
- 8 核 16GB: max_workers=4
- 16 核 32GB: max_workers=5
```

### 错误处理

- 每个工具在独立进程中运行，一个失败不影响其他
- 异常会被捕获并记录，不会导致整个批处理中断
- 失败的工具可以单独重新运行

### 日志和输出

- 并发模式下，消息按完成顺序输出（不保证工具顺序）
- 每个工具的消息会被缓存，完成后统一输出
- 最终会显示汇总统计

## 示例脚本

查看 `example_concurrent_deploy.py` 获取更多示例：

```bash
# 并发部署示例
python example_concurrent_deploy.py concurrent

# 串行部署示例
python example_concurrent_deploy.py sequential

# 按领域过滤并发部署
python example_concurrent_deploy.py filter

# 性能对比测试
python example_concurrent_deploy.py compare
```

## 故障排查

### 问题：进程启动失败

```
错误: cannot pickle 'generator' object
```

**解决**: 已通过独立的工作器函数解决，不会出现此问题。

### 问题：内存不足

```
错误: MemoryError or OSError: Cannot allocate memory
```

**解决**: 减少 `max_workers` 参数值。

### 问题：并发效果不明显

**可能原因**:
- I/O 密集型操作（Git 克隆、Docker 构建）受限于网络/磁盘
- LLM API 调用有速率限制
- 系统资源不足

**建议**:
- 检查网络带宽和磁盘速度
- 使用 SSD 而非 HDD
- 确保 LLM API 支持并发请求

## 配置文件

`config.py` 中的相关配置：

```python
# 并发配置
MAX_CONCURRENT_TOOLS = int(os.getenv("MAX_CONCURRENT_TOOLS", "2"))

# 其他相关配置
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "600"))
GIT_TIMEOUT = int(os.getenv("GIT_TIMEOUT", "300"))
```

## 最佳实践

1. **首次运行**: 使用串行模式测试少量工具，确保流程正常
2. **调整并发数**: 根据系统资源逐步增加并发数
3. **监控资源**: 使用 `htop`、`docker stats` 监控系统负载
4. **分批处理**: 大批量工具可以分多次处理，避免单次运行时间过长
5. **错误重试**: 失败的工具可以单独用串行模式重新运行，便于调试

## 性能监控

监控并发处理的性能：

```bash
# 监控 CPU 和内存
htop

# 监控 Docker 容器
watch -n 1 docker stats

# 监控磁盘 I/O
iostat -x 1

# 监控进程
ps aux | grep python
```

## 未来优化

潜在的改进方向：
- [ ] 支持优先级队列
- [ ] 支持任务依赖关系
- [ ] 实时进度条（rich/tqdm）
- [ ] 更细粒度的资源控制
- [ ] 支持分布式部署（多机器）

