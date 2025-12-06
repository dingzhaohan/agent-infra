"""
主工作流 - 编排仓库分析、Dockerfile 生成和验证的完整流程
使用纯 Python 类实现，不依赖 Agno Workflow API（更稳定）
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, Callable
from enum import Enum
from dataclasses import dataclass

from config import REPOS_DIR, RESULTS_DIR, MAX_RETRIES
from utils.list_parser import Tool, parse_list_md
from agents.repo_analyzer import create_repo_analyzer_agent
from agents.dockerfile_generator import create_dockerfile_generator_agent
from agents.verifier import create_verifier_agent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """部署状态枚举"""
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    BUILDING = "building"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowMessage:
    """工作流消息"""
    content: str
    level: str = "info"  # info, warning, error, success
    
    def __str__(self):
        return self.content


@dataclass
class DeploymentResult:
    """单个工具的部署结果"""
    tool_name: str
    repo_url: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    local_path: str = ""
    has_existing_dockerfile: bool = False
    dockerfile_path: str = ""
    image_name: str = ""
    container_id: str = ""
    error_message: str = ""
    retry_count: int = 0
    started_at: datetime = None
    completed_at: datetime = None
    analysis_notes: str = ""
    generation_notes: str = ""
    verification_notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "repo_url": self.repo_url,
            "status": self.status.value,
            "local_path": self.local_path,
            "has_existing_dockerfile": self.has_existing_dockerfile,
            "dockerfile_path": self.dockerfile_path,
            "image_name": self.image_name,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class RepoDeploymentWorkflow:
    """
    开源仓库部署工作流
    
    该工作流负责：
    1. 克隆仓库
    2. 分析项目结构
    3. 生成或使用现有 Dockerfile
    4. 构建和验证镜像
    5. 记录结果
    """
    
    def __init__(self):
        """初始化工作流和 Agents"""
        self.analyzer_agent = None
        self.generator_agent = None
        self.verifier_agent = None
        self._agents_initialized = False
    
    def _init_agents(self):
        """延迟初始化 Agents（避免启动时加载）"""
        if not self._agents_initialized:
            self.analyzer_agent = create_repo_analyzer_agent()
            self.generator_agent = create_dockerfile_generator_agent()
            self.verifier_agent = create_verifier_agent()
            self._agents_initialized = True
    
    def run(
        self,
        tool: Tool,
        max_retries: int = MAX_RETRIES,
        skip_verification: bool = False
    ) -> Generator[WorkflowMessage, None, DeploymentResult]:
        """
        执行单个工具的部署工作流
        
        Args:
            tool: 要部署的工具信息
            max_retries: 最大重试次数
            skip_verification: 是否跳过验证步骤
        
        Yields:
            WorkflowMessage: 工作流进度消息
            
        Returns:
            DeploymentResult: 部署结果
        """
        # 初始化 Agents
        self._init_agents()
        
        result = DeploymentResult(
            tool_name=tool.name,
            repo_url=tool.homepage,
            started_at=datetime.now()
        )
        
        logger.info(f"开始处理工具: {tool.name}")
        
        try:
            # 阶段 1: 仓库分析
            for msg in self._analyze_repo(tool, result):
                yield msg
            
            if result.status == DeploymentStatus.FAILED:
                yield WorkflowMessage(
                    content=f"❌ 分析失败: {result.error_message}",
                    level="error"
                )
                return result
            
            # 阶段 2: Dockerfile 生成（如果需要）
            if not result.has_existing_dockerfile:
                for msg in self._generate_dockerfile(tool, result):
                    yield msg
                
                if result.status == DeploymentStatus.FAILED:
                    yield WorkflowMessage(
                        content=f"❌ Dockerfile 生成失败: {result.error_message}",
                        level="error"
                    )
                    return result
            
            # 阶段 3: 构建和验证
            if not skip_verification:
                for msg in self._verify_deployment(tool, result, max_retries):
                    yield msg
            else:
                result.status = DeploymentStatus.SKIPPED
                result.verification_notes = "跳过验证步骤"
            
            result.completed_at = datetime.now()
            
            # 保存结果
            self._save_result(result)
            
            # 最终输出
            if result.status == DeploymentStatus.SUCCESS:
                yield WorkflowMessage(
                    content=f"✅ 工具 {tool.name} 部署成功!\n"
                            f"镜像: {result.image_name}\n"
                            f"Dockerfile: {result.dockerfile_path}",
                    level="success"
                )
            elif result.status == DeploymentStatus.SKIPPED:
                yield WorkflowMessage(
                    content=f"⏭️ 工具 {tool.name} 分析完成（跳过验证）\n"
                            f"Dockerfile: {result.dockerfile_path}",
                    level="info"
                )
            else:
                yield WorkflowMessage(
                    content=f"❌ 工具 {tool.name} 部署失败\n"
                            f"错误: {result.error_message}",
                    level="error"
                )
                
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            self._save_result(result)
            
            yield WorkflowMessage(
                content=f"❌ 工作流异常: {str(e)}",
                level="error"
            )
        
        return result
    
    def _analyze_repo(
        self,
        tool: Tool,
        result: DeploymentResult
    ) -> Generator[WorkflowMessage, None, None]:
        """分析仓库阶段"""
        result.status = DeploymentStatus.ANALYZING
        
        yield WorkflowMessage(
            content=f"🔍 正在分析仓库: {tool.name} ({tool.homepage})",
            level="info"
        )
        
        # 设置本地路径
        result.local_path = str(REPOS_DIR / tool.repo_name)
        
        # 构建分析提示
        analysis_prompt = f"""
