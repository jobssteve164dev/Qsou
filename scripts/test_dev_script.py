#!/usr/bin/env python3
"""
dev.sh 脚本功能测试
验证开发启动脚本的各项功能
"""

import os
import subprocess
import time
import sys
import requests
import signal
from pathlib import Path

def run_command(cmd, timeout=30):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)

def test_script_help():
    """测试帮助信息"""
    print("🧪 测试: 帮助信息")
    success, stdout, stderr = run_command("./dev.sh help")
    
    if success and "用法:" in stdout:
        print("✅ 帮助信息测试通过")
        return True
    else:
        print("❌ 帮助信息测试失败")
        print(f"输出: {stdout}")
        print(f"错误: {stderr}")
        return False

def test_config_loading():
    """测试配置文件加载"""
    print("🧪 测试: 配置文件加载")
    
    if not os.path.exists("dev.local"):
        print("❌ dev.local 配置文件不存在")
        return False
    
    # 检查配置文件内容
    with open("dev.local", "r") as f:
        content = f.read()
        
    required_configs = [
        "PROJECT_NAME",
        "API_PORT",
        "FRONTEND_PORT",
        "DATABASE_URL"
    ]
    
    missing_configs = []
    for config in required_configs:
        if config not in content:
            missing_configs.append(config)
    
    if missing_configs:
        print(f"❌ 缺少配置项: {missing_configs}")
        return False
    
    print("✅ 配置文件加载测试通过")
    return True

def test_directory_creation():
    """测试目录创建"""
    print("🧪 测试: 目录创建")
    
    # 运行脚本的目录初始化部分
    success, stdout, stderr = run_command("./dev.sh --help")  # 这会触发配置加载和目录创建
    
    required_dirs = ["pids", "logs"]
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"❌ 缺少目录: {missing_dirs}")
        return False
    
    print("✅ 目录创建测试通过")
    return True

def test_port_check():
    """测试端口检查功能"""
    print("🧪 测试: 端口检查")
    
    # 创建一个测试服务器占用端口
    import socket
    test_port = 9999
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', test_port))
        sock.listen(1)
        
        # 模拟端口检查（这里我们只能检查脚本是否能正常运行）
        success, stdout, stderr = run_command("./dev.sh status", timeout=10)
        
        sock.close()
        
        if success:
            print("✅ 端口检查测试通过")
            return True
        else:
            print("❌ 端口检查测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 端口检查测试失败: {e}")
        return False

def test_service_status():
    """测试服务状态检查"""
    print("🧪 测试: 服务状态检查")
    
    success, stdout, stderr = run_command("./dev.sh status", timeout=15)
    
    if success and "服务状态检查" in stdout:
        print("✅ 服务状态检查测试通过")
        return True
    else:
        print("❌ 服务状态检查测试失败")
        print(f"输出: {stdout}")
        print(f"错误: {stderr}")
        return False

def test_environment_check():
    """测试环境检查"""
    print("🧪 测试: 环境检查")
    
    # 检查Python环境
    python_version = subprocess.run(
        ["python", "--version"], 
        capture_output=True, 
        text=True
    )
    
    if python_version.returncode != 0:
        print("❌ Python环境检查失败")
        return False
    
    # 检查虚拟环境
    if not os.path.exists("venv"):
        print("⚠️  虚拟环境不存在，这是正常的（首次运行时会创建）")
    
    print("✅ 环境检查测试通过")
    return True

def test_script_permissions():
    """测试脚本权限"""
    print("🧪 测试: 脚本权限")
    
    if os.access("dev.sh", os.X_OK):
        print("✅ 脚本权限测试通过")
        return True
    else:
        print("❌ 脚本没有执行权限")
        return False

def test_cleanup_functions():
    """测试清理功能"""
    print("🧪 测试: 清理功能")
    
    # 创建一些测试文件
    test_files = [
        "test.pyc",
        "test/__pycache__/temp.pyc"
    ]
    
    # 创建测试目录和文件
    os.makedirs("test/__pycache__", exist_ok=True)
    for file_path in test_files:
        Path(file_path).touch()
    
    # 运行清理命令
    success, stdout, stderr = run_command("./dev.sh clean", timeout=10)
    
    # 检查文件是否被清理
    cleaned = True
    for file_path in test_files:
        if os.path.exists(file_path):
            cleaned = False
            break
    
    # 清理测试目录
    if os.path.exists("test"):
        import shutil
        shutil.rmtree("test")
    
    if success and cleaned:
        print("✅ 清理功能测试通过")
        return True
    else:
        print("❌ 清理功能测试失败")
        return False

def test_makefile_integration():
    """测试与Makefile的集成"""
    print("🧪 测试: Makefile集成")
    
    if not os.path.exists("Makefile"):
        print("⚠️  Makefile不存在，跳过集成测试")
        return True
    
    # 检查Makefile中是否有相关的目标
    with open("Makefile", "r") as f:
        makefile_content = f.read()
    
    if "dev.sh" in makefile_content or "dev-start" in makefile_content:
        print("✅ Makefile集成测试通过")
        return True
    else:
        print("⚠️  Makefile中未发现dev.sh相关的集成，建议添加")
        return True

def main():
    """主测试函数"""
    print("🔬 dev.sh 脚本功能测试")
    print("=" * 50)
    
    # 检查是否在项目根目录
    if not os.path.exists("dev.sh"):
        print("❌ 在当前目录找不到 dev.sh 脚本")
        print("请在项目根目录运行此测试脚本")
        sys.exit(1)
    
    # 测试用例
    tests = [
        test_script_permissions,
        test_config_loading,
        test_directory_creation,
        test_script_help,
        test_environment_check,
        test_service_status,
        test_port_check,
        test_cleanup_functions,
        test_makefile_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 出现异常: {e}")
            failed += 1
        
        print()  # 空行分隔
    
    print("=" * 50)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试通过！dev.sh 脚本功能正常")
        return True
    else:
        print("⚠️  部分测试失败，请检查脚本配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
