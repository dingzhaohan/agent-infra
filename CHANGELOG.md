# 更新日志

## [2025-12-06] Docker Build Context 自动检测修复

### 问题
dolfinx 等项目的 Dockerfile 位于子目录（如 `repos/dolfinx/docker/Dockerfile.end-user`），但其中的 COPY 指令引用了相对于仓库根目录的路径（如 `COPY dolfinx/docker/file`），导致构建失败：
```
COPY failed: file not found in build context
```

### 解决方案
在 `tools/docker_tools.py` 中添加了智能 build context 检测：

1. **自动分析 Dockerfile**: 读取并解析 COPY/ADD 指令
2. **智能向上查找**: 自动找到能包含所有引用文件的正确 context
3. **自动调整路径**: 返回正确的 context 和相对 Dockerfile 路径

### 效果
- ✅ 自动修复 dolfinx 等复杂项目的构建
- ✅ 向后兼容，不影响现有简单项目
- ✅ 支持 monorepo 和多层目录结构

### 修改文件
- `tools/docker_tools.py`: 添加 `_detect_build_context()` 函数和增强 `build_docker_image()`

### 验证
```bash
# dolfinx 示例
Context: /repos/  (自动检测，之前错误地使用 /repos/dolfinx/docker/)
Dockerfile: dolfinx/docker/Dockerfile.end-user
✅ 所有 COPY 文件现在都能正确找到
```

详细说明见: `修复总结.md` 和 `DOCKER_BUILD_CONTEXT_FIX.md`
