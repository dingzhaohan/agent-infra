# 批量部署报告功能

## 概述

批量部署完成后，系统会自动生成汇总报告，无需占用 LLM 上下文，直接基于 `results/` 目录中的结果文件生成。

## 自动生成

批量部署完成后会**自动生成**三种格式的报告：

1. **控制台输出**：实时显示统计信息
2. **JSON 报告**：保存到 `results/batch_report_YYYYMMDD_HHMMSS.json`
3. **Markdown 报告**：保存到 `results/batch_report_YYYYMMDD_HHMMSS.md`

### 示例

```bash
# 运行批量部署
python main.py --batch --limit 10

# 部署完成后自动显示报告
# 同时自动生成 JSON 和 Markdown 文件
```

## 手动生成报告

也可以随时手动生成报告：

```bash
# 控制台输出
python generate_batch_report.py

# 生成 JSON 报告
python generate_batch_report.py --format json

# 生成 Markdown 报告
python generate_batch_report.py --format markdown

# 关联特定日志文件
python generate_batch_report.py --log 20241206_143022_beijing.log --format json
```

## 报告内容

### 1. 统计信息

- **总工具数**：处理的工具总数
- **成功**：成功部署的工具数量和百分比
- **失败**：失败的工具数量和百分比
- **跳过**：跳过的工具数量和百分比（如私有仓库）

### 2. 成功列表

列出所有成功部署的工具：
- 工具名称
- 镜像名称
- 重试次数（如果有）

### 3. 失败列表

列出所有失败的工具：
- 工具名称
- 错误信息摘要

### 4. 跳过列表

列出所有跳过的工具：
- 工具名称
- 跳过原因（如需要认证访问）

## 报告格式

### JSON 格式

```json
{
  "generated_at": "2024-12-06 16:02:04",
  "log_file": "20241206_143022_beijing.log",
  "summary": {
    "total": 10,
    "success": 7,
    "failed": 2,
    "skipped": 1
  },
  "success_rate": "70.0%",
  "by_status": {
    "success": ["tool1", "tool2", ...],
    "failed": ["tool3", "tool4"],
    "skipped": ["tool5"]
  },
  "details": [
    {
      "tool_name": "tool1",
      "status": "success",
      "image_name": "scitools/tool1",
      ...
    }
  ]
}
```

### Markdown 格式

```markdown
# 批量部署汇总报告

**生成时间**: 2024-12-06 16:02:04 (北京时间)
**日志文件**: `20241206_143022_beijing.log`

## 📊 统计信息

- **总工具数**: 10
- **成功率**: 70.0%
- ✅ **成功**: 7
- ❌ **失败**: 2
- ⏭️ **跳过**: 1

## ✅ 成功的工具 (7 个)

- **tool1**
  - 镜像: `scitools/tool1`
- **tool2** *(重试 2 次)*
  - 镜像: `scitools/tool2`

## ❌ 失败的工具 (2 个)

- **tool3**
  - 错误: 构建超时
- **tool4**
  - 错误: 依赖安装失败

## ⏭️ 跳过的工具 (1 个)

- **tool5**
  - 原因: 需要认证访问（私有仓库）
```

## 私有仓库跳过功能

系统会自动检测并跳过需要认证的仓库（如 GitLab 私有仓库）：

### 检测的错误模式

- `Authentication failed`
- `Access denied`
- `Permission denied`
- `fatal: could not read Username`
- `private repository`
- `Repository not found`
- `HTTP Basic: Access denied`

### 跳过行为

1. Git 克隆失败时检测认证错误
2. 标记状态为 `skipped`
3. 记录跳过原因
4. 继续处理其他工具
5. 在报告中单独列出

### 日志示例

```
⏭️ 跳过需要认证的仓库: private-tool
原因: 需要认证访问（私有仓库/GitLab），已跳过
```

## 报告文件位置

```
agent-infra/
├── results/
│   ├── batch_report_20241206_143022.json
│   ├── batch_report_20241206_143022.md
│   ├── batch_report_20241206_160204.json
│   └── batch_report_20241206_160204.md
```

## 与日志系统的关系

报告生成**不依赖**日志文件，而是基于 `results/` 目录中的 JSON 文件：

- ✅ **优点**：不占用 LLM 上下文
- ✅ **快速**：直接读取文件，无需重新分析
- ✅ **准确**：基于实际执行结果

但可以关联日志文件以便查看详细过程：

```bash
python generate_batch_report.py --log 20241206_143022_beijing.log --format markdown
```

## 实际使用示例

### 示例 1: 批量部署后查看报告

```bash
# 1. 批量部署
python main.py --batch --limit 20

# 报告自动生成并显示
# 同时保存到 results/batch_report_*.json 和 *.md

# 2. 查看 JSON 报告
cat results/batch_report_*.json | jq

# 3. 查看 Markdown 报告
cat results/batch_report_*.md
```

### 示例 2: 定期生成报告

```bash
# 每次运行后都可以重新生成报告
python generate_batch_report.py

# 生成新的文件版本
python generate_batch_report.py --format json
python generate_batch_report.py --format markdown
```

### 示例 3: 对比不同时间的部署结果

```bash
# 查看最新报告
python generate_batch_report.py

# 查看历史报告
cat results/batch_report_20241206_100000.json | jq '.summary'
cat results/batch_report_20241206_160000.json | jq '.summary'
```

### 示例 4: 导出报告用于分享

```bash
# 生成 Markdown 报告
python generate_batch_report.py --format markdown

# 复制到其他位置
cp results/batch_report_*.md ~/deployment_reports/

# 或通过邮件发送
mail -s "部署报告" admin@example.com < results/batch_report_*.md
```

## 报告中的统计指标

| 指标 | 说明 |
|------|------|
| 总工具数 | 批量处理的工具总数 |
| 成功数 | 完全成功部署的工具 |
| 失败数 | 部署失败的工具 |
| 跳过数 | 因各种原因跳过的工具（如私有仓库） |
| 成功率 | 成功数 / 总工具数 × 100% |
| 重试次数 | 某个工具重试的次数（如果 > 1） |

## 故障排查

### 报告生成失败

```bash
# 检查 results 目录是否存在
ls -la results/

# 检查是否有结果文件
ls -la results/*.json

# 手动运行报告生成
python generate_batch_report.py
```

### 报告内容不完整

确保批量部署正常完成，每个工具都有对应的结果文件：

```bash
# 检查结果文件
ls results/*.json | grep -v batch_report

# 查看特定工具的结果
cat results/Nek5000.json | jq
```

### 跳过的工具太多

检查网络连接和仓库访问权限：

```bash
# 测试 Git 访问
git ls-remote https://github.com/xxx/yyy

# 查看详细错误
python view_logs.py --latest --grep "跳过"
```

## 最佳实践

1. **每次批量部署后查看报告**
   ```bash
   python main.py --batch --limit 10
   # 自动显示报告
   ```

2. **保存重要的报告文件**
   ```bash
   cp results/batch_report_*.json backup/important_run.json
   ```

3. **结合日志查看详细信息**
   ```bash
   python generate_batch_report.py  # 查看概览
   python view_logs.py --latest --grep "ERROR"  # 查看错误详情
   ```

4. **定期清理旧报告**
   ```bash
   # 保留最近 10 个报告
   ls -t results/batch_report_*.json | tail -n +11 | xargs rm -f
   ```

## 相关文档

- 日志系统: [LOGGING.md](LOGGING.md)
- 快速参考: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- 主文档: [README.md](README.md)