请分析以下开源工具仓库：

**工具名称**: {tool.name}
**仓库地址**: {tool.homepage}
**文档地址**: {tool.docs_url or '无'}
**版本**: {tool.version}
**领域**: {tool.domain}
**外部数据依赖**: {tool.external_data or '无'}

请执行以下步骤：
1. 克隆仓库到本地（目录名使用: {tool.repo_name}）
2. 分析项目结构
3. 查找现有的 Dockerfile
4. 读取 README 了解安装方式
5. 确定依赖管理方式和主要技术栈
6. 给出部署策略建议

请详细报告分析结果。
"""
        
        # 运行分析 Agent
        try:
            response = self.analyzer_agent.run(analysis_prompt)
            logger.info(f"分析 Agent 响应完成")
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.error_message = f"分析 Agent 错误: {str(e)}"
            yield WorkflowMessage(
                content=f"❌ 分析 Agent 错误: {str(e)}",
                level="error"
            )
            return
        
        # 验证仓库是否成功克隆
        repo_path = Path(result.local_path)
        if not repo_path.exists():
            result.status = DeploymentStatus.FAILED
            result.error_message = f"仓库克隆失败，路径不存在: {result.local_path}"
            yield WorkflowMessage(
                content=f"❌ 仓库克隆失败: {result.local_path}",
                level="error"
            )
            return
        
        # 检查是否找到 Dockerfile
        from tools.file_tools import find_dockerfile
        dockerfile_result = find_dockerfile(result.local_path)
        
        if dockerfile_result["found"]:
            result.has_existing_dockerfile = True
            result.dockerfile_path = dockerfile_result["primary_dockerfile"]
            result.analysis_notes = f"找到现有 Dockerfile: {result.dockerfile_path}"
            
            # 验证 Dockerfile 文件确实存在
            if not Path(result.dockerfile_path).exists():
                logger.warning(f"Dockerfile 路径无效: {result.dockerfile_path}")
                result.has_existing_dockerfile = False
                result.dockerfile_path = ""
                result.analysis_notes = "Dockerfile 路径无效，需要生成"
        else:
            result.has_existing_dockerfile = False
            result.dockerfile_path = ""
            result.analysis_notes = "未找到 Dockerfile，需要生成"
        
        yield WorkflowMessage(
            content=f"📋 分析完成\n"
                    f"本地路径: {result.local_path}\n"
                    f"现有 Dockerfile: {'是' if result.has_existing_dockerfile else '否'}\n"
                    f"{result.analysis_notes}",
            level="info"
        )
    
    def _generate_dockerfile(
        self,
        tool: Tool,
        result: DeploymentResult
    ) -> Generator[WorkflowMessage, None, None]:
        """生成 Dockerfile 阶段"""
        result.status = DeploymentStatus.GENERATING
        
        yield WorkflowMessage(
            content=f"📝 正在为 {tool.name} 生成 Dockerfile...",
            level="info"
        )
        
        # 获取依赖信息
        from tools.file_tools import find_dependency_files, find_readme
        
        dep_info = find_dependency_files(result.local_path)
        readme_info = find_readme(result.local_path)
        
        # 预期的 Dockerfile 路径
        expected_dockerfile_path = Path(result.local_path) / "Dockerfile.generated"
        
        # 构建生成提示
        generation_prompt = f"""
请为以下项目生成 Dockerfile：

**工具名称**: {tool.name}
**本地路径**: {result.local_path}
**主要语言**: {dep_info.get('primary_language', '未知')}
**依赖文件**: {json.dumps(dep_info.get('files', []), ensure_ascii=False)}
**领域**: {tool.domain}

**README 摘要**:
{readme_info.get('content', '无')[:2000]}

