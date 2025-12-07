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
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Queue, Process
import queue

from config import REPOS_DIR, RESULTS_DIR, MAX_RETRIES, MAX_CONCURRENT_TOOLS, DOCKER_REGISTRY, DOCKER_NAMESPACE, DOCKER_TAG
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
    # 保存原始分析上下文，供修复时使用
    dep_info: dict = None
    readme_info: dict = None
    analyzer_output: str = None  # 分析 Agent 的完整输出
    
    def __post_init__(self):
        """初始化可变默认值"""
        if self.dep_info is None:
            self.dep_info = {}
        if self.readme_info is None:
            self.readme_info = {}
        if self.analyzer_output is None:
            self.analyzer_output = ""
    
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
            
            # 阶段 2: 始终生成新的 Dockerfile
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
3. 读取 README 了解安装方式
4. 确定依赖管理方式和主要技术栈
5. 给出部署策略建议

**重要**：请详细输出你的分析结果，包括：
- 技术栈和主要语言
- 依赖管理方式（requirements.txt, setup.py, CMakeLists.txt 等）
- 推荐的基础镜像
- 需要安装的系统依赖
- 编译步骤（如需要）
- 特殊注意事项

**注意**：即使仓库中有现成的 Dockerfile，我们也会生成新的优化版本。
这些分析将被传递给下一个 Agent 用于生成 Dockerfile。
"""
        
        # 运行分析 Agent，捕获其输出
        analyzer_response = None
        try:
            response = self.analyzer_agent.run(analysis_prompt)
            # 保存 Agent 的响应用于后续步骤
            if hasattr(response, 'content'):
                analyzer_response = response.content
            else:
                analyzer_response = str(response)
            logger.info(f"分析 Agent 响应完成，输出长度: {len(analyzer_response)}")
        except Exception as e:
            error_msg = str(e)
            
            # 检查是否是认证/私有仓库错误
            auth_keywords = ["需要认证", "Authentication", "Access denied", "private repository", "已跳过"]
            if any(keyword in error_msg for keyword in auth_keywords):
                result.status = DeploymentStatus.SKIPPED
                result.error_message = "需要认证访问（私有仓库），已跳过"
                yield WorkflowMessage(
                    content=f"⏭️ 跳过需要认证的仓库: {tool.name}",
                    level="warning"
                )
                return
            
            result.status = DeploymentStatus.FAILED
            result.error_message = f"分析 Agent 错误: {error_msg}"
            yield WorkflowMessage(
                content=f"❌ 分析 Agent 错误: {error_msg}",
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
        
        # 检查是否找到 Dockerfile（仅作为参考信息）
        from tools.file_tools import find_dockerfile, find_dependency_files, find_readme
        dockerfile_result = find_dockerfile(result.local_path)
        
        # 同时获取依赖和 README 信息（供后续使用）
        dep_info = find_dependency_files(result.local_path)
        readme_info = find_readme(result.local_path)
        
        # 保存分析上下文
        result.dep_info = dep_info
        result.readme_info = readme_info
        result.analyzer_output = analyzer_response  # 保存分析 Agent 的完整输出
        
        # 始终标记为需要生成 Dockerfile（不使用原仓库的）
        result.has_existing_dockerfile = False
        result.dockerfile_path = ""
        
        # 记录是否找到了原有 Dockerfile（仅作参考）
        if dockerfile_result["found"]:
            result.analysis_notes = f"发现原有 Dockerfile: {dockerfile_result['primary_dockerfile']}（将生成新的）"
        else:
            result.analysis_notes = "未找到 Dockerfile，将生成新的"
        
        yield WorkflowMessage(
            content=f"📋 分析完成\n"
                    f"本地路径: {result.local_path}\n"
                    f"主要语言: {dep_info.get('primary_language', '未知')}\n"
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
        
        # 使用已保存的分析上下文
        dep_info = result.dep_info or {}
        readme_info = result.readme_info or {}
        analyzer_output = result.analyzer_output or "无分析输出"
        
        # 预期的 Dockerfile 路径
        expected_dockerfile_path = Path(result.local_path) / "Dockerfile.generated"
        
        # 构建生成提示 - 包含分析 Agent 的输出
        generation_prompt = f"""
