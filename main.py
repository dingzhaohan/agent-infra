#!/usr/bin/env python3
"""
开源科学工具自动化部署系统
基于 Agno 框架的工作流编排

使用方法:
    # 部署单个工具（按名称）
    python main.py --tool "scikit-fem"
    
    # 部署单个工具（按 URL）
    python main.py --url "https://github.com/kinnala/scikit-fem"
    
    # 批量部署（前5个工具）
    python main.py --batch --limit 5
    
    # 批量部署特定领域
    python main.py --batch --domain "生物信息"
    
    # 仅分析不验证
    python main.py --tool "scikit-fem" --skip-verify
    
    # 交互模式
    python main.py --interactive
"""
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import REPOS_DIR, RESULTS_DIR, OPENAI_API_KEY
from utils.list_parser import parse_list_md, get_tools_by_domain, get_tools_by_name
from workflow import RepoDeploymentWorkflow, BatchDeploymentWorkflow, deploy_single_tool

console = Console()


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║        🔬 开源科学工具自动化部署系统 🔬                        ║
║        基于 Agno 框架的智能工作流编排                          ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


def check_prerequisites():
    """检查前置条件"""
    issues = []
    
    # 检查 OpenAI API Key
    if not OPENAI_API_KEY:
        issues.append("未设置 OPENAI_API_KEY 环境变量")
    
    # 检查 Docker
    import subprocess
    try:
        result = subprocess.run(["docker", "info"], capture_output=True)
        if result.returncode != 0:
            issues.append("Docker 未运行或无法访问")
    except FileNotFoundError:
        issues.append("Docker 未安装")
    
    # 检查 Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True)
        if result.returncode != 0:
            issues.append("Git 未安装")
    except FileNotFoundError:
        issues.append("Git 未安装")
    
    return issues


def list_tools(domain: str = None, limit: int = 20):
    """列出可用工具"""
    tools = parse_list_md()
    
    if domain:
        tools = get_tools_by_domain(tools, domain)
    
    table = Table(title="可用工具列表", show_header=True)
    table.add_column("序号", style="cyan", width=6)
    table.add_column("工具名", style="green", width=25)
    table.add_column("领域", style="yellow", width=20)
    table.add_column("版本", style="blue", width=10)
    table.add_column("仓库", style="dim", width=40)
    
    for i, tool in enumerate(tools[:limit], 1):
        table.add_row(
            str(i),
            tool.name,
            tool.domain[:20] + "..." if len(tool.domain) > 20 else tool.domain,
            tool.version,
            tool.homepage[:40] + "..." if len(tool.homepage) > 40 else tool.homepage
        )
    
    console.print(table)
    
    if len(tools) > limit:
        console.print(f"\n[dim]显示前 {limit} 个，共 {len(tools)} 个工具[/dim]")


def run_single_deployment(tool_name: str = None, repo_url: str = None, skip_verify: bool = False):
    """运行单个工具部署"""
    console.print(Panel(f"🚀 开始部署: {tool_name or repo_url}", style="bold green"))
    
    try:
        result = deploy_single_tool(
            tool_name=tool_name,
            repo_url=repo_url,
            skip_verification=skip_verify
        )
        
        if result:
            if result.get("status") == "success":
                console.print("\n[bold green]✅ 部署成功![/bold green]")
            elif result.get("status") == "skipped":
                console.print("\n[bold yellow]⏭️ 分析完成（跳过验证）[/bold yellow]")
            else:
                console.print(f"\n[bold red]❌ 部署失败: {result.get('error_message', '未知错误')}[/bold red]")
        
        return result
        
    except Exception as e:
        console.print(f"\n[bold red]❌ 部署异常: {str(e)}[/bold red]")
        return None


def run_batch_deployment(limit: int = None, domain: str = None, skip_verify: bool = False):
    """运行批量部署"""
    tools = parse_list_md()
    
    if domain:
        tools = get_tools_by_domain(tools, domain)
        console.print(f"[yellow]筛选领域: {domain}, 共 {len(tools)} 个工具[/yellow]")
    
    if limit:
        tools = tools[:limit]
        console.print(f"[yellow]限制数量: {limit}[/yellow]")
    
    console.print(Panel(f"🚀 开始批量部署 {len(tools)} 个工具", style="bold green"))
    
    workflow = BatchDeploymentWorkflow()
    
    for response in workflow.run(
        tools=tools,
        skip_verification=skip_verify
    ):
        console.print(response.content)