请根据以上信息：
1. 选择合适的 Dockerfile 模板
2. 根据项目特点自定义配置
3. 添加必要的系统依赖（特别是科学计算相关的）
4. 生成完整的 Dockerfile 并保存到仓库目录（文件名：Dockerfile.generated）

如果是科学计算工具，请特别注意：
- 可能需要 BLAS/LAPACK 库
- 可能需要 Fortran 编译器
- 可能需要 HDF5 支持
- 可能需要 MPI 并行支持

**重要**: 请使用 save_dockerfile 工具将生成的 Dockerfile 保存到 {result.local_path}
"""
        
        # 运行生成 Agent
        try:
            response = self.generator_agent.run(generation_prompt)
            logger.info(f"生成 Agent 响应完成")
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.error_message = f"生成 Agent 错误: {str(e)}"
            yield WorkflowMessage(
                content=f"❌ 生成 Agent 错误: {str(e)}",
                level="error"
            )
            return
        
        # 验证 Dockerfile 是否成功生成
        if expected_dockerfile_path.exists():
            result.dockerfile_path = str(expected_dockerfile_path)
            result.generation_notes = "Dockerfile 已生成"
            yield WorkflowMessage(
                content=f"✅ Dockerfile 已生成: {result.dockerfile_path}",
                level="success"
            )
        else:
            # 检查是否有其他名称的生成文件
            generated_files = list(Path(result.local_path).glob("Dockerfile*"))
            if generated_files:
                # 使用找到的第一个 Dockerfile
                result.dockerfile_path = str(generated_files[0])
                result.generation_notes = f"使用已有 Dockerfile: {result.dockerfile_path}"
                yield WorkflowMessage(
                    content=f"📄 使用已有 Dockerfile: {result.dockerfile_path}",
                    level="info"
                )
            else:
                result.status = DeploymentStatus.FAILED
                result.error_message = "Dockerfile 生成失败，文件未创建"
                yield WorkflowMessage(
                    content=f"❌ Dockerfile 生成失败: 文件未创建",
                    level="error"
                )
    
    def _verify_deployment(
        self,
        tool: Tool,
        result: DeploymentResult,
        max_retries: int
    ) -> Generator[WorkflowMessage, None, None]:
        """验证部署阶段"""
        result.status = DeploymentStatus.BUILDING
        
        # 生成镜像名称
        image_name = f"scitools/{tool.repo_name}".lower().replace(' ', '-')
        result.image_name = image_name
        
        yield WorkflowMessage(
            content=f"🔨 正在构建镜像: {image_name}...",
            level="info"
        )
        
        for attempt in range(max_retries):
            result.retry_count = attempt + 1
            
            # 构建验证提示
            verification_prompt = f"""
请验证以下工具的 Docker 部署：

**工具名称**: {tool.name}
**Dockerfile 路径**: {result.dockerfile_path}
**镜像名称**: {image_name}
**尝试次数**: {attempt + 1}/{max_retries}

请执行以下步骤：
1. 构建 Docker 镜像
2. 如果构建失败，分析错误并提供修复建议
3. 如果构建成功，尝试运行容器
4. 检查容器状态和日志
5. 验证服务是否正常

