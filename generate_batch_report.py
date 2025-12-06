#!/usr/bin/env python3
"""
批量部署报告生成器
基于 logs 和 results 文件生成汇总报告，无需重新分析
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import RESULTS_DIR, LOGS_DIR

console = Console()


def generate_batch_report(log_file: Path = None, output_format: str = "console"):
    """
    生成批量部署报告
    
    Args:
        log_file: 日志文件路径（None=不关联日志）
        output_format: 输出格式 (console/json/markdown)
    
    Returns:
        dict or str: 报告内容
    """
    # 1. 读取所有 results
    results = []
    if not RESULTS_DIR.exists() or not list(RESULTS_DIR.glob("*.json")):
        console.print("[yellow]未找到任何部署结果文件[/yellow]")
        return None
    
    for result_file in RESULTS_DIR.glob("*.json"):
        if result_file.name.startswith("batch_report_"):
            continue  # 跳过之前的报告文件
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                results.append(json.load(f))
        except Exception as e:
            console.print(f"[yellow]警告: 无法读取 {result_file.name}: {e}[/yellow]")
    
    if not results:
        console.print("[yellow]未找到有效的部署结果[/yellow]")
        return None
    
    # 2. 统计
    stats = {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "success"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
    }
    
    # 3. 按状态分组
    by_status = defaultdict(list)
    for r in results:
        status = r.get("status", "unknown")
        tool_info = {
            "name": r.get("tool_name", "未知"),
            "error": r.get("error_message", ""),
            "image": r.get("image_name", ""),
            "path": r.get("dockerfile_path", ""),
            "retry_count": r.get("retry_count", 0)
        }
        by_status[status].append(tool_info)
    
    # 4. 生成报告
    if output_format == "console":
        _print_console_report(stats, by_status, log_file)
        return stats
    elif output_format == "json":
        return _generate_json_report(stats, by_status, results, log_file)
    elif output_format == "markdown":
        return _generate_markdown_report(stats, by_status, results, log_file)


def _print_console_report(stats, by_status, log_file):
    """打印控制台报告"""
    console.print(Panel("📊 批量部署汇总报告", style="bold blue"))
    
    if log_file:
        console.print(f"[dim]关联日志: {log_file.name}[/dim]\n")
    
    # 统计表
    table = Table(title="统计信息", show_header=True)
    table.add_column("指标", style="cyan", width=15)
    table.add_column("数量", style="green", width=10)
    table.add_column("百分比", style="yellow", width=10)
    
    table.add_row("总工具数", str(stats["total"]), "100%")
    
    if stats["total"] > 0:
        success_pct = f"{stats['success']/stats['total']*100:.1f}%"
        failed_pct = f"{stats['failed']/stats['total']*100:.1f}%"
        skipped_pct = f"{stats['skipped']/stats['total']*100:.1f}%"
    else:
        success_pct = failed_pct = skipped_pct = "0%"
    
    table.add_row("成功", f"[green]{stats['success']}[/green]", f"[green]{success_pct}[/green]")
    table.add_row("失败", f"[red]{stats['failed']}[/red]", f"[red]{failed_pct}[/red]")
    table.add_row("跳过", f"[yellow]{stats['skipped']}[/yellow]", f"[yellow]{skipped_pct}[/yellow]")
    
    console.print(table)
    
    # 详细列表
    if by_status["success"]:
        console.print(f"\n[bold green]✅ 成功的工具 ({len(by_status['success'])} 个):[/bold green]")
        for tool_info in by_status["success"]:
            retry_info = f" (重试 {tool_info['retry_count']} 次)" if tool_info['retry_count'] > 1 else ""
            console.print(f"  • {tool_info['name']}{retry_info}")
            if tool_info['image']:
                console.print(f"    [dim]镜像: {tool_info['image']}[/dim]")
    
    if by_status["failed"]:
        console.print(f"\n[bold red]❌ 失败的工具 ({len(by_status['failed'])} 个):[/bold red]")
        for tool_info in by_status["failed"]:
            console.print(f"  • {tool_info['name']}")
            if tool_info['error']:
                # 截取错误信息前100个字符
                error_short = tool_info['error'][:100] + "..." if len(tool_info['error']) > 100 else tool_info['error']
                console.print(f"    [red]{error_short}[/red]")
    
    if by_status["skipped"]:
        console.print(f"\n[bold yellow]⏭️ 跳过的工具 ({len(by_status['skipped'])} 个):[/bold yellow]")
        for tool_info in by_status["skipped"]:
            console.print(f"  • {tool_info['name']}")
            if tool_info['error']:
                console.print(f"    [yellow]{tool_info['error']}[/yellow]")


def _generate_json_report(stats, by_status, results, log_file):
    """生成 JSON 报告"""
    beijing_time = datetime.now()
    
    report = {
        "generated_at": beijing_time.strftime("%Y-%m-%d %H:%M:%S"),
        "log_file": log_file.name if log_file else None,
        "summary": stats,
        "success_rate": f"{stats['success']/stats['total']*100:.1f}%" if stats['total'] > 0 else "0%",
        "by_status": {
            status: [tool["name"] for tool in tools]
            for status, tools in by_status.items()
        },
        "details": results
    }
    
    # 保存到文件
    report_filename = f"batch_report_{beijing_time.strftime('%Y%m%d_%H%M%S')}.json"
    report_file = RESULTS_DIR / report_filename
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    console.print(f"\n[green]✅ JSON 报告已保存: {report_file}[/green]")
    return report


def _generate_markdown_report(stats, by_status, results, log_file):
    """生成 Markdown 报告"""
    beijing_time = datetime.now()
    
    lines = []
    lines.append("# 批量部署汇总报告\n")
    lines.append(f"**生成时间**: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)\n")
    
    if log_file:
        lines.append(f"**日志文件**: `{log_file.name}`\n")
    
    lines.append("\n## 📊 统计信息\n")
    lines.append(f"- **总工具数**: {stats['total']}")
    
    if stats['total'] > 0:
        success_rate = stats['success']/stats['total']*100
        lines.append(f"- **成功率**: {success_rate:.1f}%")
    
    lines.append(f"- ✅ **成功**: {stats['success']}")
    lines.append(f"- ❌ **失败**: {stats['failed']}")
    lines.append(f"- ⏭️ **跳过**: {stats['skipped']}\n")
    
    if by_status["success"]:
        lines.append(f"\n## ✅ 成功的工具 ({len(by_status['success'])} 个)\n")
        for tool_info in by_status["success"]:
            retry_info = f" *(重试 {tool_info['retry_count']} 次)*" if tool_info['retry_count'] > 1 else ""
            lines.append(f"- **{tool_info['name']}**{retry_info}")
            if tool_info['image']:
                lines.append(f"  - 镜像: `{tool_info['image']}`")
    
    if by_status["failed"]:
        lines.append(f"\n## ❌ 失败的工具 ({len(by_status['failed'])} 个)\n")
        for tool_info in by_status["failed"]:
            lines.append(f"- **{tool_info['name']}**")
            if tool_info['error']:
                lines.append(f"  - 错误: {tool_info['error']}")
    
    if by_status["skipped"]:
        lines.append(f"\n## ⏭️ 跳过的工具 ({len(by_status['skipped'])} 个)\n")
        for tool_info in by_status["skipped"]:
            lines.append(f"- **{tool_info['name']}**")
            if tool_info['error']:
                lines.append(f"  - 原因: {tool_info['error']}")
    
    lines.append("\n---\n")
    lines.append(f"*报告生成于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    content = "\n".join(lines)
    
    # 保存到文件
    report_filename = f"batch_report_{beijing_time.strftime('%Y%m%d_%H%M%S')}.md"
    report_file = RESULTS_DIR / report_filename
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    console.print(f"\n[green]✅ Markdown 报告已保存: {report_file}[/green]")
    return content


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="生成批量部署报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python generate_batch_report.py                  # 控制台输出
    python generate_batch_report.py --format json    # 生成 JSON 报告
    python generate_batch_report.py --format markdown # 生成 Markdown 报告
    python generate_batch_report.py --log 20241206_143022_beijing.log --format json
        """
    )
    
    parser.add_argument("--format", "-f", 
                       choices=["console", "json", "markdown"],
                       default="console", 
                       help="输出格式")
    parser.add_argument("--log", "-l", 
                       help="关联的日志文件名")
    
    args = parser.parse_args()
    
    log_file = None
    if args.log:
        log_file = LOGS_DIR / args.log
        if not log_file.exists():
            console.print(f"[yellow]警告: 日志文件不存在: {log_file}[/yellow]")
            log_file = None
    
    generate_batch_report(log_file=log_file, output_format=args.format)


if __name__ == "__main__":
    main()

