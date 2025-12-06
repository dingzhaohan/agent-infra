#!/usr/bin/env python3
"""
开源科学工具自动化部署系统
基于 Agno 框架的工作流编排

使用方法:
    # 部署单个工具（按名称）
    python main.py --tool "scikit-fem"
    
    # 部署单个工具（按 URL）
    python main.py --url "https://github.com/kinnala/scikit-fem"
    
    # 批量部署（前5个工具，串行模式）
    python main.py --batch --limit 5
    
    # 批量部署（并发模式，默认2个并发）
    python main.py --batch --concurrent
    
    # 批量部署（并发模式，指定4个并发）
    python main.py --batch --concurrent --workers 4
    
    # 批量部署特定领域（并发模式）
    python main.py --batch --domain "科学计算" --concurrent --workers 4
    
    # 仅分析不验证
    python main.py --tool "scikit-fem" --skip-verify
    
    # 交互模式
    python main.py --interactive
"""
import argparse
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.logging import RichHandler

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import REPOS_DIR, RESULTS_DIR, LOGS_DIR, OPENAI_API_KEY, MAX_CONCURRENT_TOOLS
from utils.list_parser import parse_list_md, get_tools_by_domain, get_tools_by_name
from workflow import RepoDeploymentWorkflow, BatchDeploymentWorkflow, deploy_single_tool

console = Console()


def setup_logging():
    """
    配置日志系统：同时输出到控制台和文件
    使用北京时间（UTC+8）作为时间戳
    """
    # 获取北京时间
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    
    # 生成日志文件名：YYYYMMDD_HHMMSS_beijing.log
    log_filename = beijing_time.strftime("%Y%m%d_%H%M%S_beijing.log")
    log_path = LOGS_DIR / log_filename
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # 设置为 DEBUG 以捕获所有日志
    
    # 清除已有的处理器（避免重复）
    logger.handlers.clear()
    
    # 文件处理器：详细格式，包含时间戳，捕获 DEBUG 及以上级别
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别，包括 DEBUG
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器：使用 RichHandler 保持美观输出
    # 控制台只显示 INFO 及以上，避免过多 DEBUG 信息干扰
    console_handler = RichHandler(
        console=console,
        show_time=False,
        show_path=False,
        markup=True,
        rich_tracebacks=True
    )
    console_handler.setLevel(logging.INFO)  # 控制台保持 INFO 级别
    
    # 配置相关库的 logger 也输出 DEBUG 到文件
    # 包括 Agno、httpx（HTTP 请求）、litellm（LLM 调用）等
    related_loggers = [
        'agno',
        'agno.agent',
        'agno.models',
        'agno.tools',
        'httpx',           # HTTP 客户端（Agno 使用）
        'litellm',         # LLM 调用库
        'openai',          # OpenAI SDK
    ]
    for logger_name in related_loggers:
        related_logger = logging.getLogger(logger_name)
        related_logger.setLevel(logging.DEBUG)
        # 不直接添加 handler，让日志传播到根 logger
        # 这样可以避免重复日志，同时确保所有日志都记录到文件
        related_logger.propagate = True
        # 确保这些 logger 不会阻止日志传播
        related_logger.handlers = []  # 清除可能存在的 handler
    
    # 注意：Agno 的 debug_mode=True 可能会直接 print 到 stdout
    # 这些输出会通过 RichHandler 显示在控制台，但不会自动记录到文件
    # 如果需要捕获这些，可以考虑重定向 stdout/stderr（但可能影响 Rich 输出）
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录启动信息
    logger.info("="*60)
    logger.info(f"开源科学工具自动化部署系统启动")
    logger.info(f"日志文件: {log_path}")
    logger.info(f"北京时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    return str(log_path)


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║        🔬 开源科学工具自动化部署系统 🔬                        ║
║        基于 Agno 框架的智能工作流编排                          ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


def check_prerequisites(skip_docker: bool = False):
    """检查前置条件"""
    issues = []
    
    # 检查 OpenAI API Key
    if not OPENAI_API_KEY:
        issues.append("未设置 OPENAI_API_KEY 环境变量")
    
    # 检查 Docker（如果不跳过验证）
    if not skip_docker:
        import subprocess
        try:
            result = subprocess.run(["docker", "info"], capture_output=True)
            if result.returncode != 0:
                issues.append("Docker 未运行或无法访问")
        except FileNotFoundError:
            issues.append("Docker 未安装")
    
    # 检查 Git
    import subprocess
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
    logger = logging.getLogger(__name__)
    console.print(Panel(f"🚀 开始部署: {tool_name or repo_url}", style="bold green"))
    logger.info(f"开始单个工具部署: {tool_name or repo_url}")
    
    try:
        result = deploy_single_tool(
            tool_name=tool_name,
            repo_url=repo_url,
            skip_verification=skip_verify
        )
        
        if result:
            if result.get("status") == "success":
                console.print("\n[bold green]✅ 部署成功![/bold green]")
                logger.info(f"部署成功: {tool_name or repo_url}")
            elif result.get("status") == "skipped":
                console.print("\n[bold yellow]⏭️ 分析完成（跳过验证）[/bold yellow]")
                logger.info(f"分析完成（跳过验证）: {tool_name or repo_url}")
            else:
                console.print(f"\n[bold red]❌ 部署失败: {result.get('error_message', '未知错误')}[/bold red]")
                logger.error(f"部署失败: {tool_name or repo_url}, 错误: {result.get('error_message', '未知错误')}")
        
        return result
        
    except Exception as e:
        console.print(f"\n[bold red]❌ 部署异常: {str(e)}[/bold red]")
        logger.exception(f"部署异常: {tool_name or repo_url}")
        return None


def run_batch_deployment(
    limit: int = None, 
    domain: str = None, 
    skip_verify: bool = False,
    concurrent: bool = False,
    max_workers: int = MAX_CONCURRENT_TOOLS
):
    """运行批量部署"""
    logger = logging.getLogger(__name__)
    tools = parse_list_md()
    
    if domain:
        tools = get_tools_by_domain(tools, domain)
        console.print(f"[yellow]筛选领域: {domain}, 共 {len(tools)} 个工具[/yellow]")
        logger.info(f"筛选领域: {domain}, 共 {len(tools)} 个工具")
    
    if limit:
        tools = tools[:limit]
        console.print(f"[yellow]限制数量: {limit}[/yellow]")
        logger.info(f"限制数量: {limit}")
    
    mode_text = "并发" if concurrent else "串行"
    workers_text = f"（{max_workers} 个并发进程）" if concurrent else ""
    console.print(Panel(f"🚀 开始批量部署 {len(tools)} 个工具 - {mode_text}模式{workers_text}", style="bold green"))
    logger.info(f"开始批量部署: {len(tools)} 个工具, 模式={mode_text}, workers={max_workers if concurrent else 1}, skip_verify={skip_verify}")
    
    workflow = BatchDeploymentWorkflow(max_workers=max_workers)
    
    for response in workflow.run(
        tools=tools,
        skip_verification=skip_verify,
        concurrent=concurrent
    ):
        console.print(response.content)
        # 也记录到日志文件
        logger.info(response.content)
    
    # 批量部署完成后，自动生成报告
    console.print("\n")
    console.print(Panel("📊 正在生成批量部署报告...", style="bold cyan"))
    logger.info("批量部署完成，生成汇总报告")
    
    try:
        from generate_batch_report import generate_batch_report
        
        # 生成控制台报告
        generate_batch_report(output_format="console")
        
        # 同时生成 JSON 和 Markdown 报告保存到文件
        generate_batch_report(output_format="json")
        generate_batch_report(output_format="markdown")
        
        logger.info("批量部署报告生成完成")
    except Exception as e:
        console.print(f"[yellow]警告: 报告生成失败: {e}[/yellow]")
        logger.warning(f"报告生成失败: {e}")


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
        console.print("  4. 批量部署（串行模式）")
        console.print("  5. 批量部署（并发模式）")
        console.print("  6. 查看部署结果")
        console.print("  7. 退出")
        
        choice = Prompt.ask("请输入选项", choices=["1", "2", "3", "4", "5", "6", "7"])
        
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
                skip_verify=skip_verify,
                concurrent=False
            )
            
        elif choice == "5":
            domain = Prompt.ask("按领域过滤（留空处理全部）", default="")
            limit = int(Prompt.ask("处理数量限制", default="5"))
            max_workers = int(Prompt.ask("并发进程数", default=str(MAX_CONCURRENT_TOOLS)))
            skip_verify = Confirm.ask("是否跳过验证？", default=True)
            run_batch_deployment(
                limit=limit,
                domain=domain if domain else None,
                skip_verify=skip_verify,
                concurrent=True,
                max_workers=max_workers
            )
            
        elif choice == "6":
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
            
        elif choice == "7":
            console.print("[bold blue]👋 再见！[/bold blue]")
            break


