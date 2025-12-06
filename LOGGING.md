# 日志系统说明

## 概述

系统已集成自动日志持久化功能，所有运行记录都会保存到 `logs/` 目录下，方便回溯和分析。

## 日志文件命名规则

日志文件使用北京时间（UTC+8）作为时间戳命名：

```
格式: YYYYMMDD_HHMMSS_beijing.log
示例: 20241206_143022_beijing.log
```

- `YYYYMMDD`: 年月日
- `HHMMSS`: 时分秒
- `_beijing`: 表示使用北京时间

## 日志内容

每个日志文件包含：

1. **系统启动信息**
   - 启动时间（北京时间）
   - 日志文件路径
   - 配置信息

2. **运行日志**
   - **DEBUG**: 详细的调试信息（包括 Agno Agent 的执行细节、工具调用、HTTP 请求等）
   - **INFO**: 一般信息（如开始处理、完成等）
   - **WARNING**: 警告信息
   - **ERROR**: 错误信息
   - 详细的操作流程记录

3. **Agent 调试信息**
   - Agno Agent 的工具调用详情
   - LLM API 请求和响应摘要
   - HTTP 请求日志（httpx）
   - 详细的执行步骤

4. **结果汇总**
   - 成功/失败的工具列表
   - 统计信息
   - 错误详情

## 日志查看

### 方法 1: 直接查看日志文件

```bash
# 查看最新日志
ls -lt logs/ | head -5
cat logs/20241206_143022_beijing.log

# 查看特定内容
grep "ERROR" logs/20241206_143022_beijing.log
tail -50 logs/20241206_143022_beijing.log
```

### 方法 2: 使用日志查看工具（推荐）

系统提供了专门的日志查看工具 `view_logs.py`，支持多种查看方式：

#### 列出所有日志

```bash
python view_logs.py
# 或
python view_logs.py --list

# 指定显示数量
python view_logs.py --list --limit 50
```

#### 查看最新日志

```bash
# 查看完整日志
python view_logs.py --latest

# 只看最后 50 行
python view_logs.py --latest --tail 50

# 只看最后 100 行
python view_logs.py --latest --tail 100
```

#### 查看指定日志文件

```bash
python view_logs.py --file 20241206_143022_beijing.log
```

#### 过滤关键词

```bash
# 只看错误日志
python view_logs.py --latest --grep "ERROR"

# 只看成功记录
python view_logs.py --latest --grep "成功"

# 只看某个工具的日志
python view_logs.py --latest --grep "Nek5000"
```

#### 分析日志统计

```bash
# 分析最新日志
python view_logs.py --analyze

# 分析指定日志
python view_logs.py --file 20241206_143022_beijing.log --analyze
```

统计包含：
- 总行数
- INFO/WARNING/ERROR 数量
- 成功/失败操作数
- 关键事件提取

### 方法 3: 组合使用

```bash
# 查看最新日志的错误信息（最后 100 行）
python view_logs.py --latest --tail 100 --grep "ERROR"

# 查看最新日志的部署结果
python view_logs.py --latest --grep "部署"
```

## 实际使用示例

### 示例 1: 运行批量部署并查看日志

```bash
# 1. 运行批量部署
python main.py --batch --limit 5

# 2. 查看最新日志
python view_logs.py --latest

# 3. 只看错误
python view_logs.py --latest --grep "ERROR"

# 4. 查看统计
python view_logs.py --analyze
```

### 示例 2: 并发部署后查看日志

```bash
# 1. 并发部署
python main.py --batch --concurrent --workers 4 --domain "科学计算"

# 2. 查看最新日志的最后 200 行
python view_logs.py --latest --tail 200

# 3. 查看成功的工具
python view_logs.py --latest --grep "部署成功"
```

### 示例 3: 比较不同时间的日志

```bash
# 1. 列出所有日志
python view_logs.py --list

# 2. 查看两个不同时间的日志统计
python view_logs.py --file 20241206_100000_beijing.log --analyze
python view_logs.py --file 20241206_150000_beijing.log --analyze
```

## 日志文件位置

```
agent-infra/
├── logs/
│   ├── 20241206_100532_beijing.log
│   ├── 20241206_143022_beijing.log
│   ├── 20241206_160145_beijing.log
│   └── ...
```

## 日志保留策略

- 日志文件会一直保留，不会自动删除
- 如需清理旧日志，可以手动删除：