请为以下项目生成 Dockerfile。

## 项目基本信息
**工具名称**: {tool.name}
**本地路径**: {result.local_path}
**领域**: {tool.domain}

## 分析 Agent 的详细分析（重要参考）
{analyzer_output}

## 项目依赖信息
**主要语言**: {dep_info.get('primary_language', '未知')}
**依赖文件**: {json.dumps(dep_info.get('files', []), ensure_ascii=False)}

## README 摘要
{readme_info.get('content', '无')[:2000]}

## 任务要求
根据上述**分析 Agent 的建议**和项目信息：
1. 参考 Dockerfile 模版选择合适的基础镜像
2. 根据项目特点自定义配置
3. 添加分析中提到的系统依赖
4. 如果需要编译，参考分析中的编译步骤
5. 生成完整的 Dockerfile 并保存（文件名：Dockerfile.generated）

如果是科学计算工具，请特别注意：
- 可能需要 BLAS/LAPACK 库
- 可能需要 Fortran 编译器（gfortran）
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
        """验证部署阶段（带自动修复）"""
        result.status = DeploymentStatus.BUILDING
        
        # 生成镜像名称
        # 格式: registry.dp.tech/davinci/tool-name:tag
        safe_name = tool.repo_name.lower().replace(' ', '-').replace('/', '-')
        image_name = f"{DOCKER_REGISTRY}/{DOCKER_NAMESPACE}/{safe_name}"
        image_tag = DOCKER_TAG
        image_full = f"{image_name}:{image_tag}"
        
        result.image_name = image_full
        
        yield WorkflowMessage(
            content=f"🔨 正在构建镜像: {image_full}...",
            level="info"
        )
        
        for attempt in range(max_retries):
            result.retry_count = attempt + 1
            
            # 生成唯一的结果文件路径（并发安全）
            import tempfile
            import os
            import uuid
            
            # 使用工具名和 UUID 生成唯一文件名
            safe_tool_name = tool.repo_name.replace('/', '_').replace(' ', '_')
            unique_id = uuid.uuid4().hex[:8]
            temp_file = os.path.join(
                tempfile.gettempdir(),
                f"verifier_result_{safe_tool_name}_{unique_id}.json"
            )
            
            # 设置环境变量供 verifier agent 使用
            os.environ['VERIFIER_RESULT_FILE'] = temp_file
            
            # 构建验证提示
            verification_prompt = f"""
请验证以下工具的 Docker 部署：

**工具名称**: {tool.name}
**领域**: {tool.domain}
**Dockerfile 路径**: {result.dockerfile_path}
**镜像名称**: {image_full}
**尝试次数**: {attempt + 1}/{max_retries}

请执行完整的验证流程：
1. 构建 Docker 镜像
2. 运行容器（使用 tail -f /dev/null 保持运行）
3. 检查容器状态
4. **重要：执行功能性测试**
   - 对于科学计算工具，检查编译器和工具是否可用
   - 测试命令：which gfortran gcc g++ make cmake mpicc mpifort
   - 如果有特定工具路径（如 /opt/工具名），检查文件是否存在
   - 尝试简单的功能测试
5. **必须调用 report_verification_result 报告最终结果**

**特别注意**：
- 如果镜像构建成功但缺少关键工具（如 gfortran、gcc、make），必须报告为失败
- 必须明确列出所有缺失的依赖
- 提供具体的修复建议

"""
            
            # 运行验证 Agent
            try:
                response = self.verifier_agent.run(verification_prompt)
                logger.info(f"验证 Agent 响应完成")
            except Exception as e:
                result.verification_notes = f"验证 Agent 错误: {str(e)}"
                # 清理环境变量
                os.environ.pop('VERIFIER_RESULT_FILE', None)
                if attempt < max_retries - 1:
                    yield WorkflowMessage(
                        content=f"⚠️ 第 {attempt + 1} 次尝试失败，正在重试...\n原因: {result.verification_notes}",
                        level="warning"
                    )
                continue
            
            # 读取验证结果
            verification_result = None
            
            if os.path.exists(temp_file):
                try:
                    with open(temp_file, 'r') as f:
                        verification_result = json.load(f)
                    os.remove(temp_file)  # 清理临时文件
                except Exception as e:
                    logger.warning(f"无法读取验证结果: {e}")
            
            # 清理环境变量
            os.environ.pop('VERIFIER_RESULT_FILE', None)
            
            # 根据验证结果决定下一步
            if verification_result:
                yield WorkflowMessage(
                    content=f"验证结果: 已经找到验证结果文件: {temp_file}",
                    level="info"
                )
                overall_status = verification_result.get("overall_status", "needs_fix")
                # 提前提取这些变量，确保在所有分支都可用
                error_summary = verification_result.get("error_summary", "")
                missing_deps = verification_result.get("missing_dependencies", [])
                fix_suggestions = verification_result.get("fix_suggestions", [])
                
                if overall_status == "success":
                    result.status = DeploymentStatus.SUCCESS
                    result.verification_notes = "构建和功能验证成功"
                    
                    yield WorkflowMessage(
                        content=f"✅ 验证成功！镜像 {image_name} 已构建并通过功能测试",
                        level="success"
                    )
                    return
                
                elif (overall_status == "needs_fix" or overall_status == "failed") and attempt < max_retries - 1:
                    # 需要修复 Dockerfile
                    
                    yield WorkflowMessage(
                        content=f"⚠️ 第 {attempt + 1} 次验证发现问题，尝试重写 Dockerfile...\n"
                                f"问题: {error_summary}\n"
                                f"缺失依赖: {', '.join(missing_deps) if missing_deps else '无'}",
                        level="warning"
                    )
                    
                    # 读取当前的 Dockerfile（用于参考）
                    current_dockerfile = ""
                    try:
                        with open(result.dockerfile_path, 'r') as f:
                            current_dockerfile = f.read()
                    except Exception as e:
                        logger.warning(f"无法读取当前 Dockerfile: {e}")
                    
                    # 构建包含完整上下文的修复提示
                    fix_prompt = f"""
请重写 Dockerfile 以解决验证中发现的问题。

## 项目基本信息
**工具名称**: {tool.name}
**领域**: {tool.domain}
**本地路径**: {result.local_path}
**主要语言**: {getattr(result, 'dep_info', {}).get('primary_language', '未知')}
**依赖文件**: {json.dumps(getattr(result, 'dep_info', {}).get('files', []), ensure_ascii=False)}

## 分析 Agent 的原始分析（重要参考）
{getattr(result, 'analyzer_output', '无')[:3000]}

## README 摘要
{getattr(result, 'readme_info', {}).get('content', '无')[:2000]}

## 当前 Dockerfile（第 {attempt + 1} 次尝试）
```dockerfile
{current_dockerfile}
```

## 验证失败的问题
**错误摘要**: {error_summary}

**缺失的依赖**: 
{chr(10).join(f'- {dep}' for dep in missing_deps) if missing_deps else '无'}

**修复建议**:
{chr(10).join(f'- {s}' for s in fix_suggestions) if fix_suggestions else '无'}

## 任务要求
请根据上述信息**重写完整的 Dockerfile**，而不是修补。重点：

1. **从头开始设计** - 根据项目需求选择最合适的基础镜像和模版
2. **确保包含所有依赖** - 特别注意验证中发现缺失的依赖
3. **科学计算工具必备组件**：
   - 完整编译工具链：gcc, g++, gfortran, make, cmake, build-essential
   - MPI 支持（如需要）：openmpi-bin, libopenmpi-dev, mpicc, mpifort
   - 数学库：libblas-dev, liblapack-dev, libfftw3-dev
   - HDF5 支持：libhdf5-dev, hdf5-tools
   - Python 科学计算：numpy, scipy, matplotlib, ase
4. **遵循最佳实践**：
   - 层优化（合并命令）
   - 缓存清理（apt: rm -rf /var/lib/apt/lists/*, pip: --no-cache-dir）
   - 环境变量双配置（ENV + bashrc）
   - 临时文件清理
5. **不要设置限制性的 ENTRYPOINT** - 使用 WORKDIR /root 即可

请使用 save_dockerfile 工具将重写的 Dockerfile 保存到 {result.local_path}，文件名：Dockerfile.generated
"""
                    
                    try:
                        self.generator_agent.run(fix_prompt)
                        
                        yield WorkflowMessage(
                            content=f"🔧 Dockerfile 已重写（尝试 {attempt + 2}/{max_retries}），准备重新验证...",
                            level="info"
                        )
                        
                        # 继续下一次循环重新验证
                        continue
                        
                    except Exception as e:
                        yield WorkflowMessage(
                            content=f"❌ Dockerfile 重写失败: {str(e)}",
                            level="error"
                        )
                
                else:
                    # 验证失败且无法修复或已达最大重试次数
                    result.verification_notes = error_summary if error_summary else "验证失败"
                    
                    if attempt < max_retries - 1:
                        yield WorkflowMessage(
                            content=f"⚠️ 第 {attempt + 1} 次尝试失败，正在重试...\n原因: {result.verification_notes}",
                            level="warning"
                        )
            else:
                # 没有收到结构化的验证结果，使用简化检查
                yield WorkflowMessage(
                    content=f"验证结果: 未找到验证结果文件: {temp_file}, 使用简化检查",
                    level="info"
                )
                from tools.docker_tools import build_docker_image, run_docker_container
                
                build_result = build_docker_image(
                    dockerfile_path=result.dockerfile_path,
                    image_name=image_name,
                    tag=image_tag
                )
                
                if build_result["success"]:
                    result.status = DeploymentStatus.VERIFYING
                    
                    # 尝试运行容器
                    container_name = f"test-{tool.repo_name}".lower().replace(' ', '-')
                    run_result = run_docker_container(
                        image_name=image_full,
                        container_name=container_name
                    )
                    
                    if run_result["success"]:
                        result.container_id = run_result["container_id"]
                        result.status = DeploymentStatus.SUCCESS
                        result.verification_notes = "构建和运行验证成功（未进行功能测试）"
                        
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