def interactive_mode():
    """交互式模式"""
    print_banner()
    
    # 检查前置条件
    issues = check_prerequisites()
    if issues:
        console.print("[bold red]⚠️ 前置条件检查失败:[/bold red]")
        for issue in issues:
            console.print(f"  - {issue}")
        if not Confirm.ask("是否继续？"):
            return
    
    while True:
        console.print("\n[bold cyan]请选择操作:[/bold cyan]")
        console.print("  1. 列出可用工具")
        console.print("  2. 部署单个工具（按名称）")
        console.print("  3. 部署单个工具（按 URL）")
        console.print("  4. 批量部署")
        console.print("  5. 查看部署结果")
        console.print("  6. 退出")
        
        choice = Prompt.ask("请输入选项", choices=["1", "2", "3", "4", "5", "6"])
        
        if choice == "1":
            domain = Prompt.ask("按领域过滤（留空显示全部）", default="")
            limit = int(Prompt.ask("显示数量", default="20"))
            list_tools(domain=domain if domain else None, limit=limit)
            
        elif choice == "2":
            tool_name = Prompt.ask("请输入工具名称")
            skip_verify = Confirm.ask("是否跳过验证？", default=False)
            run_single_deployment(tool_name=tool_name, skip_verify=skip_verify)
            
        elif choice == "3":
            repo_url = Prompt.ask("请输入仓库 URL")
            skip_verify = Confirm.ask("是否跳过验证？", default=False)
            run_single_deployment(repo_url=repo_url, skip_verify=skip_verify)
            
        elif choice == "4":
            domain = Prompt.ask("按领域过滤（留空处理全部）", default="")
            limit = int(Prompt.ask("处理数量限制", default="5"))
            skip_verify = Confirm.ask("是否跳过验证？", default=True)
            run_batch_deployment(
                limit=limit,
                domain=domain if domain else None,
                skip_verify=skip_verify
            )
            
        elif choice == "5":
            # 查看结果
            results_files = list(RESULTS_DIR.glob("*.json"))
            if not results_files:
                console.print("[yellow]暂无部署结果[/yellow]")
            else:
                table = Table(title="部署结果", show_header=True)
                table.add_column("工具", style="green")
                table.add_column("状态", style="yellow")
                table.add_column("镜像", style="blue")
                
                import json
                for f in results_files[:20]:
                    with open(f, 'r') as file:
                        data = json.load(file)
                    
                    status_style = {
                        "success": "[green]✅ 成功[/green]",
                        "failed": "[red]❌ 失败[/red]",
                        "skipped": "[yellow]⏭️ 跳过[/yellow]",
                    }.get(data.get("status", ""), data.get("status", ""))
                    
                    table.add_row(
                        data.get("tool_name", ""),
                        status_style,
                        data.get("image_name", "")[:30]
                    )
                
                console.print(table)
            
        elif choice == "6":
            console.print("[bold blue]👋 再见！[/bold blue]")
            break


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="开源科学工具自动化部署系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py --tool "scikit-fem"
    python main.py --url "https://github.com/kinnala/scikit-fem"
    python main.py --batch --limit 5
    python main.py --batch --domain "生物信息"
    python main.py --interactive
    python main.py --list
        """
    )
    
    # 操作模式
    parser.add_argument("--tool", "-t", help="按名称部署单个工具")
    parser.add_argument("--url", "-u", help="按 URL 部署单个工具")
    parser.add_argument("--batch", "-b", action="store_true", help="批量部署模式")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    parser.add_argument("--list", "-l", action="store_true", help="列出可用工具")
    
    # 选项
    parser.add_argument("--limit", type=int, help="限制处理数量")
    parser.add_argument("--domain", "-d", help="按领域过滤")
    parser.add_argument("--skip-verify", action="store_true", help="跳过验证步骤")
    
    args = parser.parse_args()
    
    # 如果没有参数，进入交互模式
    if len(sys.argv) == 1:
        interactive_mode()
        return
    
    # 列出工具
    if args.list:
        print_banner()
        list_tools(domain=args.domain, limit=args.limit or 50)
        return
    
    # 交互模式
    if args.interactive:
        interactive_mode()
        return
    
    # 检查前置条件
    issues = check_prerequisites()
    if issues:
        console.print("[bold red]⚠️ 前置条件检查失败:[/bold red]")
        for issue in issues:
            console.print(f"  - {issue}")
        sys.exit(1)
    
    print_banner()
    
    # 单个工具部署
    if args.tool or args.url:
        run_single_deployment(
            tool_name=args.tool,
            repo_url=args.url,
            skip_verify=args.skip_verify
        )
        return
    
    # 批量部署
    if args.batch:
        run_batch_deployment(
            limit=args.limit,
            domain=args.domain,
            skip_verify=args.skip_verify
        )
        return
    
    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()

