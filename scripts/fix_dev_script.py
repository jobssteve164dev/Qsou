#!/usr/bin/env python3
"""
dev.sh 脚本问题诊断和修复工具
"""

import os
import sys
import subprocess
import platform

def diagnose_issues():
    """诊断dev.sh脚本的常见问题"""
    print("🔍 诊断 dev.sh 脚本问题...")
    print("=" * 50)
    
    issues = []
    fixes = []
    
    # 检查1: 脚本权限
    if not os.access("dev.sh", os.X_OK):
        issues.append("dev.sh 脚本没有执行权限")
        fixes.append("运行: chmod +x dev.sh")
    
    # 检查2: 配置文件
    if not os.path.exists("dev.local"):
        issues.append("dev.local 配置文件不存在")
        fixes.append("运行: cp env.example dev.local")
    else:
        print("✅ dev.local 配置文件存在")
    
    # 检查3: Python环境
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Python: {version}")
        else:
            issues.append("Python不可用")
            fixes.append("安装 Python 3.8+")
    except:
        issues.append("无法检查Python版本")
    
    # 检查4: 虚拟环境
    if os.path.exists("venv"):
        print("✅ Python虚拟环境存在")
    else:
        issues.append("Python虚拟环境不存在")
        fixes.append("将会自动创建虚拟环境")
    
    # 检查5: 操作系统特定问题
    os_type = platform.system().lower()
    if os_type == "windows":
        # Windows特定检查
        if not os.path.exists("venv/Scripts/python.exe") and os.path.exists("venv"):
            issues.append("Windows虚拟环境可能损坏")
            fixes.append("删除venv目录并重新创建: rm -rf venv")
    
    # 检查6: 依赖文件
    if not os.path.exists("requirements.txt"):
        issues.append("requirements.txt 不存在")
        fixes.append("确保项目文件完整")
    else:
        print("✅ requirements.txt 存在")
    
    # 输出问题和修复建议
    if issues:
        print("\n❌ 发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        
        print("\n🔧 修复建议:")
        for i, fix in enumerate(fixes, 1):
            print(f"  {i}. {fix}")
    else:
        print("\n✅ 未发现明显问题")
    
    return len(issues) == 0

def create_simple_start_script():
    """创建简化的启动脚本"""
    simple_script = """#!/bin/bash
# 简化版启动脚本 - 用于故障排除

echo "🚀 简化启动脚本"

# 检查基本环境
echo "检查Python..."
python --version || python3 --version || { echo "Python未安装"; exit 1; }

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python -m venv venv || python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# 安装基本依赖
echo "安装基本依赖..."
pip install --upgrade pip
pip install fastapi uvicorn

# 启动API服务
echo "启动API服务..."
echo "如果api-gateway目录存在，请手动运行："
echo "cd api-gateway && uvicorn app.main:app --reload"

echo "简化启动完成"
"""
    
    with open("dev-simple.sh", "w") as f:
        f.write(simple_script)
    
    os.chmod("dev-simple.sh", 0o755)
    print("✅ 创建了简化启动脚本: dev-simple.sh")

def fix_common_issues():
    """修复常见问题"""
    print("\n🔧 修复常见问题...")
    
    # 修复1: 脚本权限
    try:
        os.chmod("dev.sh", 0o755)
        print("✅ 修复脚本执行权限")
    except:
        print("❌ 无法修复脚本权限")
    
    # 修复2: 创建必要目录
    dirs = ["pids", "logs", "data", "backups"]
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✅ 创建目录: {dir_name}")
    
    # 修复3: 配置文件
    if not os.path.exists("dev.local") and os.path.exists("env.example"):
        import shutil
        shutil.copy("env.example", "dev.local")
        print("✅ 创建dev.local配置文件")
    
    # 修复4: 清理问题虚拟环境
    if os.path.exists("venv") and platform.system().lower() == "windows":
        if not os.path.exists("venv/Scripts/python.exe"):
            import shutil
            shutil.rmtree("venv")
            print("✅ 清理损坏的虚拟环境")

def main():
    """主函数"""
    print("🛠️  dev.sh 脚本问题诊断工具")
    print("=" * 50)
    
    # 检查是否在正确目录
    if not os.path.exists("dev.sh"):
        print("❌ 在当前目录找不到 dev.sh 脚本")
        print("请在项目根目录运行此工具")
        return False
    
    # 诊断问题
    no_issues = diagnose_issues()
    
    # 修复常见问题
    fix_common_issues()
    
    # 创建简化脚本
    create_simple_start_script()
    
    print("\n" + "=" * 50)
    print("🎯 下一步建议:")
    
    if no_issues:
        print("1. 尝试运行: ./dev.sh start")
        print("2. 如果还有问题，运行: DEBUG=true ./dev.sh start")
    else:
        print("1. 按照上述修复建议处理问题")
        print("2. 或者先尝试简化脚本: ./dev-simple.sh")
        print("3. 问题修复后再运行: ./dev.sh start")
    
    print("4. 如果需要跳过依赖安装: SKIP_DEPS=true ./dev.sh start")
    print("5. 查看详细帮助: ./dev.sh help")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