```bash
# 查看日志总大小
du -sh logs/

# 删除 7 天前的日志
find logs/ -name "*.log" -mtime +7 -delete

# 删除所有日志（谨慎！）
rm logs/*.log
```

## 日志着色说明

在终端查看时，日志会根据内容自动着色：

- 🟢 **绿色**: 成功信息（SUCCESS、✅、部署成功等）
- 🟡 **黄色**: 警告信息（WARNING、⚠️）
- 🔴 **红色**: 错误信息（ERROR、❌、失败等）
- ⚪ **白色**: 一般信息（INFO）

## 技术细节

### 日志系统特点

1. **最小侵入式设计**
   - 只在 `main.py` 入口添加日志配置
   - 不影响现有代码逻辑
   - 自动记录所有输出

2. **双输出模式**
   - **控制台**: 保持原有的美观输出（Rich），只显示 INFO 及以上级别
   - **文件**: 详细的结构化日志，包含所有 DEBUG 级别信息

3. **完整的 Agent 调试信息**
   - 捕获 Agno Agent 的所有 DEBUG 日志
   - 记录工具调用详情
   - 记录 LLM API 交互
   - 记录 HTTP 请求日志（httpx）

4. **北京时间**
   - 使用 UTC+8 时区
   - 文件名和日志内容都使用北京时间

5. **自动创建**
   - 每次运行自动创建新日志文件
   - 按时间戳命名，永不覆盖

### 日志级别配置

- **根 Logger**: DEBUG（捕获所有日志）
- **文件处理器**: DEBUG（记录所有级别到文件）
- **控制台处理器**: INFO（只显示重要信息，避免干扰）
- **相关库 Logger**: DEBUG（agno, httpx, litellm 等）

### 日志格式

文件中的日志格式：
```
2024-12-06 14:30:22 - __main__ - INFO - 开始批量部署: 5 个工具, 模式=串行
2024-12-06 14:30:25 - __main__ - INFO - 开始单个工具部署: Nek5000
2024-12-06 14:30:26 - agno.agent - DEBUG - Tool Call: clone_repository(repo_url=...)
2024-12-06 14:30:27 - httpx - INFO - HTTP Request: POST https://llm.dp.tech/chat/completions
2024-12-06 14:30:28 - agno.agent - DEBUG - Tool Result: {"success": true, ...}
2024-12-06 14:35:10 - __main__ - INFO - 部署成功: Nek5000
```

**日志级别说明**：
- **DEBUG**: Agent 工具调用、LLM 交互细节、内部执行流程
- **INFO**: 主要操作步骤、HTTP 请求、系统状态
- **WARNING**: 警告信息、可恢复的错误
- **ERROR**: 错误信息、失败的操作

## 故障排查

### 日志文件未创建

检查 logs 目录权限：
```bash
ls -ld logs/
chmod 755 logs/
```

### 日志内容不完整

确保程序正常退出（不要强制 Ctrl+C 中断），日志会在程序退出时完整写入。

### DEBUG 日志未记录

如果发现 Agent 的 DEBUG 日志没有记录到文件：

1. **检查日志级别**：
   ```python
   # 在 main.py 中确认
   logger.setLevel(logging.DEBUG)
   file_handler.setLevel(logging.DEBUG)
   ```

2. **检查相关 Logger**：
   ```python
   # 确认相关库的 logger 已配置
   logging.getLogger('agno').setLevel(logging.DEBUG)
   logging.getLogger('httpx').setLevel(logging.DEBUG)
   ```

3. **查看日志文件**：
   ```bash
   # 查看是否有 DEBUG 日志
   grep "DEBUG" logs/最新日志.log | head -20
   ```

### 日志文件过大

如果单个日志文件过大（> 100MB），考虑：
- 分批处理工具（使用 --limit）
- 使用并发模式减少单次运行时间
- 定期清理旧日志

## 最佳实践

1. **每次运行前查看最新日志**
   ```bash
   python view_logs.py --analyze
   ```

2. **出现问题时查看错误日志**
   ```bash
   python view_logs.py --latest --grep "ERROR"
   ```

3. **定期分析日志了解系统运行状况**
   ```bash
   python view_logs.py --analyze
   ```

4. **保留重要的日志文件**
   ```bash
   cp logs/20241206_143022_beijing.log logs/important_run_备份.log
   ```

## 更多帮助

- 主文档: [README.md](README.md)
- 改进说明: [IMPROVEMENTS.md](IMPROVEMENTS.md)
- 快速参考: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

