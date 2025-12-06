"""
Docker 操作工具 - 用于构建镜像、运行容器、验证等
"""
import docker
import time
from pathlib import Path
from typing import Optional
from config import DOCKER_TIMEOUT, DOCKER_MEMORY_LIMIT


def get_docker_client():
    """获取 Docker 客户端"""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        raise ConnectionError(f"无法连接到 Docker: {e}")


def _detect_build_context(dockerfile_path: Path) -> tuple[str, str]:
    """
    智能检测 Docker build context
    
    Args:
        dockerfile_path: Dockerfile 的路径
    
    Returns:
        tuple: (context_path, relative_dockerfile_path)
    """
    # 读取 Dockerfile 内容分析 COPY/ADD 指令
    try:
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有包含仓库名的 COPY/ADD 指令
        # 例如: COPY dolfinx/docker/some-file 或 COPY ./dolfinx/
        import re
        copy_pattern = r'(?:COPY|ADD)\s+(\S+)'
        matches = re.findall(copy_pattern, content, re.IGNORECASE)
        
        if matches:
            for match in matches:
                # 如果路径包含多层级（如 xxx/yyy/zzz），说明需要更高层的 context
                parts = match.strip().split('/')
                if len(parts) >= 2 and not match.startswith(('http://', 'https://', '--')):
                    # 找到第一个路径部分，检查是否是仓库名
                    first_part = parts[0]
                    
                    # 尝试找到仓库根目录
                    current = dockerfile_path.parent
                    for _ in range(5):  # 最多向上查找5层
                        if (current.parent / first_part).exists():
                            # 找到了！使用这个目录作为 context
                            context_path = str(current.parent)
                            relative_dockerfile = str(dockerfile_path.relative_to(current.parent))
                            return context_path, relative_dockerfile
                        current = current.parent
    except Exception:
        pass
    
    # 默认行为：使用 Dockerfile 的父目录
    return str(dockerfile_path.parent), dockerfile_path.name


def build_docker_image(
    dockerfile_path: str,
    image_name: str,
    tag: str = "latest",
    build_args: Optional[dict] = None,
    no_cache: bool = False,
    timeout: int = DOCKER_TIMEOUT,
    context_path: Optional[str] = None
) -> dict:
    """
    构建 Docker 镜像
    
    Args:
        dockerfile_path: Dockerfile 路径或包含 Dockerfile 的目录
        image_name: 镜像名称
        tag: 镜像标签
        build_args: 构建参数
        no_cache: 是否禁用缓存
        timeout: 构建超时时间
        context_path: 可选的构建上下文路径（如不指定则自动检测）
    
    Returns:
        dict: 包含 success, image_id, logs, error
    """
    try:
        client = get_docker_client()
        
        path = Path(dockerfile_path)
        
        # 如果指定了 context_path，使用它
        if context_path:
            build_context = context_path
            if path.is_file():
                dockerfile = str(path.relative_to(Path(context_path)))
            else:
                dockerfile = "Dockerfile"
        elif path.is_file():
            # 智能检测 build context
            build_context, dockerfile = _detect_build_context(path)
        else:
            build_context = str(path)
            dockerfile = "Dockerfile"
        
        full_tag = f"{image_name}:{tag}"
        
        # 构建镜像
        image, logs = client.images.build(
            path=build_context,
            dockerfile=dockerfile,
            tag=full_tag,
            buildargs=build_args or {},
            nocache=no_cache,
            timeout=timeout,
            rm=True  # 构建后删除中间容器
        )
        
        # 收集构建日志
        build_logs = []
        for chunk in logs:
            if 'stream' in chunk:
                build_logs.append(chunk['stream'].strip())
        
        return {
            "success": True,
            "image_id": image.id,
            "image_tag": full_tag,
            "logs": "\n".join(build_logs[-50:]),  # 只保留最后50行
            "error": None
        }
        
    except docker.errors.BuildError as e:
        return {
            "success": False,
            "image_id": None,
            "image_tag": None,
            "logs": str(e.build_log) if hasattr(e, 'build_log') else "",
            "error": f"构建失败: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "image_id": None,
            "image_tag": None,
            "logs": "",
            "error": f"构建异常: {str(e)}"
        }


