# 🔬 开源科学工具自动化部署系统

基于 [Agno](https://github.com/agno-agi/agno) 框架的智能工作流，用于自动化分析、生成 Dockerfile 并部署开源科学计算工具。

## ✨ 功能特性

- **智能仓库分析**: 自动克隆仓库，分析项目结构，识别技术栈和依赖
- **Dockerfile 生成**: 根据项目特点生成最优的 Dockerfile
- **自动化验证**: 构建镜像并验证服务运行状态
- **批量处理**: 支持批量部署多个工具
- **错误反馈**: 智能分析错误并提供修复建议
- **结果追踪**: 记录每个工具的部署状态和结果

## 📁 项目结构

```
repo_parse_dockerfile/
├── main.py                 # 主入口文件
├── workflow.py             # Agno Workflow 定义
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── list.md               # 工具列表
├── guide.md              # 任务指南
├── agents/               # Agno Agents
│   ├── repo_analyzer.py      # 仓库分析 Agent
│   ├── dockerfile_generator.py # Dockerfile 生成 Agent
│   └── verifier.py           # 验证 Agent
├── tools/                # 自定义工具
│   ├── terminal_tools.py     # 终端操作工具
│   ├── docker_tools.py       # Docker 操作工具
│   └── file_tools.py         # 文件操作工具
├── utils/                # 工具函数
│   └── list_parser.py        # list.md 解析器
├── repos/                # 克隆的仓库目录
├── results/              # 部署结果目录
└── logs/                 # 日志目录
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd repo_parse_dockerfile
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# LLM 配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Docker 配置
DOCKER_TIMEOUT=600
DOCKER_MEMORY_LIMIT=4g

# Git 配置
GIT_CLONE_DEPTH=1
GIT_TIMEOUT=300

# 工作流配置
MAX_RETRIES=3
```

### 3. 确保 Docker 运行中

```bash
docker info
```

## 📖 使用方法

### 交互模式（推荐）

```bash
python main.py --interactive
# 或直接运行
python main.py
```

### 部署单个工具

```bash
# 按名称（从 list.md 查找）
python main.py --tool "scikit-fem"

# 按仓库 URL
python main.py --url "https://github.com/kinnala/scikit-fem"

# 仅分析不验证
python main.py --tool "scikit-fem" --skip-verify
```

### 批量部署

```bash
# 部署前 5 个工具
python main.py --batch --limit 5

# 按领域过滤
python main.py --batch --domain "生物信息" --limit 10

# 跳过验证（仅生成 Dockerfile）
python main.py --batch --limit 10 --skip-verify
```

### 列出可用工具

```bash
python main.py --list
python main.py --list --domain "材料"
```

## 🔄 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      RepoDeploymentWorkflow                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   阶段 1     │    │   阶段 2     │    │   阶段 3     │      │
│  │  仓库分析    │───▶│ Dockerfile  │───▶│  构建验证    │      │
│  │             │    │   生成       │    │             │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  • git clone         • 选择模板          • 构建镜像            │
│  • 分析结构          • 自定义配置         • 运行容器            │
│  • 查找 Dockerfile   • 处理依赖          • 健康检查            │
│  • 读取 README       • 保存文件          • 错误分析            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🤖 Agent 说明

### RepoAnalyzer (仓库分析专家)

负责：
- 克隆 Git 仓库
- 分析项目结构
- 识别技术栈和依赖
- 确定部署策略

### DockerfileGenerator (Dockerfile 生成专家)

负责：
- 选择合适的基础镜像
- 生成优化的 Dockerfile
- 处理科学计算特殊依赖

### DockerVerifier (Docker 验证专家)

负责：
- 构建 Docker 镜像
- 运行和验证容器
- 分析错误并提供修复建议

## 📝 支持的语言和框架

| 语言 | 依赖管理 | 模板 |
|------|---------|------|
| Python | pip, conda, poetry | ✅ |
| JavaScript | npm, yarn, pnpm | ✅ |
| Rust | cargo | ✅ |
| Go | go mod | ✅ |
| C/C++ | cmake, make | ✅ |
| R | DESCRIPTION | ⚠️ |
| Julia | Project.toml | ⚠️ |

## 🔧 自定义配置

### 添加新的 Dockerfile 模板

编辑 `agents/dockerfile_generator.py` 中的 `DOCKERFILE_TEMPLATES` 字典。

### 添加新工具

在 `list.md` 中按格式添加：

```
话题
领域
工具名
版本号
GitHub/GitLab URL
文档链接（可选）
外部数据依赖（可选）
```

## 📊 结果输出

### 部署结果

部署结果保存在 `results/` 目录，格式为 JSON：

```json
{
  "tool_name": "scikit-fem",
  "repo_url": "https://github.com/kinnala/scikit-fem",
  "status": "success",
  "local_path": "/path/to/repos/scikit-fem",
  "dockerfile_path": "/path/to/repos/scikit-fem/Dockerfile.generated",
  "image_name": "scitools/scikit-fem",
  "started_at": "2024-01-01T00:00:00",
  "completed_at": "2024-01-01T00:05:00"
}
```

### 运行日志

系统会自动保存所有运行日志到 `logs/` 目录，使用北京时间（UTC+8）作为时间戳命名：

```
logs/
├── 20241206_143022_beijing.log
├── 20241206_160145_beijing.log
└── ...
```

**查看日志**：

```bash
# 列出所有日志
python view_logs.py

# 查看最新日志
python view_logs.py --latest

# 只看错误
python view_logs.py --latest --grep "ERROR"

# 分析统计
python view_logs.py --analyze
```

详细说明请查看 [LOGGING.md](LOGGING.md)

## ⚠️ 注意事项

1. **API 额度**: 每个工具的分析和生成会消耗 OpenAI API 额度
2. **磁盘空间**: 克隆仓库和构建镜像需要足够的磁盘空间
3. **网络环境**: 部分仓库可能需要科学上网
4. **Docker 资源**: 构建和运行容器需要足够的内存和 CPU

## 🐛 故障排除

### 常见问题

1. **Docker 连接失败**
   ```bash
   # 确保 Docker Desktop 运行中
   docker info
   ```

2. **Git 克隆失败**
   ```bash
   # 检查网络连接
   git ls-remote https://github.com/xxx/yyy
   ```

3. **构建超时**
   ```bash
   # 调整超时设置
   export DOCKER_TIMEOUT=1200
   ```

## 📄 License

MIT License

