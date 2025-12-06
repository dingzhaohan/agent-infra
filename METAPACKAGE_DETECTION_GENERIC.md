# 泛化的元仓库（Meta-package）检测

## 改进说明

### 问题：旧版本缺乏泛化性

旧版本的 `check_if_metapackage` 函数硬编码了 SuiteSparse 的子包列表：

```python
# ❌ 不好：硬编码特定项目的包名
suitesparse_subpackages = [
    "AMD", "BTF", "CAMD", "CCOLAMD", "COLAMD",
    "CHOLMOD", "CSparse", "CXSparse",
    "GraphBLAS", "LAGraph",
    ...
]
```

这导致：
- ❌ 只能识别 SuiteSparse
- ❌ 无法识别其他元仓库（如 Trilinos, Boost 等）
- ❌ 需要为每个新项目添加硬编码

### 解决方案：完全泛化的检测逻辑

新版本使用**通用的启发式规则**，不依赖任何硬编码的包名。

## 泛化的检测标准

### 1. 根目录构建文件检查

```python
has_root_cmake = (repo_path / "CMakeLists.txt").exists()
has_root_makefile = (repo_path / "Makefile").exists()
```

**条件**: 根目录必须有 `CMakeLists.txt` 或 `Makefile`

### 2. 自动扫描子包

```python
# 扫描所有一级子目录
for subdir in repo_path.iterdir():
    if subdir.is_dir():
        # 检查是否有构建文件
        if (subdir / "CMakeLists.txt").exists():
            subpackages.append(subdir.name)
        if (subdir / "Makefile").exists():
            subpackages.append(subdir.name)
```

**跳过目录**（排除非子包目录）：
- 版本控制：`.git`, `.github`, `.gitlab`, `.svn`
- 构建输出：`build`, `builds`, `_build`, `dist`, `out`, `bin`, `lib`
- 文档和测试：`docs`, `doc`, `examples`, `tests`, `test`
- 依赖管理：`node_modules`, `venv`, `.venv`, `__pycache__`

### 3. 分析根构建文件内容

#### CMakeLists.txt 分析

```python
# 查找 add_subdirectory() 命令
subdirs = re.findall(
    r'add_subdirectory\s*\(\s*([^)]+)\s*\)',
    cmake_content,
    re.IGNORECASE
)
```

**示例**：
```cmake
add_subdirectory(AMD)
add_subdirectory(CHOLMOD)
add_subdirectory(GraphBLAS)
```

#### Makefile 分析

```python
# 查找两种模式：
# 1. cd xxx && make
cd_patterns = re.findall(r'cd\s+([^\s;&|]+)\s+&&', makefile_content)

# 2. $(MAKE) -C xxx
make_c_patterns = re.findall(r'\$\(MAKE\)\s+-C\s+([^\s;&|]+)', makefile_content)
```

**示例**：
```makefile
( cd AMD && $(MAKE) )
( cd CHOLMOD && $(MAKE) )
$(MAKE) -C GraphBLAS
```

### 4. 判断逻辑

```python
is_metapackage = (
    # 有根构建文件
    (has_root_cmake or has_root_makefile) and
    # 满足以下任一条件：
    (
        subpackage_count >= 3 or              # 至少3个子包有构建文件
        (references_subdirs and referenced_count >= 3)  # 或根文件引用了3+子目录
    )
)
```

**判断标准**：
- ✅ 根目录有 CMakeLists.txt 或 Makefile
- ✅ **并且**满足以下之一：
  - 至少 **3 个**子目录有构建文件（CMakeLists.txt 或 Makefile）
  - 根构建文件引用了至少 **3 个**子目录

## 检测结果示例

### SuiteSparse（元仓库）

```json
{
  "is_metapackage": true,
  "has_root_cmake": true,
  "has_root_makefile": true,
  "subpackages_with_build_files": [
    "AMD", "BTF", "CAMD", "CCOLAMD", "CHOLMOD",
    "COLAMD", "CSparse", "CXSparse", "Example",
    "GraphBLAS", "KLU", "LAGraph", "LDL", "Mongoose",
    "ParU", "RBio", "SPEX", "SPQR", "SuiteSparse_config",
    "TestConfig", "UMFPACK", "ssget"
  ],
  "subpackage_count": 22,
  "referenced_directories": [
    "AMD", "BTF", "CAMD", "CCOLAMD", "CHOLMOD",
    "COLAMD", "CSparse", "CXSparse", "GraphBLAS",
    "KLU"
  ],
  "referenced_count": 20,
  "recommendation": "使用 cmake_metapackage 模板从根目录构建所有子包"
}
```

### FEBio（普通仓库）

```json
{
  "is_metapackage": false,
  "has_root_cmake": false,
  "has_root_makefile": false,
  "subpackages_with_build_files": [],
  "subpackage_count": 0,
  "reason": "根目录没有构建文件"
}
```

## 支持的元仓库类型

