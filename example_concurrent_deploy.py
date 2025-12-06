#!/usr/bin/env python3
"""
示例：使用并发模式批量部署工具

这个脚本展示如何使用新的并发功能来加速批量部署过程
"""
import sys
from workflow import BatchDeploymentWorkflow, deploy_batch_tools
from config import MAX_CONCURRENT_TOOLS


def example_concurrent_deployment():
    """并发部署示例"""
    print("=" * 60)
    print("示例 1: 并发部署前 5 个工具")
    print("=" * 60)
    
    # 方式 1: 使用便捷函数
    result = deploy_batch_tools(
        limit=5,
        skip_verification=False,  # 实际构建和验证
        concurrent=True,          # 启用并发模式
        max_workers=3             # 最多 3 个并发进程
    )
    
    print(f"\n部署结果: {result}")


def example_sequential_deployment():
    """串行部署示例（原有方式）"""
    print("=" * 60)
    print("示例 2: 串行部署前 3 个工具")
    print("=" * 60)
    
    workflow = BatchDeploymentWorkflow()
    
    for msg in workflow.run(
        limit=3,
        skip_verification=True,   # 跳过验证加快速度
        concurrent=False          # 串行模式
    ):
        print(msg.content)


def example_domain_filter_concurrent():
    """按领域过滤并并发部署"""
    print("=" * 60)
    print("示例 3: 并发部署 ML 领域的工具")
    print("=" * 60)
    
    workflow = BatchDeploymentWorkflow(max_workers=2)
    
    for msg in workflow.run(
        filter_domain="machine learning",
        limit=10,
        skip_verification=True,
        concurrent=True
    ):
        print(msg.content)


def compare_performance():
    """性能对比：串行 vs 并发"""
    import time
    from utils.list_parser import parse_list_md
    
    tools = parse_list_md()[:5]  # 使用前 5 个工具
    
    print("=" * 60)
    print("性能对比测试")
    print("=" * 60)
    
    # 串行模式
    print("\n[串行模式]")
    workflow_seq = BatchDeploymentWorkflow()
    start_time = time.time()
    
    for msg in workflow_seq.run(
        tools=tools,
        skip_verification=True,
        concurrent=False
    ):
        pass  # 只计时，不打印
    
    seq_time = time.time() - start_time
    print(f"串行耗时: {seq_time:.2f} 秒")
    
    # 并发模式
    print("\n[并发模式]")
    workflow_con = BatchDeploymentWorkflow(max_workers=3)
    start_time = time.time()
    
    for msg in workflow_con.run(
        tools=tools,
        skip_verification=True,
        concurrent=True
    ):
        pass  # 只计时，不打印
    
    con_time = time.time() - start_time
    print(f"并发耗时: {con_time:.2f} 秒")
    print(f"加速比: {seq_time/con_time:.2f}x")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        example = sys.argv[1]
        
        if example == "concurrent":
            example_concurrent_deployment()
        elif example == "sequential":
            example_sequential_deployment()
        elif example == "filter":
            example_domain_filter_concurrent()
        elif example == "compare":
            compare_performance()
        else:
            print(f"未知示例: {example}")
            print("可用选项: concurrent, sequential, filter, compare")
    else:
        print("使用方法:")xainzai
        print("  python example_concurrent_deploy.py concurrent  # 并发部署")
        print("  python example_concurrent_deploy.py sequential  # 串行部署")
        print("  python example_concurrent_deploy.py filter      # 按领域过滤")
        print("  python example_concurrent_deploy.py compare     # 性能对比")
        print()
        print("提示: 可以在 .env 中设置 MAX_CONCURRENT_TOOLS 来控制并发数")

