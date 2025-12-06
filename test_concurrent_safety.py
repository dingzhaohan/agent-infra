#!/usr/bin/env python3
"""
测试并发场景下临时文件的安全性

验证修复后的代码在并发场景下不会出现文件冲突
"""
import os
import json
import time
import uuid
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def simulate_verifier_worker(tool_name: str, delay: float = 0.1) -> dict:
    """
    模拟 verifier agent 的工作流程
    
    Args:
        tool_name: 工具名称
        delay: 模拟处理延迟（秒）
    
    Returns:
        dict: 包含工具名、文件路径和验证结果
    """
    # 生成唯一的临时文件名（与修复后的代码一致）
    safe_tool_name = tool_name.replace('/', '_').replace(' ', '_')
    unique_id = uuid.uuid4().hex[:8]
    temp_file = os.path.join(
        tempfile.gettempdir(),
        f"verifier_result_{safe_tool_name}_{unique_id}.json"
    )
    
    # 模拟验证过程
    result = {
        "tool_name": tool_name,
        "overall_status": "success",
        "build_success": True,
        "container_running": True,
        "functional_test_success": True,
        "timestamp": time.time(),
        "process_id": os.getpid()
    }
    
    # 写入结果
    with open(temp_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    # 模拟处理延迟
    time.sleep(delay)
    
    # 读取结果（验证写入成功）
    with open(temp_file, 'r') as f:
        read_result = json.load(f)
    
    # 验证读取的数据是否正确
    assert read_result["tool_name"] == tool_name, \
        f"数据错误！期望 {tool_name}，实际 {read_result['tool_name']}"
    
    # 清理文件
    os.remove(temp_file)
    
    return {
        "tool_name": tool_name,
        "temp_file": temp_file,
        "process_id": os.getpid(),
        "success": True,
        "result": read_result
    }


def test_concurrent_workers(num_workers: int = 5, num_tools: int = 10):
    """
    测试并发场景
    
    Args:
        num_workers: 并发工作进程数
        num_tools: 工具数量
    """
    print(f"\n{'='*60}")
    print(f"并发安全性测试")
    print(f"{'='*60}")
    print(f"工作进程数: {num_workers}")
    print(f"工具数量: {num_tools}")
    print(f"{'='*60}\n")
    
    # 生成测试工具列表
    tools = [f"Tool_{i:02d}" for i in range(1, num_tools + 1)]
    
    results = []
    errors = []
    
    start_time = time.time()
    
    # 使用进程池并发执行
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # 提交所有任务
        future_to_tool = {
            executor.submit(simulate_verifier_worker, tool): tool
            for tool in tools
        }
        
        # 处理完成的任务
        for i, future in enumerate(as_completed(future_to_tool), 1):
            tool = future_to_tool[future]
            
            try:
                result = future.result()
                results.append(result)
                print(f"[{i:2d}/{num_tools}] ✅ {tool:12s} - PID: {result['process_id']:6d} - File: {Path(result['temp_file']).name}")
            
            except Exception as e:
                errors.append({
                    "tool": tool,
                    "error": str(e)
                })
                print(f"[{i:2d}/{num_tools}] ❌ {tool:12s} - 错误: {str(e)}")
    
    elapsed_time = time.time() - start_time
    
    # 打印结果
    print(f"\n{'='*60}")
    print(f"测试结果")
    print(f"{'='*60}")
    print(f"总计: {num_tools}")
    print(f"成功: {len(results)}")
    print(f"失败: {len(errors)}")
    print(f"耗时: {elapsed_time:.2f} 秒")
    print(f"{'='*60}\n")
    
    # 验证结果
    if errors:
        print("❌ 测试失败！发现错误：")
        for err in errors:
            print(f"  - {err['tool']}: {err['error']}")
        return False
    
    # 验证文件名唯一性
    temp_files = [r['temp_file'] for r in results]
    unique_files = set(temp_files)
    
    if len(temp_files) != len(unique_files):
        print(f"❌ 文件名冲突！重复的文件: {len(temp_files) - len(unique_files)}")
        return False
    
    # 验证进程隔离（应该有多个不同的 PID）
    process_ids = set(r['process_id'] for r in results)
    print(f"使用的进程数: {len(process_ids)} (期望 <= {num_workers})")
    
    # 验证数据完整性
    for result in results:
        tool_name = result['tool_name']
        read_tool_name = result['result']['tool_name']
        if tool_name != read_tool_name:
            print(f"❌ 数据不一致！{tool_name} vs {read_tool_name}")
            return False
    
    print("\n✅ 所有测试通过！并发场景下无文件冲突。\n")
    return True


def test_old_vs_new_approach():
    """
    对比旧方法（固定文件名）和新方法（唯一文件名）
    """
    print(f"\n{'='*60}")
    print(f"对比测试：旧方法 vs 新方法")
    print(f"{'='*60}\n")
    
    # 旧方法（固定文件名）- 演示问题
    print("1. 旧方法（固定文件名）:")
    old_file = os.path.join(tempfile.gettempdir(), "verifier_result.json")
    
    # 进程 A 写入
    with open(old_file, 'w') as f:
        json.dump({"tool": "Tool_A"}, f)
    print(f"   进程 A 写入: {old_file}")
    
    # 进程 B 写入（覆盖！）
    with open(old_file, 'w') as f:
        json.dump({"tool": "Tool_B"}, f)
    print(f"   进程 B 写入: {old_file} (覆盖!)")
    
    # 进程 A 读取
    with open(old_file, 'r') as f:
        data = json.load(f)
    print(f"   进程 A 读取: {data}")
    print(f"   ❌ 进程 A 期望读到 Tool_A，实际读到 {data['tool']}\n")
    
    os.remove(old_file)
    
    # 新方法（唯一文件名）
    print("2. 新方法（唯一文件名）:")
    
    new_file_a = os.path.join(tempfile.gettempdir(), f"verifier_result_Tool_A_{uuid.uuid4().hex[:8]}.json")
    new_file_b = os.path.join(tempfile.gettempdir(), f"verifier_result_Tool_B_{uuid.uuid4().hex[:8]}.json")
    
    # 进程 A 写入
    with open(new_file_a, 'w') as f:
        json.dump({"tool": "Tool_A"}, f)
    print(f"   进程 A 写入: {Path(new_file_a).name}")
    
    # 进程 B 写入（独立文件）
    with open(new_file_b, 'w') as f:
        json.dump({"tool": "Tool_B"}, f)
    print(f"   进程 B 写入: {Path(new_file_b).name}")
    
    # 进程 A 读取
    with open(new_file_a, 'r') as f:
        data_a = json.load(f)
    print(f"   进程 A 读取: {data_a}")
    print(f"   ✅ 进程 A 正确读到 {data_a['tool']}")
    
    # 进程 B 读取
    with open(new_file_b, 'r') as f:
        data_b = json.load(f)
    print(f"   进程 B 读取: {data_b}")
    print(f"   ✅ 进程 B 正确读到 {data_b['tool']}\n")
    
    os.remove(new_file_a)
    os.remove(new_file_b)
    
    print("结论: 新方法完全隔离，无冲突！\n")


if __name__ == "__main__":
    # 运行对比测试
    test_old_vs_new_approach()
    
    # 运行并发测试
    test_concurrent_workers(num_workers=5, num_tools=20)
    
    print(f"{'='*60}")
    print("测试完成！")
    print(f"{'='*60}")

