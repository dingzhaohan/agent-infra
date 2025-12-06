"""
工具列表解析器 - 从 list.md 中解析开源工具列表
"""
import re
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


def parse_list_md(file_path: Optional[Path] = None) -> list[Tool]:
    """
    解析 list.md 文件，返回工具列表
    
    list.md 格式（以空行分隔的记录块）:
    话题
    领域（大类/子类）
    工具名
    版本号
    工具主页
    文档链接（可选）
    外部数据依赖（可选）
    """
    if file_path is None:
        file_path = BASE_DIR / "list.md"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tools = []
    
    # 跳过标题行（话题、领域等）
    lines = content.strip().split('\n')
    
    # 找到实际数据开始的位置（跳过标题）
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip() == '外部数据依赖（类型；无则空）':
            data_start = i + 1
            break
    
    # 按空行分割成记录块
    current_block = []
    
    for line in lines[data_start:]:
        stripped = line.strip()
        if stripped == '':
            if current_block:
                tool = _parse_block(current_block)
                if tool:
                    tools.append(tool)
                current_block = []
        else:
            current_block.append(stripped)
    
    # 处理最后一个块
    if current_block:
        tool = _parse_block(current_block)
        if tool:
            tools.append(tool)
    
    return tools


def _parse_block(lines: list[str]) -> Optional[Tool]:
    """解析单个工具记录块"""
    if len(lines) < 5:
        return None
    
    # 基本字段
    topic = lines[0]
    domain = lines[1]
    name = lines[2]
    version = lines[3]
    homepage = lines[4]
    
    # 验证 homepage 是否是有效的 URL
    if not homepage.startswith('http'):
        return None
    
    # 可选字段
    docs_url = None
    external_data = None
    
    if len(lines) > 5:
        # 第6行可能是文档链接或外部数据依赖
        if lines[5].startswith('http'):
            docs_url = lines[5]
            if len(lines) > 6:
                external_data = lines[6]
        else:
            external_data = lines[5]
    
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
    # 测试解析
    tools = parse_list_md()
    print(f"解析到 {len(tools)} 个工具")
    for tool in tools[:5]:
        print(f"  - {tool.name}: {tool.homepage}")

