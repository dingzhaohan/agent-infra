"""
改进后的工作流使用示例

本示例展示如何使用改进后的系统部署科学计算工具
"""

from workflow import deploy_single_tool, deploy_batch_tools
from utils.list_parser import Tool


def example_1_deploy_nek5000():
    """
    示例 1：重新部署 Nek5000
    
    改进后的系统会：
    1. 使用 scientific_computing_fortran 模板
    2. 自动包含 gfortran, gcc, make, cmake, MPI, HDF5
    3. 进行功能性测试
    4. 如果发现问题，自动修复 Dockerfile
    """
    print("=" * 60)
    print("示例 1：部署 Nek5000（带自动修复）")
    print("=" * 60)
    
    result = deploy_single_tool(
        tool_name="Nek5000",
        skip_verification=False  # 进行完整验证
    )
    
    print("\n部署结果：")
    print(f"状态: {result.get('status', 'unknown')}")
    print(f"镜像: {result.get('image_name', 'N/A')}")
    print(f"Dockerfile: {result.get('dockerfile_path', 'N/A')}")
    print(f"重试次数: {result.get('retry_count', 0)}")


def example_2_deploy_custom_tool():
    """
    示例 2：部署自定义科学计算工具
    
    展示如何部署不在 list.md 中的工具
    """
    print("\n" + "=" * 60)
    print("示例 2：部署自定义工具")
    print("=" * 60)
    
    result = deploy_single_tool(
        repo_url="https://github.com/your-org/your-scientific-tool",
        skip_verification=False
    )
    
    print("\n部署结果：")
    print(f"状态: {result.get('status', 'unknown')}")


def example_3_batch_deploy_scientific_tools():
    """
    示例 3：批量部署科学计算工具
    
    使用并发模式快速部署多个工具
    """
    print("\n" + "=" * 60)
    print("示例 3：批量部署科学计算工具（并发）")
    print("=" * 60)
    
    stats = deploy_batch_tools(
        filter_domain="科学计算",  # 只处理科学计算领域的工具
        limit=5,                    # 限制处理 5 个工具
        concurrent=True,            # 使用并发模式
        max_workers=2,              # 最多 2 个并发任务
        skip_verification=False     # 进行完整验证
    )
    
    print("\n批量部署统计：")
    print(f"总计: {stats['total']}")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"跳过: {stats['skipped']}")


def example_4_direct_workflow_usage():
    """
    示例 4：直接使用 Workflow 类
    
    展示更细粒度的控制
    """
    print("\n" + "=" * 60)
    print("示例 4：直接使用 Workflow 类")
    print("=" * 60)
    
    from workflow import RepoDeploymentWorkflow
    
    # 创建工具对象
    tool = Tool(
        topic="科学计算",
        domain="计算流体力学",
        name="Nek5000",
        version="19.0",
        homepage="https://github.com/Nek5000/Nek5000",
        docs_url="https://nek5000.github.io/NekDoc/",
        external_data="无",
        repo_name="Nek5000"
    )
    
    # 创建工作流
    workflow = RepoDeploymentWorkflow()
    
    # 运行工作流并实时打印消息
    print("\n开始部署流程：")
    for msg in workflow.run(tool=tool, max_retries=3, skip_verification=False):
        print(f"[{msg.level.upper()}] {msg.content}")


