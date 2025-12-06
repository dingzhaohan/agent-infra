#!/usr/bin/env python3
"""
测试 list_parser 模块 - CSV 解析功能
"""
import sys
sys.path.insert(0, '.')

from utils.list_parser import parse_tools, get_tools_by_domain, get_tools_by_name, Tool

def main():
    print("=" * 60)
    print("测试 list_parser - CSV 解析功能")
    print("=" * 60)
    print()
    
    # 解析工具列表
    print("📊 解析工具列表...")
    tools = parse_tools()
    print(f"✅ 成功解析 {len(tools)} 个工具\n")
    
    # 显示前 5 个工具
    print("-" * 60)
    print("📦 前 5 个工具详情:")
    print("-" * 60)
    for i, tool in enumerate(tools[:5], 1):
        print(f"\n{i}. {tool.name}")
        print(f"   话题: {tool.topic}")
        print(f"   领域: {tool.domain}")
        print(f"   版本: {tool.version}")
        print(f"   主页: {tool.homepage}")
        if tool.docs_url:
            print(f"   文档: {tool.docs_url}")
        if tool.external_data:
            print(f"   外部依赖: {tool.external_data}")
    
    # 统计信息
    print("\n" + "=" * 60)
    print("📈 统计信息")
    print("=" * 60)
    print(f"总工具数: {len(tools)}")
    print(f"有文档链接: {sum(1 for t in tools if t.docs_url)} 个")
    print(f"有外部依赖: {sum(1 for t in tools if t.external_data)} 个")
    
    # 领域分布
    print(f"\nGitHub 项目: {sum(1 for t in tools if t.is_github)} 个")
    print(f"GitLab 项目: {sum(1 for t in tools if t.is_gitlab)} 个")
    
    # 测试查询功能
    print("\n" + "=" * 60)
    print("🔍 测试查询功能")
    print("=" * 60)
    
    # 按领域查询
    test_domains = ["生物", "材料", "流体力学", "量子"]
    for domain in test_domains:
        domain_tools = get_tools_by_domain(tools, domain)
        print(f"\n{domain}相关工具: {len(domain_tools)} 个")
        if domain_tools:
            for tool in domain_tools[:3]:
                print(f"  - {tool.name} ({tool.domain})")
            if len(domain_tools) > 3:
                print(f"  ... 还有 {len(domain_tools) - 3} 个")
    
    # 按名称查询
    print("\n" + "-" * 60)
    test_names = ["LAMMPS", "OpenFOAM", "AlphaFold"]
    for name in test_names:
        name_tools = get_tools_by_name(tools, name)
        if name_tools:
            tool = name_tools[0]
            print(f"\n搜索 '{name}':")
            print(f"  名称: {tool.name}")
            print(f"  领域: {tool.domain}")
            print(f"  主页: {tool.homepage}")
    
    # 验证数据完整性
    print("\n" + "=" * 60)
    print("✅ 数据完整性验证")
    print("=" * 60)
    
    # 检查必填字段
    invalid_tools = []
    for tool in tools:
        if not tool.name or not tool.homepage:
            invalid_tools.append(tool)
    
    if invalid_tools:
        print(f"⚠️  发现 {len(invalid_tools)} 个无效工具")
    else:
        print("✅ 所有工具的必填字段完整")
    
    # 检查 URL 格式
    invalid_urls = [t for t in tools if not t.homepage.startswith('http')]
    if invalid_urls:
        print(f"⚠️  发现 {len(invalid_urls)} 个无效 URL")
    else:
        print("✅ 所有主页 URL 格式正确")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()

