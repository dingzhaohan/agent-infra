# 更新日志

## [2025-12-06] Dockerfile 交互性支持修复

### 问题
生成的 Dockerfile 构建的镜像不支持交互式使用：
- 无法使用 `docker run -it image /bin/bash` 进入容器
- 无法使用 `docker exec -it container /bin/bash` 
- 用户无法进行调试、开发和交互式实验

### 解决方案
更新所有 Dockerfile 模板以支持交互式使用：

1. **添加 bash 安装**: 确保所有模板都安装 bash
2. **设置默认 CMD**: `CMD ["/bin/bash"]` 让容器默认启动 bash
3. **避免 ENTRYPOINT**: 不使用限制性的 ENTRYPOINT
4. **Agent 指令更新**: 明确要求生成支持交互式使用的 Dockerfile

### 效果
- ✅ 用户可以直接运行 `docker run -it image` 进入 bash
- ✅ 用户可以使用 `docker exec -it container /bin/bash`
- ✅ 保持灵活性：用户仍可运行 `docker run image python script.py`
- ✅ Conda 环境自动激活

### 修改文件
- `agents/dockerfile_generator.py`: 更新所有交互式模板和 Agent instructions

### 受影响的模板
- `python_pip`, `python_conda`, `python_poetry`
- `scientific_python`, `cpp_cmake`

详细说明见: `DOCKERFILE_INTERACTIVE_FIX.md`

---

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