def example_5_test_verification_only():
    """
    示例 5：只测试验证功能
    
    假设 Dockerfile 已存在，只运行验证
    """
    print("\n" + "=" * 60)
    print("示例 5：测试验证功能")
    print("=" * 60)
    
    from agents.verifier import create_verifier_agent
    
    # 创建验证 Agent
    verifier = create_verifier_agent()
    
    # 构建验证提示
    verification_prompt = """
请验证以下工具的 Docker 部署：

**工具名称**: Nek5000
**领域**: 计算流体力学
**Dockerfile 路径**: /root/agent-infra/repos/Nek5000/Dockerfile.generated
**镜像名称**: scitools/nek5000

请执行完整的验证流程：
1. 构建 Docker 镜像
2. 运行容器（使用 tail -f /dev/null 保持运行）
3. 检查容器状态
4. **执行功能性测试**：
   - which gfortran gcc g++ make cmake mpicc mpifort
   - 检查 /opt/Nek5000 是否存在
   - 测试简单的编译
5. **必须调用 report_verification_result 报告最终结果**
"""
    
    # 运行验证
    print("\n开始验证：")
    response = verifier.run(verification_prompt)
    
    # 读取验证结果
    import tempfile
    import os
    import json
    
    temp_file = os.path.join(tempfile.gettempdir(), "verifier_result.json")
    if os.path.exists(temp_file):
        with open(temp_file, 'r') as f:
            result = json.load(f)
        
        print("\n验证结果：")
        print(f"构建成功: {result.get('build_success', False)}")
        print(f"容器运行: {result.get('container_running', False)}")
        print(f"功能测试: {result.get('functional_test_success', False)}")
        print(f"总体状态: {result.get('overall_status', 'unknown')}")
        
        if result.get('missing_dependencies'):
            print(f"缺失依赖: {', '.join(result['missing_dependencies'])}")
        
        if result.get('fix_suggestions'):
            print("\n修复建议：")
            for suggestion in result['fix_suggestions']:
                print(f"  - {suggestion}")
        
        os.remove(temp_file)
    else:
        print("未找到验证结果文件")


def example_6_manual_fix():
    """
    示例 6：手动触发 Dockerfile 修复
    
    展示如何使用 generator_agent 修复 Dockerfile
    """
    print("\n" + "=" * 60)
    print("示例 6：手动修复 Dockerfile")
    print("=" * 60)
    
    from agents.dockerfile_generator import create_dockerfile_generator_agent
    
    # 创建生成器 Agent
    generator = create_dockerfile_generator_agent()
    
    # 构建修复提示
    fix_prompt = """
请修复 Dockerfile 以解决以下问题：

**工具名称**: Nek5000
**领域**: 计算流体力学
**Dockerfile 路径**: /root/agent-infra/repos/Nek5000/Dockerfile.generated

**验证发现的问题**:
镜像构建成功，但缺少关键编译工具，导致无法编译 Nek5000 示例

**缺失的依赖**: gfortran, gcc, make, cmake, h5pcc, h5fc

**修复建议**:
- 添加 build-essential 提供基本工具（gcc/g++/make）
- 单独安装 gfortran
- 安装 cmake 和 pkg-config
- 安装 libopenmpi-dev 和 openmpi-bin 提供 MPI 编译器包装器
- 安装 libhdf5-openmpi-dev 和 hdf5-tools 提供 h5pcc/h5fc
- 设置环境变量 NEK_SOURCE_ROOT=/opt/Nek5000

请使用 patch_dockerfile 工具获取当前 Dockerfile，然后生成修复后的版本。
"""
    
    # 运行修复
    print("\n开始修复：")
    response = generator.run(fix_prompt)
    
    print("\n修复完成！请重新验证。")


if __name__ == "__main__":
    import sys
    
    examples = {
        "1": example_1_deploy_nek5000,
        "2": example_2_deploy_custom_tool,
        "3": example_3_batch_deploy_scientific_tools,
        "4": example_4_direct_workflow_usage,
        "5": example_5_test_verification_only,
        "6": example_6_manual_fix,
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in examples:
        # 运行指定示例
        examples[sys.argv[1]]()
    else:
        # 显示菜单
        print("改进后的工作流使用示例")
        print("=" * 60)
        print("\n可用示例：")
        print("1. 重新部署 Nek5000（带自动修复）")
        print("2. 部署自定义工具")
        print("3. 批量部署科学计算工具（并发）")
        print("4. 直接使用 Workflow 类")
        print("5. 测试验证功能")
        print("6. 手动修复 Dockerfile")
        print("\n使用方法：")
        print("  python example_improved_workflow.py <示例编号>")
        print("\n示例：")
        print("  python example_improved_workflow.py 1")