def main():
    """主函数"""
    # 配置日志系统（最小侵入，只在这里调用一次）
    log_file = setup_logging()
    
    parser = argparse.ArgumentParser(
        description="开源科学工具自动化部署系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py --tool "scikit-fem"
    python main.py --url "https://github.com/kinnala/scikit-fem"
    python main.py --batch --limit 5
    python main.py --batch --concurrent --workers 4
    python main.py --batch --domain "科学计算" --concurrent
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
    
    # 并发选项
    parser.add_argument("--concurrent", "-c", action="store_true", 
                       help="使用并发模式（仅与 --batch 一起使用）")
    parser.add_argument("--workers", "-w", type=int, default=MAX_CONCURRENT_TOOLS,
                       help=f"并发进程数（默认: {MAX_CONCURRENT_TOOLS}，仅与 --concurrent 一起使用）")
    
    args = parser.parse_args()
    
    # 验证参数组合
    if args.concurrent and not args.batch:
        parser.error("--concurrent 只能与 --batch 一起使用")
    
    if args.workers and not args.concurrent:
        console.print("[yellow]⚠️ --workers 参数需要与 --concurrent 一起使用，将被忽略[/yellow]")
    
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
    
    # 检查前置条件（如果跳过验证则不检查 Docker）
    issues = check_prerequisites(skip_docker=args.skip_verify)
    if issues:
        console.print("[bold red]⚠️ 前置条件检查失败:[/bold red]")
        for issue in issues:
            console.print(f"  - {issue}")
        sys.exit(1)
    
    print_banner()
    console.print(f"[dim]日志文件: {log_file}[/dim]\n")
    
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
            skip_verify=args.skip_verify,
            concurrent=args.concurrent,
            max_workers=args.workers if args.concurrent else MAX_CONCURRENT_TOOLS
        )
        return
    
    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()