def _run_single_tool_worker(tool: Tool, skip_verification: bool = False) -> dict:
    """
    多进程工作器函数 - 在子进程中运行单个工具的部署
    
    Args:
        tool: 要部署的工具
        skip_verification: 是否跳过验证
    
    Returns:
        dict: 包含工具名称、状态和消息的结果字典
    """
    workflow = RepoDeploymentWorkflow()
    messages = []
    
    try:
        # 收集所有消息
        for msg in workflow.run(tool=tool, skip_verification=skip_verification):
            messages.append({
                "content": msg.content,
                "level": msg.level,
                "tool_name": tool.name
            })
        
        # 读取最终结果
        result_file = RESULTS_DIR / f"{tool.name.replace('/', '_')}.json"
        if result_file.exists():
            with open(result_file, 'r') as f:
                result_data = json.load(f)
            status = result_data.get("status", "unknown")
        else:
            status = "failed"
        
        return {
            "tool_name": tool.name,
            "status": status,
            "messages": messages,
            "success": True
        }
    
    except Exception as e:
        messages.append({
            "content": f"❌ 处理 {tool.name} 时发生异常: {str(e)}",
            "level": "error",
            "tool_name": tool.name
        })
        
        return {
            "tool_name": tool.name,
            "status": "failed",
            "messages": messages,
            "success": False,
            "error": str(e)
        }


