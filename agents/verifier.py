"""
验证 Agent - 负责构建和验证 Docker 镜像
"""
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
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


def create_verifier_agent() -> Agent:
    """
    创建验证 Agent
    
    该 Agent 负责:
    1. 构建 Docker 镜像
    2. 运行容器
    3. 验证服务状态
    4. 错误诊断和反馈
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
        ],
        description="Docker 构建和验证专家，负责构建镜像并验证服务运行状态",
        instructions=[
            "你是一个 Docker 运维专家，负责构建和验证容器化部署。",
            "",
            "## 验证流程",
            "1. 构建 Docker 镜像",
            "2. 如果构建失败，分析错误日志并提供修复建议",
            "3. 运行容器",
            "4. 检查容器状态和日志",
            "5. 验证服务是否正常启动",
            "",
            "## 错误处理",
            "- 仔细分析构建和运行错误",
            "- 提供具体的修复建议",
            "- 如果是依赖问题，建议添加缺失的依赖",
            "- 如果是配置问题，建议正确的配置方式",
            "",
            "## 输出要求",
            "- 明确报告验证结果（成功/失败）",
            "- 如果失败，提供详细的错误分析和修复建议",
            "- 如果成功，确认服务状态和访问方式",
        ],
        show_tool_calls=True,
        markdown=True,
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

