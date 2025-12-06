# list_parser 使用说明

## 功能概述

`list_parser.py` 是一个通用工具列表解析器，支持从 **CSV** 或 **MD** 格式解析科学计算工具列表。

## 数据格式

### CSV 格式（推荐）

位置：`utils/list.csv`

```csv
话题,领域（大类/子类）,工具名,版本号,工具主页,文档链接,外部数据依赖（类型；无则空）
PDE / FEM,计算数学,dolfinx (FEniCSx),rolling,https://github.com/FEniCS/dolfinx,https://docs.fenicsproject.org/dolfinx/main/python/installation.html,
```

### MD 格式（兼容）

位置：`list.md`

每个工具条目占固定 7 行：
```
话题
领域（大类/子类）
工具名
版本号
工具主页
文档链接
外部数据依赖（类型；无则空）
```

## 使用方法

### 1. 基本使用 - 自动检测格式

```python
from utils.list_parser import parse_tools

# 自动检测并解析（优先使用 CSV）
tools = parse_tools()
print(f"解析到 {len(tools)} 个工具")
```

### 2. 指定文件路径

```python
from pathlib import Path
from utils.list_parser import parse_tools

# 解析指定的 CSV 文件
tools = parse_tools(Path("utils/list.csv"))

# 解析指定的 MD 文件
tools = parse_tools(Path("list.md"))
```

### 3. 直接调用特定解析器

```python
from utils.list_parser import parse_list_csv, parse_list_md

# 仅解析 CSV
tools = parse_list_csv()

# 仅解析 MD
tools = parse_list_md()
```

### 4. 查询和过滤

```python
from utils.list_parser import parse_tools, get_tools_by_domain, get_tools_by_name

tools = parse_tools()

# 按领域筛选
bio_tools = get_tools_by_domain(tools, "生物")
print(f"生物相关工具: {len(bio_tools)} 个")

# 按名称搜索
lammps = get_tools_by_name(tools, "LAMMPS")
if lammps:
    tool = lammps[0]
    print(f"{tool.name}: {tool.homepage}")
```

## Tool 数据类

每个工具被解析为 `Tool` 对象，包含以下字段：

```python
@dataclass
class Tool:
    topic: str                          # 话题
    domain: str                         # 领域（大类/子类）
    name: str                           # 工具名
    version: str                        # 版本号
    homepage: str                       # 工具主页 (GitHub/GitLab URL)
    docs_url: Optional[str] = None      # 文档链接
    external_data: Optional[str] = None # 外部数据依赖
```

### 属性方法

```python
tool = tools[0]

# 仓库名称
print(tool.repo_name)  # 从 URL 提取仓库名

# Git clone URL
print(tool.clone_url)  # 添加 .git 后缀

# 平台判断
if tool.is_github:
    print("这是 GitHub 项目")
if tool.is_gitlab:
    print("这是 GitLab 项目")
```

## 测试

运行测试脚本：

```bash
python test_list_parser.py
```

输出示例：
```
✅ 成功解析 121 个工具

统计信息:
- 总工具数: 121
- 有文档链接: 118 个
- 有外部依赖: 28 个
- GitHub 项目: 110 个
- GitLab 项目: 6 个
```

## 在其他模块中使用

### 在 workflow.py 中使用

```python
from utils.list_parser import parse_tools

def load_tools():
    """加载工具列表"""
    return parse_tools()

tools = load_tools()
for tool in tools:
    print(f"处理工具: {tool.name}")
    # ... 执行工作流
```

### 在 Dockerfile 生成器中使用

```python
from utils.list_parser import parse_tools

tools = parse_tools()
for tool in tools:
    if tool.is_github:
        dockerfile = generate_dockerfile(
            name=tool.name,
            git_url=tool.clone_url,
            version=tool.version
        )
```

## 数据完整性

解析器会自动验证：
- ✅ 必填字段（name, homepage）不能为空
- ✅ homepage 必须以 `http` 开头
- ✅ 空字符串自动转换为 `None`（docs_url, external_data）

## 文件检测优先级

`parse_tools()` 自动检测顺序：
1. `utils/list.csv`（优先）
2. `list.md`（回退）
3. 抛出 `FileNotFoundError`

## 迁移说明

### 从 MD 迁移到 CSV

如果您的项目正在从 MD 格式迁移到 CSV：

1. 保持两个文件都存在（解析器会优先使用 CSV）
2. 返回的 `Tool` 对象结构完全一致
3. 无需修改使用 `parse_tools()` 的代码

### CSV 的优势

- ✅ 结构清晰，每行一个工具
- ✅ 易于编辑和维护
- ✅ 支持标准 CSV 工具处理
- ✅ 不依赖固定行数格式
- ✅ 更容易与数据库集成

## 示例输出

```python
tool = tools[0]
print(f"""
工具信息:
  名称: {tool.name}
  话题: {tool.topic}
  领域: {tool.domain}
  版本: {tool.version}
  主页: {tool.homepage}
  文档: {tool.docs_url or '无'}
  外部依赖: {tool.external_data or '无'}
  仓库名: {tool.repo_name}
""")
```

输出：
```
工具信息:
  名称: dolfinx (FEniCSx)
  话题: PDE / FEM
  领域: 计算数学
  版本: rolling
  主页: https://github.com/FEniCS/dolfinx
  文档: https://docs.fenicsproject.org/dolfinx/main/python/installation.html
  外部依赖: 无
  仓库名: dolfinx
```

