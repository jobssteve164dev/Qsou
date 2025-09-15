#!/usr/bin/env python3
"""
快速启动脚本
自动化执行开发环境的初始化流程
"""

import os
import sys
import subprocess
import time


def run_command(cmd, description, check_exit_code=True):
    """运行命令并打印状态"""
    print(f"🔄 {description}...")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if check_exit_code and result.returncode != 0:
            print(f"❌ {description} 失败:")
            print(result.stderr)
            return False
        else:
            print(f"✅ {description} 完成")
            if result.stdout:
                # 只显示重要信息，避免输出过多
                lines = result.stdout.strip().split('\n')
                important_lines = [line for line in lines if any(
                    keyword in line.lower() for keyword in ['success', 'complete', 'created', '✅', '完成', '成功']
                )]
                if important_lines:
                    for line in important_lines[-3:]:  # 只显示最后3条重要信息
                        print(f"   {line}")
            return True
            
    except Exception as e:
        print(f"❌ {description} 出现异常: {e}")
        return False


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本")
        return False
    print(f"✅ Python 版本检查通过 ({version.major}.{version.minor}.{version.micro})")
    return True


def main():
    """主函数"""
    print("🚀 Qsou 投资情报搜索引擎 - 快速启动")
    print("=" * 50)
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 步骤1: 检查是否在项目根目录
    if not os.path.exists('PROJECT_MEMORY.md'):
        print("❌ 请在项目根目录运行此脚本")
        sys.exit(1)
    
    # 步骤2: 创建虚拟环境（如果不存在）
    if not os.path.exists('venv'):
        if not run_command('python -m venv venv', '创建Python虚拟环境'):
            sys.exit(1)
    
    # 步骤3: 激活虚拟环境并安装依赖
    activate_cmd = 'venv\\Scripts\\activate' if os.name == 'nt' else 'source venv/bin/activate'
    pip_cmd = f'{activate_cmd} && pip install --upgrade pip && pip install -r requirements.txt'
    
    if not run_command(pip_cmd, '安装Python依赖包'):
        print("⚠️  依赖包安装失败，请手动运行: pip install -r requirements.txt")
    
    # 步骤4: 创建配置文件
    if not os.path.exists('.env'):
        if os.path.exists('env.example'):
            run_command('cp env.example .env' if os.name != 'nt' else 'copy env.example .env', 
                       '创建环境配置文件', check_exit_code=False)
            print("📝 请编辑 .env 文件，配置数据库密码等参数")
        else:
            print("⚠️  env.example 文件不存在，请手动创建 .env 文件")
    
    # 步骤5: 创建必要目录
    directories = ['logs', 'data', 'backups']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ 创建目录: {directory}")
    
    # 步骤6: 验证服务连接
    verify_cmd = f'{activate_cmd} && python scripts/verify_setup.py'
    print("\n🔍 验证服务连接...")
    run_command(verify_cmd, '验证开发环境', check_exit_code=False)
    
    # 步骤7: 提供下一步指引
    print("\n" + "=" * 50)
    print("🎉 快速启动完成！")
    print("\n📋 下一步操作:")
    print("1. 编辑 .env 文件，配置数据库密码")
    print("2. 确保所有服务正在运行:")
    print("   - PostgreSQL (端口 5432)")
    print("   - Redis (端口 6379)")
    print("   - Elasticsearch (端口 9200)")
    print("   - Qdrant (端口 6333)")
    print("\n3. 初始化数据存储:")
    print("   make init-db        # 初始化数据库")
    print("   make init-es        # 初始化搜索引擎")
    print("   make init-qdrant    # 初始化向量数据库")
    print("\n4. 启动开发服务:")
    print("   make dev-api        # 启动API服务")
    print("   make dev-frontend   # 启动前端服务")
    print("   make dev-celery     # 启动任务队列")
    print("\n5. 验证服务状态:")
    print("   make status         # 检查所有服务状态")
    print("\n📖 完整文档: docs/local-development-setup.md")
    
    return True


if __name__ == "__main__":
    main()