class BatchDeploymentWorkflow:
    """
    批量部署工作流
    
    处理 list.md 中的多个工具，支持串行和并发两种模式
    """
    
    def __init__(self, max_workers: int = MAX_CONCURRENT_TOOLS):
        """
        初始化批量部署工作流
        
        Args:
            max_workers: 最大并发工作进程数
        """
        self.single_workflow = RepoDeploymentWorkflow()
        self.max_workers = max_workers
    
    def run(
        self,
        tools: list[Tool] = None,
        limit: int = None,
        skip_verification: bool = False,
        filter_domain: str = None,
        concurrent: bool = False
    ) -> Generator[WorkflowMessage, None, dict]:
        """
        批量执行部署工作流（支持串行和并发两种模式）
        
        Args:
            tools: 工具列表（如果为空，从 list.md 读取）
            limit: 限制处理数量
            skip_verification: 是否跳过验证
            filter_domain: 按领域过滤
            concurrent: 是否使用并发模式（默认 False 串行）
        
        Yields:
            WorkflowMessage: 工作流进度消息
            
        Returns:
            dict: 统计结果
        """
        if concurrent:
            # 使用并发模式
            yield from self.run_concurrent(
                tools=tools,
                limit=limit,
                skip_verification=skip_verification,
                filter_domain=filter_domain
            )
        else:
            # 使用串行模式
            yield from self._run_sequential(
                tools=tools,
                limit=limit,
                skip_verification=skip_verification,
                filter_domain=filter_domain
            )
    
    def _run_sequential(
        self,
        tools: list[Tool] = None,
        limit: int = None,
        skip_verification: bool = False,
        filter_domain: str = None
    ) -> Generator[WorkflowMessage, None, dict]:
        """
        串行执行部署工作流（原有逻辑）
        
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
    
    def run_concurrent(
        self,
        tools: list[Tool] = None,
        limit: int = None,
        skip_verification: bool = False,
        filter_domain: str = None
    ) -> Generator[WorkflowMessage, None, dict]:
        """
        并发执行部署工作流（使用多进程）
        
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
        completed_count = 0
        
        yield WorkflowMessage(
            content=f"📋 开始并发处理 {total} 个工具（最大并发数: {self.max_workers}）...",
            level="info"
        )
        
        # 使用 ProcessPoolExecutor 并发执行
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_tool = {
                executor.submit(_run_single_tool_worker, tool, skip_verification): tool
                for tool in tools
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_tool):
                tool = future_to_tool[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    
                    # 输出该工具的所有消息
                    yield WorkflowMessage(
                        content=f"\n{'='*50}\n[{completed_count}/{total}] {tool.name} 完成\n{'='*50}",
                        level="info"
                    )
                    
                    for msg in result.get("messages", []):
                        yield WorkflowMessage(
                            content=msg["content"],
                            level=msg["level"]
                        )
                    
                    # 统计结果
                    status = result.get("status", "failed")
                    if status == "success":
                        success_count += 1
                    elif status == "skipped":
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
                    f"📊 并发处理完成\n"
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
def deploy_batch_tools(
    limit: int = None,
    skip_verification: bool = False,
    filter_domain: str = None,
    concurrent: bool = False,
    max_workers: int = MAX_CONCURRENT_TOOLS
) -> dict:
    """
    批量部署工具的便捷函数
    
    Args:
        limit: 限制处理数量
        skip_verification: 是否跳过验证
        filter_domain: 按领域过滤
        concurrent: 是否使用并发模式
        max_workers: 最大并发工作进程数
    
    Returns:
        dict: 统计结果
    """
    workflow = BatchDeploymentWorkflow(max_workers=max_workers)
    
    # 运行工作流并打印消息
    for msg in workflow.run(
        limit=limit,
        skip_verification=skip_verification,
        filter_domain=filter_domain,
        concurrent=concurrent
    ):
        print(msg.content)
    
    return workflow


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
