根据你的需求，我为你提供一个精简的使用指南：

精简使用指南

1. 基础部署命令

# 部署单个工具（按名称）
python main.py --tool "scikit-fem"

# 部署单个工具（按GitHub URL）
python main.py --url "https://github.com/kinnala/scikit-fem"

# 批量部署科学计算工具（前5个）
python main.py --batch --domain "科学计算" --limit 5


2. 并发部署命令（推荐）

# 并发部署科学计算工具（默认2个并发）
python main.py --batch --domain "科学计算" --concurrent

# 并发部署，指定4个并发工作线程
python main.py --batch --domain "科学计算" --concurrent --workers 4

# 并发部署所有工具
python main.py --batch --concurrent --workers 4


3. 快速测试命令

# 快速测试（跳过验证，仅生成Dockerfile）
python main.py --tool "scikit-fem" --skip-verify

# 快速批量测试
python main.py --batch --domain "科学计算" --limit 3 --skip-verify


4. 交互模式

# 交互式部署
python main.py --interactive


5. 查看帮助

# 查看完整帮助
python main.py --help

# 查看版本信息
python main.py --version


常用场景组合

场景1：快速部署科学计算工具栈

# 部署前10个科学计算工具，4并发
python main.py --batch --domain "科学计算" --limit 10 --concurrent --workers 4


场景2：测试特定工具

# 测试scikit-fem，包含完整验证
python main.py --tool "scikit-fem" --skip-verify false


场景3：批量验证现有配置

# 快速验证多个工具配置
python main.py --batch --domain "科学计算" --limit 5 --skip-verify true


参数说明

参数 简写 说明 默认值

--tool -t 部署单个工具（按名称） -

--url -u 部署单个工具（按URL） -

--batch -b 批量部署模式 false

--domain -d 按领域过滤工具 "所有"

--limit -l 限制部署数量 无限制

--concurrent -c 启用并发模式 false

--workers -w 并发工作线程数 2

--skip-verify -s 跳过验证步骤 false

--interactive -i 交互模式 false

使用示例

# 示例1：部署scikit-fem并进行完整验证
python main.py -t "scikit-fem"

# 示例2：并发部署5个科学计算工具
python main.py -b -d "科学计算" -l 5 -c -w 4

# 示例3：快速测试Nek5000（仅生成Dockerfile）
python main.py -t "Nek5000" -s true


注意事项

1. 首次使用建议先测试：使用 --skip-verify true 快速生成Dockerfile
2. 生产部署使用并发：--concurrent --workers 4 显著提升速度
3. 网络问题：确保能正常访问GitHub和Docker Hub
4. 资源限制：并发数不要超过系统CPU核心数