### 1. CMake 元仓库

**特征**：
- 根目录有 `CMakeLists.txt`
- 使用 `add_subdirectory()` 添加子包
- 每个子包有自己的 `CMakeLists.txt`

**示例**：
- SuiteSparse
- Trilinos
- Boost（部分）
- OpenCV

### 2. Make 元仓库

**特征**：
- 根目录有 `Makefile`
- 使用循环或多个 `cd` 命令进入子目录
- 每个子包有自己的 `Makefile`

**示例**：
- 旧版 GNU 工具链
- 某些 Linux 内核模块

### 3. 混合元仓库

**特征**：
- 根目录同时有 `CMakeLists.txt` 和 `Makefile`
- 两种构建方式都支持

**示例**：
- SuiteSparse（同时支持 CMake 和 Make）

## 优势

### ✅ 完全泛化

- 不需要硬编码任何项目名称
- 自动适应任何遵循类似模式的项目

### ✅ 鲁棒性强

- 多种检测方式（子包扫描 + 构建文件分析）
- 排除常见的非子包目录
- 正则表达式匹配多种语法

### ✅ 可扩展

- 容易添加新的检测模式
- 可调整阈值（目前是 3 个子包）

## 潜在的元仓库示例

基于这个泛化的检测逻辑，可以自动识别：

### 科学计算领域

1. **SuiteSparse** ✅ 已验证
   - 22 个子包（AMD, CHOLMOD, GraphBLAS 等）

2. **Trilinos** (未测试，但应该能识别)
   - 50+ 个包（Teuchos, Epetra, AztecOO 等）

3. **PETSc** (取决于结构)
   - 如果有多个子模块，可能被识别

4. **deal.II** (可能)
   - 如果包含多个独立构建的模块

### 其他领域

1. **LLVM/Clang**
   - 多个子项目（clang, lldb, lld 等）

2. **Qt**
   - 多个模块（qtbase, qtdeclarative 等）

3. **Boost**
   - 多个库（每个有独立构建）

## 使用方法

### 在 Agent 中自动使用

Agent 会自动调用 `check_if_metapackage`：

```python
# Agent 指令中包含：
"1. 首先使用 check_if_metapackage 检查是否是元仓库"
"2. 如果是元仓库，使用 cmake_metapackage 模板"
"3. 如果不是，按常规流程处理"
```

### 手动测试

```bash
python main.py --tool "YourProject" --skip-verify
```

Agent 会：
1. 自动检测项目结构
2. 如果是元仓库，使用 `cmake_metapackage` 模板
3. 如果不是，使用适合的常规模板

## 调优参数

### 子包数量阈值

当前：`>= 3` 个子包

```python
# 可以调整为更严格或宽松
subpackage_count >= 3  # 当前值
subpackage_count >= 2  # 更宽松（可能误识别）
subpackage_count >= 5  # 更严格（可能漏识别）
```

### 跳过目录列表

可以添加更多应该跳过的目录：

```python
skip_dirs = {
    '.git', '.github', '.gitlab', '.svn',  # VCS
    'build', 'bin', 'lib', 'include',      # 构建输出
    'docs', 'doc', 'examples', 'tests',    # 文档和测试
    'venv', 'node_modules', '__pycache__', # 依赖
    # 可以添加更多...
}
```

## 限制和注意事项

### 1. 假阳性（误识别）

可能误将普通项目识别为元仓库：

**场景**：项目有多个示例/插件目录，每个都有 CMakeLists.txt

**缓解措施**：
- 跳过 `examples`, `plugins`, `addons` 等目录
- 提高子包数量阈值
- 检查子包的复杂度（未实现）

### 2. 假阴性（漏识别）

可能漏掉某些元仓库：

**场景**：
- 子包数量少于 3 个
- 使用非标准的构建系统
- 子包在更深的目录层级

**缓解措施**：
- 降低阈值到 2
- 支持更多构建系统模式
- 支持多层目录扫描

### 3. 性能考虑

对于大型仓库（如 Linux 内核），扫描可能较慢

**优化**：
- 只扫描一级子目录（已实现）
- 跳过常见的大目录
- 可以添加缓存

## 总结

泛化的元仓库检测：

- ✅ **不依赖硬编码**：自动适应任何项目
- ✅ **多维度检测**：子包扫描 + 构建文件分析
- ✅ **鲁棒可靠**：排除常见干扰目录
- ✅ **易于扩展**：可调整阈值和规则

**适用于**：
- SuiteSparse ✅
- Trilinos ✅（理论上）
- LLVM ✅（理论上）
- 任何遵循类似模式的元仓库 ✅

相关文档：
- [METAPACKAGE_DETECTION.md](METAPACKAGE_DETECTION.md) - 元仓库概念和处理
- [BUGFIX_SUITESPARSE_METAPACKAGE.md](BUGFIX_SUITESPARSE_METAPACKAGE.md) - 原始问题

