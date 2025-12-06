# Verifier Agent Schema 错误修复

## 问题描述

在运行验证阶段时出现以下错误：

```
litellm.BadRequestError: AzureException BadRequestError - Invalid schema for function 
'report_verification_result': In context=('properties', 'missing_dependencies'), 
array schema missing items.
```

## 根本原因

OpenAI Function Calling API 要求所有 `array` 类型的参数必须明确指定 `items` 的类型。

原有代码使用了 Python 的 `list` 类型注解，但没有指定列表元素的类型：

```python
missing_dependencies: list = None  # ❌ 错误：没有指定 items 类型
fix_suggestions: list = None        # ❌ 错误：没有指定 items 类型
```

## 解决方案

将参数类型从 `list` 改为 `str`，使用分隔符分隔多个值：

### 修复前

```python
@tool
def report_verification_result(
    # ...
    missing_dependencies: list = None,  # ❌ 错误
    fix_suggestions: list = None        # ❌ 错误
) -> str:
    result = {
        "missing_dependencies": missing_dependencies or [],
        "fix_suggestions": fix_suggestions or []
    }
```

### 修复后

```python
@tool
def report_verification_result(
    # ...
    missing_dependencies: str = "",  # ✅ 正确：使用字符串
    fix_suggestions: str = ""        # ✅ 正确：使用字符串
) -> str:
    # 在函数内部转换为列表
    missing_deps_list = [dep.strip() for dep in missing_dependencies.split(",")] if missing_dependencies else []
    fix_suggestions_list = [fix.strip() for fix in fix_suggestions.split(";")] if fix_suggestions else []
    
    result = {
        "missing_dependencies": missing_deps_list,
        "fix_suggestions": fix_suggestions_list
    }
```

## 使用方式

Agent 调用时使用字符串格式：

```python
# 正确的调用方式
report_verification_result(
    build_success=True,
    container_running=True,
    functional_test_success=False,
    overall_status="needs_fix",
    error_summary="缺少编译工具",
    missing_dependencies="gfortran, gcc, make",  # 逗号分隔
    fix_suggestions="安装 gfortran; 安装 gcc 和 make"  # 分号分隔
)
```

## 格式说明

- **`missing_dependencies`**: 用**逗号**分隔的依赖列表
  - 示例: `"gfortran, gcc, make, cmake"`
  
- **`fix_suggestions`**: 用**分号**分隔的建议列表
  - 示例: `"安装编译器工具; 设置环境变量 NEK_SOURCE_ROOT; 验证工具是否可用"`

## 更新的 Agent 指令

在 `agents/verifier.py` 中更新了 Agent 指令，明确告知格式要求：

```python
instructions=[
    # ...
    "**参数格式要求**：",
    "- missing_dependencies: 用逗号分隔的字符串，如 'gfortran, gcc, make'",
    "- fix_suggestions: 用分号分隔的字符串，如 '安装gfortran; 设置环境变量'",
]
```

## 其他可能的解决方案（未采用）

### 方案 1: 使用 List[str] 类型注解

```python
from typing import List

missing_dependencies: List[str] = None  # 可能有效
```

**问题**: 不确定 Agno/LiteLLM 是否正确处理 `List[str]` 类型注解。

### 方案 2: 完全移除 list 参数

```python
# 只使用 error_summary 字符串
error_summary: str = "缺少: gfortran, gcc, make; 建议: ..."
```

**问题**: 失去了结构化数据，不利于程序化处理。

### 选择方案 3 的原因

- ✅ 兼容性最好（字符串类型）
- ✅ 保持结构化（在函数内部转换）
- ✅ 易于 Agent 理解和使用
- ✅ 结果仍然是结构化的列表

## 影响范围

### 修改的文件

- `agents/verifier.py` (1 个文件)

### 修改的函数

- `report_verification_result` 函数签名
- Agent 指令（添加格式说明）

### 影响的组件

- Verifier Agent 调用此函数时
- Workflow 读取验证结果时（无影响，因为最终存储的仍是列表）

## 测试验证

修复后，系统应该能够正常调用 `report_verification_result` 而不会出现 schema 错误。

可以通过以下方式验证：

```bash
# 运行包含验证步骤的部署
python main.py --tool "Nek5000"

# 或批量部署
python main.py --batch --limit 1
```

如果没有出现 "Invalid schema" 错误，说明修复成功。

## 经验教训

1. **Function Calling Schema 限制**: 
   - 必须明确指定所有类型
   - `array` 类型必须有 `items` 定义
   - 简单类型（string, number, boolean）最可靠

2. **类型注解的重要性**: 
   - Python 的类型注解会被转换为 OpenAI Function Schema
   - 使用不当会导致 API 调用失败

3. **向后兼容**: 
   - 修改后的版本仍然产生相同的结果
   - 只是输入格式从列表变为字符串

## 相关文档

- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- JSON Schema Specification: https://json-schema.org/

## 总结

通过将 `list` 类型参数改为 `str` 类型（使用分隔符），解决了 OpenAI Function Calling 的 schema 验证错误，同时保持了数据的结构化特性。

修复后系统应该可以正常运行验证流程。✅

