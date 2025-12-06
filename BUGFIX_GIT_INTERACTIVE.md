# Git 交互式提示问题修复

## 问题描述

在克隆某些仓库（特别是 GitLab 私有仓库或需要认证的仓库）时，Git 会弹出交互式提示要求输入用户名和密码，导致程序卡住等待用户输入。

### 问题场景

1. **GitLab 私有仓库**: 没有公开访问权限的仓库
2. **需要 SSH 认证**: 使用 `git@` 格式的 URL
3. **需要 HTTP 认证**: 私有或受限访问的仓库

### 症状

```bash
# 程序卡在这里等待输入
Username for 'https://gitlab.com': _
Password for 'https://gitlab.com': _
```

系统无法继续，必须手动 Ctrl+C 中断。

## 之前的解决方案（不完善）

之前只在克隆**失败后**检测错误信息：

```python
# ❌ 问题：只在失败后检测，已经卡住了
result = run_shell_command("git clone ...")
if not result["success"]:
    if "Authentication" in error:
        # 已经太晚了，程序已经卡住
        return {"skipped": True}
```

**问题**: Git 会在克隆过程中等待交互式输入，程序已经卡住，错误检测来不及。

## 新的解决方案（多层防护）

### 1. 提前检测（预防）

在克隆前使用 `git ls-remote` 检查仓库是否可访问：

```python
# ✅ 提前检测
might_need_auth = any(re.search(pattern, repo_url) for pattern in [
    r'gitlab\.com/[^/]+/[^/]+(?!\.git$)',  # GitLab 可能的私有仓库
    r'git@',  # SSH 格式
    r'://[^@]+@',  # 带用户名的 URL
])

if might_need_auth:
    # 快速测试仓库是否可访问（10秒超时）
    test_cmd = f"git ls-remote --exit-code -h {repo_url}"
    test_result = run_shell_command(test_cmd, timeout=10)
    if not test_result["success"]:
        return {
            "success": False,
            "skipped": True,
            "error": "仓库需要认证访问或不存在，已跳过"
        }
```

**优点**: 
- `git ls-remote` 不会克隆任何内容，只检查仓库信息
- 10秒超时，快速失败
- 不会卡住等待输入

### 2. 禁用交互式提示（强制）

使用环境变量 `GIT_TERMINAL_PROMPT=0` 禁止 Git 弹出提示：

```python
# ✅ 禁用交互式提示
cmd_parts = ["GIT_TERMINAL_PROMPT=0", "git", "clone", ...]
```

**效果**: 
- Git 不会弹出用户名/密码提示
- 需要认证时立即失败，返回错误
- 不会卡住程序

### 3. 事后检测（兜底）

克隆失败后检测错误类型：

```python
# ✅ 兜底检测
if not result["success"]:
    error_output = result.get("stderr", "")
    
    auth_error_patterns = [
        "Authentication failed",
        "Access denied",
        "Permission denied",
        "terminal prompts disabled",  # GIT_TERMINAL_PROMPT=0 的错误
        # ...
    ]
    
    if any(pattern in error_output for pattern in auth_error_patterns):
        return {"skipped": True, "error": "需要认证"}
```

### 4. 异常抛出（通知上层）

在 Agent 工具函数中抛出异常，让 workflow 捕获：

```python
@tool
def clone_repository(repo_url: str, target_name: Optional[str] = None) -> str:
    result = git_clone(repo_url, target_name)
    
    # ✅ 如果被跳过，抛出异常让 workflow 知道
    if result.get("skipped"):
        raise Exception(f"需要认证访问（私有仓库/GitLab），已跳过: {repo_url}")
    
    return json.dumps(result, ensure_ascii=False)
```

## 完整流程

```
开始克隆仓库
    ↓
[第1层] 检测 URL 模式 → 可能需要认证？
    ↓ 是
    git ls-remote 快速测试 → 失败？
    ↓ 是
    返回 skipped=True，不再克隆 ✅
    ↓
[第2层] 设置 GIT_TERMINAL_PROMPT=0
    ↓
执行 git clone
    ↓
需要认证？→ 立即失败（不会弹提示）✅
    ↓
[第3层] 检测错误信息
    ↓
包含认证错误？→ 返回 skipped=True ✅
    ↓
[第4层] 抛出异常
    ↓
workflow 捕获 → 标记为 SKIPPED ✅
```

## 检测的 URL 模式

### 1. GitLab 可能的私有仓库

```python
r'gitlab\.com/[^/]+/[^/]+(?!\.git$)'
```

**示例**:
- ✅ `https://gitlab.com/user/private-repo` (可能私有)
- ✅ `https://gitlab.com/org/project` (可能私有)
- ⚠️ `https://gitlab.com/user/public.git` (会测试)

### 2. SSH 格式

```python
r'git@'
```

**示例**:
- ✅ `git@github.com:user/repo.git`
- ✅ `git@gitlab.com:org/project.git`