def run_docker_container(
    image_name: str,
    container_name: Optional[str] = None,
    command: Optional[str] = None,
    ports: Optional[dict] = None,
    environment: Optional[dict] = None,
    volumes: Optional[dict] = None,
    detach: bool = True,
    remove: bool = False,
    memory_limit: str = DOCKER_MEMORY_LIMIT
) -> dict:
    """
    运行 Docker 容器
    
    Args:
        image_name: 镜像名称
        container_name: 容器名称
        command: 运行命令
        ports: 端口映射 {"8080/tcp": 8080}
        environment: 环境变量
        volumes: 卷映射
        detach: 是否后台运行
        remove: 运行完成后是否删除
        memory_limit: 内存限制
    
    Returns:
        dict: 包含 success, container_id, status, error
    """
    try:
        client = get_docker_client()
        
        # 如果容器名已存在，先删除
        if container_name:
            try:
                existing = client.containers.get(container_name)
                existing.remove(force=True)
            except docker.errors.NotFound:
                pass
        
        container = client.containers.run(
            image_name,
            command=command,
            name=container_name,
            ports=ports,
            environment=environment or {},
            volumes=volumes or {},
            detach=detach,
            remove=remove,
            mem_limit=memory_limit
        )
        
        # 等待容器启动
        time.sleep(2)
        container.reload()
        
        return {
            "success": True,
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "error": None
        }
        
    except docker.errors.ContainerError as e:
        return {
            "success": False,
            "container_id": None,
            "status": "error",
            "error": f"容器运行错误: {e.stderr}"
        }
    except docker.errors.ImageNotFound:
        return {
            "success": False,
            "container_id": None,
            "status": "error",
            "error": f"镜像不存在: {image_name}"
        }
    except Exception as e:
        return {
            "success": False,
            "container_id": None,
            "status": "error",
            "error": f"运行异常: {str(e)}"
        }


def check_container_status(container_id_or_name: str) -> dict:
    """
    检查容器状态
    
    Args:
        container_id_or_name: 容器 ID 或名称
    
    Returns:
        dict: 包含 success, status, running, health, error
    """
    try:
        client = get_docker_client()
        container = client.containers.get(container_id_or_name)
        container.reload()
        
        return {
            "success": True,
            "status": container.status,
            "running": container.status == "running",
            "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
            "error": None
        }
        
    except docker.errors.NotFound:
        return {
            "success": False,
            "status": "not_found",
            "running": False,
            "error": f"容器不存在: {container_id_or_name}"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "running": False,
            "error": str(e)
        }


def get_docker_logs(
    container_id_or_name: str,
    tail: int = 100,
    timestamps: bool = False
) -> dict:
    """
    获取容器日志
    
    Args:
        container_id_or_name: 容器 ID 或名称
        tail: 获取最后多少行
        timestamps: 是否包含时间戳
    
    Returns:
        dict: 包含 success, logs, error
    """
    try:
        client = get_docker_client()
        container = client.containers.get(container_id_or_name)
        
        logs = container.logs(tail=tail, timestamps=timestamps)
        logs_str = logs.decode('utf-8', errors='replace')
        
        return {
            "success": True,
            "logs": logs_str,
            "error": None
        }
        
    except docker.errors.NotFound:
        return {
            "success": False,
            "logs": "",
            "error": f"容器不存在: {container_id_or_name}"
        }
    except Exception as e:
        return {
            "success": False,
            "logs": "",
            "error": str(e)
        }


def cleanup_container(container_id_or_name: str, remove_image: bool = False) -> dict:
    """
    清理容器（停止并删除）
    
    Args:
        container_id_or_name: 容器 ID 或名称
        remove_image: 是否同时删除镜像
    
    Returns:
        dict: 包含 success, message, error
    """
    try:
        client = get_docker_client()
        container = client.containers.get(container_id_or_name)
        
        image_id = container.image.id if remove_image else None
        
        # 停止并删除容器
        container.stop(timeout=10)
        container.remove()
        
        message = f"容器 {container_id_or_name} 已清理"
        
        # 可选删除镜像
        if remove_image and image_id:
            try:
                client.images.remove(image_id, force=True)
                message += f", 镜像 {image_id[:12]} 已删除"
            except:
                pass
        
        return {
            "success": True,
            "message": message,
            "error": None
        }
        
    except docker.errors.NotFound:
        return {
            "success": True,
            "message": f"容器 {container_id_or_name} 不存在或已删除",
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": "",
            "error": str(e)
        }


def pull_docker_image(image_name: str, tag: str = "latest") -> dict:
    """
    拉取 Docker 镜像
    
    Args:
        image_name: 镜像名称
        tag: 镜像标签
    
    Returns:
        dict: 包含 success, image_id, error
    """
    try:
        client = get_docker_client()
        
        full_name = f"{image_name}:{tag}"
        image = client.images.pull(image_name, tag=tag)
        
        return {
            "success": True,
            "image_id": image.id,
            "image_name": full_name,
            "error": None
        }
        
    except docker.errors.ImageNotFound:
        return {
            "success": False,
            "image_id": None,
            "error": f"镜像不存在: {image_name}:{tag}"
        }
    except Exception as e:
        return {
            "success": False,
            "image_id": None,
            "error": str(e)
        }

