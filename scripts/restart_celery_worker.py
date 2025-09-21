#!/usr/bin/env python3
"""
重启Celery Worker脚本

用于在Worker进程停止时自动重启
"""

import sys
import os
import subprocess
import time
import signal
from datetime import datetime

def log_info(message):
    """打印信息日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] {message}")

def log_error(message):
    """打印错误日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {message}")

def log_success(message):
    """打印成功日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] {message}")

def check_worker_running():
    """检查Worker是否在运行"""
    try:
        from tasks import app
        inspect = app.control.inspect()
        stats = inspect.stats()
        return bool(stats)
    except Exception as e:
        log_error(f"检查Worker状态失败: {e}")
        return False

def restart_celery_worker():
    """重启Celery Worker"""
    log_info("重启Celery Worker...")
    
    # 项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_processor_dir = os.path.join(project_root, 'data-processor')
    python_exe = os.path.join(project_root, 'api-gateway', '.venv', 'Scripts', 'python.exe')
    
    if not os.path.exists(python_exe):
        log_error(f"Python可执行文件不存在: {python_exe}")
        return False
    
    # 构建启动命令
    cmd = [
        python_exe, '-m', 'celery', '-A', 'tasks', 'worker',
        '-P', 'solo',  # Windows使用solo池
        '--concurrency=1',
        '--loglevel=info'
    ]
    
    log_info(f"启动命令: {' '.join(cmd)}")
    log_info(f"工作目录: {data_processor_dir}")
    
    try:
        # 启动Worker进程
        process = subprocess.Popen(
            cmd,
            cwd=data_processor_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        log_success(f"Celery Worker已启动，PID: {process.pid}")
        
        # 等待Worker启动
        log_info("等待Worker启动...")
        for i in range(10):
            time.sleep(2)
            if check_worker_running():
                log_success("Worker启动成功并响应检查")
                return True
            log_info(f"等待中... ({i+1}/10)")
        
        log_error("Worker启动超时")
        return False
        
    except Exception as e:
        log_error(f"启动Worker失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("Celery Worker重启脚本")
    print("=" * 50)
    
    # 检查当前状态
    log_info("检查当前Worker状态...")
    if check_worker_running():
        log_success("Worker正在运行")
        return True
    
    log_info("Worker未运行，开始重启...")
    
    # 重启Worker
    success = restart_celery_worker()
    
    if success:
        log_success("Worker重启成功")
    else:
        log_error("Worker重启失败")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
