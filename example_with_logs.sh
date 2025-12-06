#!/bin/bash
# 演示日志系统的使用示例

set -e

echo "=========================================="
echo "日志系统使用示例"
echo "=========================================="
echo ""

# 示例 1: 运行一个简单命令并查看日志
echo "示例 1: 运行帮助命令并查看日志"
echo "------------------------------------------"
python main.py --help
echo ""
echo "查看刚才生成的日志:"
python view_logs.py --latest
echo ""
read -p "按回车继续下一个示例..."
echo ""

# 示例 2: 列出工具并查看日志
echo "示例 2: 列出工具并查看日志统计"
echo "------------------------------------------"
python main.py --list --limit 5
echo ""
echo "查看日志统计:"
python view_logs.py --analyze
echo ""
read -p "按回车继续下一个示例..."
echo ""

# 示例 3: 查看历史日志
echo "示例 3: 查看所有历史日志"
echo "------------------------------------------"
python view_logs.py --list
echo ""
read -p "按回车继续下一个示例..."
echo ""

# 示例 4: 过滤日志
echo "示例 4: 过滤包含特定关键词的日志"
echo "------------------------------------------"
echo "查看包含 '工具' 的日志行:"
python view_logs.py --latest --grep "工具"
echo ""

echo "=========================================="
echo "示例完成！"
echo "=========================================="
echo ""
echo "日志文件保存在 logs/ 目录下"
echo "使用 'python view_logs.py' 可以随时查看"
echo ""
echo "更多帮助: python view_logs.py --help"

