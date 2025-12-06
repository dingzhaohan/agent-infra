"""
工具列表解析器 - 从 list.csv 或 list.md 中解析开源工具列表
"""
import re
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from config import BASE_DIR


@dataclass
class Tool:
    """开源工具数据类"""
    topic: str                           # 话题
    domain: str                          # 领域（大类/子类）
    name: str                            # 工具名
    version: str                         # 版本号
    homepage: str                        # 工具主页 (GitHub/GitLab URL)
    docs_url: Optional[str] = None       # 文档链接
    external_data: Optional[str] = None  # 外部数据依赖
    
    @property
    def repo_name(self) -> str:
        """从 homepage 提取仓库名"""
        # 处理 GitHub/GitLab URL
        url = self.homepage.rstrip('/')
        parts = url.split('/')
        if len(parts) >= 2:
            return parts[-1]
        return self.name.lower().replace(' ', '-')
    
    @property
    def clone_url(self) -> str:
        """获取 git clone URL"""
        url = self.homepage.rstrip('/')
        if 'github.com' in url or 'gitlab.com' in url:
            return f"{url}.git"
        return url
    
    @property
    def is_github(self) -> bool:
        return 'github.com' in self.homepage
    
    @property
    def is_gitlab(self) -> bool:
        return 'gitlab' in self.homepage


def parse_list_csv(file_path: Optional[Path] = None) -> list[Tool]:
    """
    解析 list.csv 文件，返回工具列表
    
    CSV 格式:
    话题,领域（大类/子类）,工具名,版本号,工具主页,文档链接,外部数据依赖（类型；无则空）
    """
    if file_path is None:
        file_path = BASE_DIR / "utils" / "list.csv"
    
    tools = []
    
    # 使用 utf-8-sig 自动去除 BOM
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # 提取字段
            topic = row.get('话题', '').strip()
            domain = row.get('领域（大类/子类）', '').strip()
            name = row.get('工具名', '').strip()
            version = row.get('版本号', '').strip()
            homepage = row.get('工具主页', '').strip()
            docs_url = row.get('文档链接', '').strip()
            external_data = row.get('外部数据依赖（类型；无则空）', '').strip()
            
            # 验证必填字段
            if not name or not homepage:
                continue
            
            # 验证 homepage 是否是有效的 URL
            if not homepage.startswith('http'):
                continue
            
            # 处理可选字段（空字符串转为 None）
            docs_url = docs_url if docs_url else None
            external_data = external_data if external_data else None
            
            tool = Tool(
                topic=topic,
                domain=domain,
                name=name,
                version=version,
                homepage=homepage,
                docs_url=docs_url,
                external_data=external_data
            )
            tools.append(tool)
    
    return tools


def parse_list_md(file_path: Optional[Path] = None) -> list[Tool]:
    """
    解析 list.md 文件，返回工具列表
    
    list.md 格式（固定 7 行一组）:
    第1行: 话题
    第2行: 领域（大类/子类）
    第3行: 工具名
    第4行: 版本号
    第5行: 工具主页
    第6行: 文档链接
    第7行: 外部数据依赖（可能为空行）
    """
    if file_path is None:
        file_path = BASE_DIR / "list.md"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    tools = []
    
    # 找到实际数据开始的位置（跳过前 7 行标题）
    data_start = 7
    
    # 每个条目固定占 7 行
    LINES_PER_ENTRY = 7
    data_lines = lines[data_start:]
    total_entries = len(data_lines) // LINES_PER_ENTRY
    
    for i in range(total_entries):
        start_idx = i * LINES_PER_ENTRY
        end_idx = start_idx + LINES_PER_ENTRY
        entry_lines = [line.strip() for line in data_lines[start_idx:end_idx]]
        
        tool = _parse_entry(entry_lines)
        if tool:
            tools.append(tool)
    
    return tools


def parse_tools(file_path: Optional[Path] = None) -> list[Tool]:
    """
    自动检测并解析工具列表文件（优先使用 CSV）
    
    Args:
        file_path: 可选的文件路径。如果未提供，自动查找 list.csv 或 list.md
    
    Returns:
        Tool 对象列表
    """
    if file_path is not None:
        # 如果指定了文件路径，根据扩展名选择解析器
        if str(file_path).endswith('.csv'):
            return parse_list_csv(file_path)
        else:
            return parse_list_md(file_path)
    
    # 自动检测：优先使用 CSV
    csv_path = BASE_DIR / "utils" / "list.csv"
    if csv_path.exists():
        return parse_list_csv(csv_path)
    
    # 回退到 MD
    md_path = BASE_DIR / "list.md"
    if md_path.exists():
        return parse_list_md(md_path)
    
    raise FileNotFoundError("找不到 list.csv 或 list.md 文件")


def _parse_entry(lines: list[str]) -> Optional[Tool]:
    """
    解析单个工具条目（固定 7 行格式）
    
    第1行: 话题
    第2行: 领域（大类/子类）
    第3行: 工具名
    第4行: 版本号
    第5行: 工具主页
    第6行: 文档链接
    第7行: 外部数据依赖
    """
    if len(lines) < 7:
        return None
    
    # 提取字段
    topic = lines[0].strip()
    domain = lines[1].strip()
    name = lines[2].strip()
    version = lines[3].strip()
    homepage = lines[4].strip()
    docs_url = lines[5].strip()
    external_data = lines[6].strip()
    
    # 验证必填字段
    if not name or not homepage:
        return None
    
    # 验证 homepage 是否是有效的 URL
    if not homepage.startswith('http'):
        return None
    
    # 处理可选字段（空字符串转为 None）
    docs_url = docs_url if docs_url else None
    external_data = external_data if external_data else None
    
    return Tool(
        topic=topic,
        domain=domain,
        name=name,
        version=version,
        homepage=homepage,
        docs_url=docs_url,
        external_data=external_data
    )


def get_tools_by_domain(tools: list[Tool], domain: str) -> list[Tool]:
    """按领域筛选工具"""
    return [t for t in tools if domain.lower() in t.domain.lower()]


def get_tools_by_name(tools: list[Tool], name: str) -> list[Tool]:
    """按名称搜索工具"""
    return [t for t in tools if name.lower() in t.name.lower()]


if __name__ == "__main__":
    # 测试解析（自动检测 CSV 或 MD 格式）
    print("自动检测并解析工具列表...")
    tools = parse_tools()
    print(f"✅ 解析到 {len(tools)} 个工具\n")
    
    # 显示前 5 个工具
    print("前 5 个工具:")
    for i, tool in enumerate(tools[:5], 1):
        print(f"{i}. {tool.name}")
        print(f"   话题: {tool.topic}")
        print(f"   领域: {tool.domain}")
        print(f"   版本: {tool.version}")
        print(f"   主页: {tool.homepage}")
        if tool.docs_url:
            print(f"   文档: {tool.docs_url}")
        if tool.external_data:
            print(f"   外部依赖: {tool.external_data}")
        print()
    
    # 统计信息
    print("\n统计信息:")
    print(f"- 总工具数: {len(tools)}")
    print(f"- 有文档链接: {sum(1 for t in tools if t.docs_url)}")
    print(f"- 有外部依赖: {sum(1 for t in tools if t.external_data)}")
    
    # 测试查询功能
    print("\n测试查询功能:")
    bio_tools = get_tools_by_domain(tools, "生物")
    print(f"- 生物相关工具: {len(bio_tools)} 个")
    
    fem_tools = get_tools_by_domain(tools, "FEM")
    print(f"- FEM 相关工具: {len(fem_tools)} 个")

