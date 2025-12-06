"""
验证 Agent - 负责构建和验证 Docker 镜像
"""
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from typing import List, Optional
import json
import time

from config import OPENAI_MODEL, OPENAI_API_BASE, DOCKER_TIMEOUT
from tools.docker_tools import (
    build_docker_image,
    run_docker_container,
    check_container_status,
    get_docker_logs,
    cleanup_container,
    pull_docker_image
)
from tools.terminal_tools import run_shell_command


@tool
def build_image(
    dockerfile_path: str,
    image_name: str,
    tag: str = "latest",
    no_cache: bool = False
) -> str:
    """
    构建 Docker 镜像
    
    Args:
        dockerfile_path: Dockerfile 路径或包含 Dockerfile 的目录
        image_name: 镜像名称
        tag: 镜像标签
        no_cache: 是否禁用缓存
    
    Returns:
        构建结果 JSON
    """
    result = build_docker_image(
        dockerfile_path=dockerfile_path,
        image_name=image_name,
        tag=tag,
        no_cache=no_cache
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def run_container(
    image_name: str,
    container_name: str = None,
    command: str = None,
    ports: str = None,
    environment: str = None
) -> str:
    """
    运行 Docker 容器
    
    Args:
        image_name: 镜像名称
        container_name: 容器名称
        command: 运行命令
        ports: 端口映射 JSON (如 '{"8080/tcp": 8080}')
        environment: 环境变量 JSON (如 '{"KEY": "value"}')
    
    Returns:
        运行结果 JSON
    """
    ports_dict = json.loads(ports) if ports else None
    env_dict = json.loads(environment) if environment else None
    
    result = run_docker_container(
        image_name=image_name,
        container_name=container_name,
        command=command,
        ports=ports_dict,
        environment=env_dict
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def check_status(container_id_or_name: str) -> str:
    """
    检查容器运行状态
    
    Args:
        container_id_or_name: 容器 ID 或名称
    
    Returns:
        状态信息 JSON
    """
    result = check_container_status(container_id_or_name)
    return json.dumps(result, ensure_ascii=False)


@tool
def get_logs(container_id_or_name: str, tail: int = 100) -> str:
    """
    获取容器日志
    
    Args:
        container_id_or_name: 容器 ID 或名称
        tail: 获取最后多少行
    
    Returns:
        日志内容
    """
    result = get_docker_logs(container_id_or_name, tail=tail)
    if result["success"]:
        return result["logs"]
    else:
        return f"错误: {result.get('error', '无法获取日志')}"


@tool
def cleanup(container_id_or_name: str, remove_image: bool = False) -> str:
    """
    清理容器（停止并删除）
    
    Args:
        container_id_or_name: 容器 ID 或名称
        remove_image: 是否同时删除镜像
    
    Returns:
        清理结果
    """
    result = cleanup_container(container_id_or_name, remove_image=remove_image)
    return json.dumps(result, ensure_ascii=False)


@tool
def pull_image(image_name: str, tag: str = "latest") -> str:
    """
    从 Docker Hub 拉取镜像
    
    Args:
        image_name: 镜像名称
        tag: 镜像标签
    
    Returns:
        拉取结果 JSON
    """
    result = pull_docker_image(image_name, tag)
    return json.dumps(result, ensure_ascii=False)


@tool
def execute_in_container(container_id_or_name: str, command: str) -> str:
    """
    在运行中的容器内执行命令
    
    Args:
        container_id_or_name: 容器 ID 或名称
        command: 要执行的命令
    
    Returns:
        执行结果
    """
    cmd = f'docker exec {container_id_or_name} {command}'
    result = run_shell_command(cmd, timeout=60)
    return json.dumps(result, ensure_ascii=False)


@tool
def verify_service_health(
    container_id_or_name: str,
    check_type: str = "running",
    port: int = None,
    timeout: int = 30
) -> str:
    """
    验证服务健康状态
    
    Args:
        container_id_or_name: 容器 ID 或名称
        check_type: 检查类型 ("running", "http", "command")
        port: HTTP 检查的端口
        timeout: 超时时间
    
    Returns:
        健康检查结果 JSON
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status_result = check_container_status(container_id_or_name)
        
        if not status_result["success"]:
            return json.dumps({
                "healthy": False,
                "check_type": check_type,
                "error": status_result.get("error")
            }, ensure_ascii=False)
        
        if check_type == "running":
            if status_result["running"]:
                return json.dumps({
                    "healthy": True,
                    "check_type": check_type,
                    "status": status_result["status"]
                }, ensure_ascii=False)
        
        elif check_type == "http" and port:
            # 简单的 HTTP 健康检查
            cmd = f'docker exec {container_id_or_name} curl -sf http://localhost:{port}/ || true'
            result = run_shell_command(cmd, timeout=10)
            if result["success"] and result["return_code"] == 0:
                return json.dumps({
                    "healthy": True,
                    "check_type": check_type,
                    "port": port
                }, ensure_ascii=False)
        
        time.sleep(2)
    
    # 超时
    logs = get_docker_logs(container_id_or_name, tail=50)
    return json.dumps({
        "healthy": False,
        "check_type": check_type,
        "error": "健康检查超时",
        "logs": logs.get("logs", "") if isinstance(logs, dict) else logs
    }, ensure_ascii=False)


@tool
def report_verification_result(
    build_success: bool,
    container_running: bool,
    functional_test_success: bool,
    overall_status: str,
    error_summary: str = None,
    missing_dependencies: Optional[List[str]] = None,
    fix_suggestions: Optional[List[str]] = None
) -> str:
    """
    报告验证结果 - 必须在验证流程结束时调用此工具
    
    Args:
        build_success: 镜像构建是否成功
        container_running: 容器是否成功运行
        functional_test_success: 功能测试是否通过（检查工具/编译器是否可用）
        overall_status: 总体状态 ("success", "failed", "needs_fix")
        error_summary: 错误摘要（如果有）
        missing_dependencies: 缺失的依赖列表（如 ["gfortran", "gcc", "make"]）
        fix_suggestions: 修复建议列表
    
    Returns:
        确认消息
    """
    result = {
        "build_success": build_success,
        "container_running": container_running,
        "functional_test_success": functional_test_success,
        "overall_status": overall_status,
        "error_summary": error_summary,
        "missing_dependencies": missing_dependencies or [],
        "fix_suggestions": fix_suggestions or []
    }
    
    # 将结果保存到临时文件供 workflow 读取
    import tempfile
    import os
    temp_file = os.path.join(tempfile.gettempdir(), "verifier_result.json")
    with open(temp_file, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return json.dumps({
        "success": True,
        "message": "验证结果已记录",
        "result": result
    }, ensure_ascii=False)


def create_verifier_agent() -> Agent:
    """
    创建验证 Agent
    
    该 Agent 负责:
    1. 构建 Docker 镜像
    2. 运行容器
    3. 验证服务状态
    4. 功能性测试（检查工具是否真正可用）
    5. 错误诊断和反馈
    """
    return Agent(
        name="DockerVerifier",
        model=OpenAIChat(id=OPENAI_MODEL, base_url=OPENAI_API_BASE or None),
        tools=[
            build_image,
            run_container,
            check_status,
            get_logs,
            cleanup,
            pull_image,
            execute_in_container,
            verify_service_health,
            report_verification_result,
        ],
        description="Docker 构建和验证专家，负责构建镜像并进行全面的功能验证",
        instructions=[
            "你是一个 Docker 运维专家，负责构建和验证容器化部署。",
            "",
            "## 完整验证流程（必须按顺序执行）",
            "1. **构建镜像**：使用 build_image 构建 Docker 镜像",
            "2. **检查构建结果**：如果构建失败，分析错误日志并报告",
            "3. **运行容器**：使用 run_container 启动容器（建议使用 `tail -f /dev/null` 保持运行）",
            "4. **检查容器状态**：使用 check_status 确认容器正在运行",
            "5. **功能性测试（关键！）**：",
            "   - 对于科学计算工具，使用 execute_in_container 检查关键工具是否存在",
            "   - 必须测试的工具示例：gfortran, gcc, g++, make, cmake, mpicc, mpifort",
            "   - 使用命令如：`which gfortran`, `gcc --version`, `make --version`",
            "   - 如果是特定软件（如 Nek5000），测试其可执行文件或脚本是否存在",
            "   - 尝试运行简单的编译测试（如编译 hello world）",
            "6. **获取日志**：如果有问题，使用 get_logs 获取容器日志",
            "7. **报告结果**：**必须调用 report_verification_result** 报告最终结果",
            "",
            "## 科学计算工具的关键检查项",
            "对于科学计算/HPC 工具，必须验证以下依赖是否可用：",
            "- **编译器**：gfortran（Fortran）、gcc（C）、g++（C++）",
            "- **构建工具**：make、cmake",
            "- **MPI 支持**：mpicc、mpifort、mpirun（如果需要并行计算）",
            "- **科学库**：检查 HDF5、BLAS/LAPACK 等库的编译器包装器（h5pcc、h5fc）",
            "- **环境变量**：检查必要的环境变量是否设置（如 NEK_SOURCE_ROOT）",
            "",
            "## 判断标准（重要！）",
            "**验证成功的标准**：",
            "- 镜像构建成功 ✅",
            "- 容器可以运行 ✅",
            "- 所有关键工具/编译器存在且可用 ✅",
            "- 能够成功编译简单的测试程序（如果适用）✅",
            "",
            "**验证失败的标准（任何一项不满足）**：",
            "- 镜像构建失败 ❌",
            "- 容器无法运行 ❌",
            "- 缺少关键编译器或工具 ❌ （即使镜像构建成功）",
            "- 无法编译测试程序 ❌",
            "",
            "**如果镜像构建成功但缺少关键工具，必须报告为失败！**",
            "",
            "## 错误处理和修复建议",
            "当发现问题时，必须：",
            "1. 明确列出所有缺失的依赖（如 ['gfortran', 'gcc', 'make']）",
            "2. 提供具体的修复建议：",
            "   - 需要添加什么包（如 `apt-get install -y gfortran gcc make`）",
            "   - 需要设置什么环境变量",
            "   - 需要修改什么配置",
            "3. 给出修复后的验证方法",
            "",
            "## 报告要求（必须遵守）",
            "**在验证流程结束时，必须调用 report_verification_result 工具**：",
            "- 如果所有检查都通过：overall_status='success'",
            "- 如果构建失败或功能测试失败：overall_status='failed'",
            "- 如果需要修复 Dockerfile：overall_status='needs_fix'",
            "- 必须提供详细的 error_summary 和 fix_suggestions",
            "",
            "## 输出格式",
            "验证报告应包含：",
            "1. **验证步骤与结果**：每个步骤的执行情况",
            "2. **错误分析**：详细的错误原因分析",
            "3. **修复建议**：具体的、可操作的修复方案",
            "4. **验证流程**：修复后应如何再次验证",
        ],
        markdown=True,
        debug_mode=True,  # 显示调试信息
    )


class VerificationResult:
    """验证结果"""
    
    def __init__(
        self,
        tool_name: str,
        build_success: bool = False,
        image_id: str = None,
        container_id: str = None,
        container_running: bool = False,
        service_healthy: bool = False,
        verification_success: bool = False,
        error_message: str = None,
        fix_suggestions: list = None,
        logs: str = None
    ):
        self.tool_name = tool_name
        self.build_success = build_success
        self.image_id = image_id
        self.container_id = container_id
        self.container_running = container_running
        self.service_healthy = service_healthy
        self.verification_success = verification_success
        self.error_message = error_message
        self.fix_suggestions = fix_suggestions or []
        self.logs = logs
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "build_success": self.build_success,
            "image_id": self.image_id,
            "container_id": self.container_id,
            "container_running": self.container_running,
            "service_healthy": self.service_healthy,
            "verification_success": self.verification_success,
            "error_message": self.error_message,
            "fix_suggestions": self.fix_suggestions
        }