### 3. 带用户名的 URL

```python
r'://[^@]+@'
```

**示例**:
- ✅ `https://user@gitlab.com/org/repo`
- ✅ `http://username@server.com/repo.git`

## 环境变量说明

### GIT_TERMINAL_PROMPT=0

**作用**: 禁用 Git 的交互式终端提示

**效果**:
```bash
# 没有这个变量（默认）
$ git clone https://private-repo.git
Username: _  # ❌ 卡在这里等待输入

# 有这个变量
$ GIT_TERMINAL_PROMPT=0 git clone https://private-repo.git
fatal: could not read Username for 'https://...': terminal prompts disabled
# ✅ 立即失败，不会等待输入
```

**文档**: https://git-scm.com/docs/git#Documentation/git.txt-codeGITTERMINALPROMPTcode

## 测试用例

### 用例 1: 公开的 GitHub 仓库

```python
result = git_clone("https://github.com/user/public-repo.git")
# ✅ 正常克隆，success=True
```

### 用例 2: GitLab 私有仓库

```python
result = git_clone("https://gitlab.com/user/private-repo")
# 1. 检测到 GitLab 模式
# 2. git ls-remote 测试失败
# 3. 返回 skipped=True
# ✅ 不会卡住
```

### 用例 3: SSH 仓库（无密钥）

```python
result = git_clone("git@github.com:user/repo.git")
# 1. 检测到 SSH 模式
# 2. git ls-remote 测试失败
# 3. 返回 skipped=True
# ✅ 不会卡住
```

### 用例 4: 仓库已存在

```python
result = git_clone("https://github.com/user/repo.git", "repo")
# ✅ 直接返回已存在，跳过所有检查
```

## 修改的文件

1. **tools/terminal_tools.py**
   - `git_clone()` 函数
   - 添加提前检测逻辑
   - 添加 `GIT_TERMINAL_PROMPT=0`
   - 改进错误检测

2. **agents/repo_analyzer.py**
   - `clone_repository()` 工具函数
   - 添加异常抛出逻辑

3. **workflow.py** (已有)
   - 异常捕获和处理（已实现）

## 错误信息示例

### 成功跳过的情况

```json
{
  "success": false,
  "skipped": true,
  "path": "",
  "error": "仓库需要认证访问或不存在，已跳过",
  "message": "跳过可能需要认证的仓库: https://gitlab.com/user/private",
  "details": "fatal: could not read Username..."
}
```

### Workflow 日志

```
⏭️ 跳过需要认证的仓库: private-tool
原因: 需要认证访问（私有仓库/GitLab），已跳过
```

### 结果文件

```json
{
  "tool_name": "private-tool",
  "status": "skipped",
  "error_message": "需要认证访问（私有仓库），已跳过"
}
```

## 性能影响

- **提前检测**: 10秒超时，只针对可疑 URL
- **正常仓库**: 无额外开销（不触发检测）
- **环境变量**: 无性能影响

## 优势

1. ✅ **不会卡住**: 多层防护确保不会等待用户输入
2. ✅ **快速失败**: 10秒内检测并跳过
3. ✅ **明确原因**: 清楚记录跳过原因
4. ✅ **继续处理**: 不影响其他工具的部署
5. ✅ **向后兼容**: 不影响公开仓库的克隆

## 局限性

1. **误判可能**: 某些 GitLab 公开仓库可能被错误标记
   - **解决**: 只是快速测试，真正的公开仓库会通过
   
2. **网络超时**: `git ls-remote` 可能因网络问题超时
   - **解决**: 10秒超时足够快，不会长时间等待

3. **SSH 密钥**: 有 SSH 密钥的用户仍然会失败
   - **预期行为**: 系统设计为处理 HTTPS 公开仓库

## 相关命令

### 测试仓库是否可访问

```bash
# 测试公开仓库
git ls-remote --exit-code -h https://github.com/user/public-repo.git
# 返回: 0 (成功)

# 测试私有仓库
git ls-remote --exit-code -h https://gitlab.com/user/private-repo
# 返回: 非0 (失败)
```

### 测试禁用提示

```bash
# 尝试克隆私有仓库（禁用提示）
GIT_TERMINAL_PROMPT=0 git clone https://private-repo.git
# 输出: fatal: could not read Username... (立即失败)
```

## 总结

通过多层防护机制（提前检测 + 禁用提示 + 事后检测 + 异常抛出），彻底解决了 Git 交互式提示导致程序卡住的问题。

系统现在可以：
- ✅ 快速识别需要认证的仓库
- ✅ 自动跳过并继续处理其他工具
- ✅ 记录详细的跳过原因
- ✅ 不会卡住等待用户输入

修复后系统更加健壮和自动化！🎉

## 相关文档

- Git Environment Variables: https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables
- Git ls-remote: https://git-scm.com/docs/git-ls-remote

