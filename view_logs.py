#!/usr/bin/env python3
"""
日志查看工具 - 方便查看和分析历史日志
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import LOGS_DIR

console = Console()


def list_logs(limit: int = 20):
    """列出所有日志文件"""
    log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not log_files:
        console.print("[yellow]暂无日志文件[/yellow]")
        return []
    
    table = Table(title=f"日志文件列表（最近 {limit} 个）", show_header=True)
    table.add_column("序号", style="cyan", width=6)
    table.add_column("文件名", style="green", width=30)
    table.add_column("大小", style="yellow", width=12)
    table.add_column("创建时间", style="blue", width=20)
    
    for i, log_file in enumerate(log_files[:limit], 1):
        size_kb = log_file.stat().st_size / 1024
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        
        table.add_row(
            str(i),
            log_file.name,
            f"{size_kb:.2f} KB",
            mtime.strftime("%Y-%m-%d %H:%M:%S")
        )
    
    console.print(table)
    
    if len(log_files) > limit:
        console.print(f"\n[dim]显示前 {limit} 个，共 {len(log_files)} 个日志文件[/dim]")
    
    return log_files[:limit]


def view_log(log_file: Path, tail: int = None, grep: str = None):
    """查看日志内容"""
    if not log_file.exists():
        console.print(f"[red]日志文件不存在: {log_file}[/red]")
        return
    
    console.print(Panel(f"📄 日志文件: {log_file.name}", style="bold green"))
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 过滤
    if grep:
        lines = [line for line in lines if grep.lower() in line.lower()]
        console.print(f"[yellow]过滤关键词: {grep}, 匹配 {len(lines)} 行[/yellow]\n")
    
    # 截取
    if tail:
        lines = lines[-tail:]
        console.print(f"[yellow]显示最后 {tail} 行[/yellow]\n")
    
    # 显示
    for line in lines:
        # 根据日志级别着色
        if "ERROR" in line or "❌" in line:
            console.print(line.rstrip(), style="red")
        elif "WARNING" in line or "⚠️" in line:
            console.print(line.rstrip(), style="yellow")
        elif "SUCCESS" in line or "✅" in line:
            console.print(line.rstrip(), style="green")
        else:
            console.print(line.rstrip())


def analyze_log(log_file: Path):
    """分析日志统计信息"""
    if not log_file.exists():
        console.print(f"[red]日志文件不存在: {log_file}[/red]")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 统计
    total_lines = len(lines)
    info_count = sum(1 for line in lines if "INFO" in line)
    warning_count = sum(1 for line in lines if "WARNING" in line)
    error_count = sum(1 for line in lines if "ERROR" in line)
    success_count = sum(1 for line in lines if "成功" in line or "✅" in line)
    failed_count = sum(1 for line in lines if "失败" in line or "❌" in line)
    
    # 显示统计
    console.print(Panel(f"📊 日志分析: {log_file.name}", style="bold blue"))
    
    table = Table(show_header=False)
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    
    table.add_row("总行数", str(total_lines))
    table.add_row("INFO 日志", str(info_count))
    table.add_row("WARNING 日志", f"[yellow]{warning_count}[/yellow]")
    table.add_row("ERROR 日志", f"[red]{error_count}[/red]")
    table.add_row("成功操作", f"[green]{success_count}[/green]")
    table.add_row("失败操作", f"[red]{failed_count}[/red]")
    
    console.print(table)
    
    # 提取关键信息
    console.print("\n[bold cyan]关键事件:[/bold cyan]")
    for line in lines:
        if "开始" in line or "完成" in line or "部署" in line:
            if any(keyword in line for keyword in ["开始批量", "批量处理完成", "开始部署", "部署成功", "部署失败"]):
                console.print(f"  • {line.strip()}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="日志查看工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python view_logs.py                    # 列出所有日志
    python view_logs.py --latest           # 查看最新日志
    python view_logs.py --file 20241206_143022_beijing.log
    python view_logs.py --latest --tail 50 # 查看最新日志的最后50行
    python view_logs.py --latest --grep "ERROR"  # 过滤错误日志
    python view_logs.py --analyze          # 分析最新日志
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true", help="列出所有日志文件")
    parser.add_argument("--latest", action="store_true", help="查看最新日志")
    parser.add_argument("--file", "-f", help="指定日志文件名")
    parser.add_argument("--tail", "-t", type=int, help="只显示最后 N 行")
    parser.add_argument("--grep", "-g", help="过滤包含关键词的行")
    parser.add_argument("--analyze", "-a", action="store_true", help="分析日志统计信息")
    parser.add_argument("--limit", type=int, default=20, help="列表显示数量限制")
    
    args = parser.parse_args()
    
    # 如果没有参数，默认列出日志
    if len(sys.argv) == 1:
        list_logs(limit=args.limit)
        return
    
    # 列出日志
    if args.list:
        list_logs(limit=args.limit)
        return
    
    # 获取目标日志文件
    log_file = None
    if args.file:
        log_file = LOGS_DIR / args.file
    elif args.latest or args.analyze:
        log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            log_file = log_files[0]
        else:
            console.print("[red]未找到日志文件[/red]")
            return
    
    if log_file:
        if args.analyze:
            analyze_log(log_file)
        else:
            view_log(log_file, tail=args.tail, grep=args.grep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