如果遇到错误，请详细分析原因。
"""
            
            # 运行验证 Agent
            try:
                response = self.verifier_agent.run(verification_prompt)
            except Exception as e:
                result.verification_notes = f"验证 Agent 错误: {str(e)}"
                if attempt < max_retries - 1:
                    yield WorkflowMessage(
                        content=f"⚠️ 第 {attempt + 1} 次尝试失败，正在重试...\n原因: {result.verification_notes}",
                        level="warning"
                    )
                continue
            
            # 检查结果（简化的检查逻辑）
            from tools.docker_tools import build_docker_image, run_docker_container
            
            build_result = build_docker_image(
                dockerfile_path=result.dockerfile_path,
                image_name=image_name
            )
            
            if build_result["success"]:
                result.status = DeploymentStatus.VERIFYING
                
                # 尝试运行容器
                container_name = f"test-{tool.repo_name}".lower().replace(' ', '-')
                run_result = run_docker_container(
                    image_name=f"{image_name}:latest",
                    container_name=container_name
                )
                
                if run_result["success"]:
                    result.container_id = run_result["container_id"]
                    result.status = DeploymentStatus.SUCCESS
                    result.verification_notes = "构建和运行验证成功"
                    
                    yield WorkflowMessage(
                        content=f"✅ 验证成功！镜像 {image_name} 已构建并运行",
                        level="success"
                    )
                    return
                else:
                    result.verification_notes = f"容器运行失败: {run_result.get('error', '')}"
            else:
                result.verification_notes = f"构建失败: {build_result.get('error', '')}"
            
            if attempt < max_retries - 1:
                yield WorkflowMessage(
                    content=f"⚠️ 第 {attempt + 1} 次尝试失败，正在重试...\n原因: {result.verification_notes}",
                    level="warning"
                )
        
        # 所有重试都失败
        result.status = DeploymentStatus.FAILED
        result.error_message = f"验证失败（尝试 {max_retries} 次）: {result.verification_notes}"
        
        yield WorkflowMessage(
            content=f"❌ 验证失败: {result.error_message}",
            level="error"
        )
    
    def _save_result(self, result: DeploymentResult):
        """保存部署结果到文件"""
        result_file = RESULTS_DIR / f"{result.tool_name.replace('/', '_')}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存: {result_file}")


class BatchDeploymentWorkflow:
    """
    批量部署工作流
    
    处理 list.md 中的多个工具
    """
    
    def __init__(self):
        self.single_workflow = RepoDeploymentWorkflow()
    
    def run(
        self,
        tools: list[Tool] = None,
        limit: int = None,
        skip_verification: bool = False,
        filter_domain: str = None
    ) -> Generator[WorkflowMessage, None, dict]:
        """
        批量执行部署工作流
        
        Args:
            tools: 工具列表（如果为空，从 list.md 读取）
            limit: 限制处理数量
            skip_verification: 是否跳过验证
            filter_domain: 按领域过滤
        
        Yields:
            WorkflowMessage: 工作流进度消息
            
        Returns:
            dict: 统计结果
        """
        # 读取工具列表
        if tools is None:
            tools = parse_list_md()
        
        # 过滤
        if filter_domain:
            tools = [t for t in tools if filter_domain.lower() in t.domain.lower()]
        
        # 限制数量
        if limit:
            tools = tools[:limit]
        
        total = len(tools)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        yield WorkflowMessage(
            content=f"📋 开始批量处理 {total} 个工具...",
            level="info"
        )
        
        for i, tool in enumerate(tools, 1):
            yield WorkflowMessage(
                content=f"\n{'='*50}\n[{i}/{total}] 处理: {tool.name}\n{'='*50}",
                level="info"
            )
            
            try:
                # 运行单个工具的工作流
                for msg in self.single_workflow.run(
                    tool=tool,
                    skip_verification=skip_verification
                ):
                    yield msg
                
                # 统计结果
                result_file = RESULTS_DIR / f"{tool.name.replace('/', '_')}.json"
                if result_file.exists():
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)
                    
                    if result_data["status"] == "success":
                        success_count += 1
                    elif result_data["status"] == "skipped":
                        skipped_count += 1
                    else:
                        failed_count += 1
                        
            except Exception as e:
                failed_count += 1
                yield WorkflowMessage(
                    content=f"❌ 处理 {tool.name} 时发生异常: {str(e)}",
                    level="error"
                )
        
        # 最终汇总
        yield WorkflowMessage(
            content=f"\n{'='*50}\n"
                    f"📊 批量处理完成\n"
                    f"总计: {total}\n"
                    f"成功: {success_count}\n"
                    f"失败: {failed_count}\n"
                    f"跳过: {skipped_count}\n"
                    f"{'='*50}",
            level="info"
        )
        
        return {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count
        }


# 便捷函数
def deploy_single_tool(
    tool_name: str = None,
    repo_url: str = None,
    skip_verification: bool = False
) -> dict:
    """
    部署单个工具的便捷函数
    
    Args:
        tool_name: 工具名称（从 list.md 查找）
        repo_url: 或直接提供仓库 URL
        skip_verification: 是否跳过验证
    
    Returns:
        dict: 部署结果
    """
    if tool_name:
        tools = parse_list_md()
        matching = [t for t in tools if tool_name.lower() in t.name.lower()]
        if not matching:
            raise ValueError(f"未找到工具: {tool_name}")
        tool = matching[0]
    elif repo_url:
        tool = Tool(
            topic="自定义",
            domain="自定义",
            name=repo_url.split('/')[-1].replace('.git', ''),
            version="latest",
            homepage=repo_url
        )
    else:
        raise ValueError("请提供 tool_name 或 repo_url")
    
    workflow = RepoDeploymentWorkflow()
    
    # 运行工作流并打印消息
    for msg in workflow.run(tool=tool, skip_verification=skip_verification):
        print(msg.content)
    
    # 读取结果
    result_file = RESULTS_DIR / f"{tool.name.replace('/', '_')}.json"
    if result_file.exists():
        with open(result_file, 'r') as f:
            return json.load(f)
    
    return None
