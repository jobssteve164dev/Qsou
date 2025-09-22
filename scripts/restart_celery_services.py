#!/usr/bin/env python3
"""
重启Celery服务脚本

用于重启Celery Worker和Beat调度器
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

def kill_process_by_pid_file(pid_file_path):
    """通过PID文件杀死进程"""
    if not os.path.exists(pid_file_path):
        log_info(f"PID文件不存在: {pid_file_path}")
        return True
    
    try:
        with open(pid_file_path, 'r') as f:
            pid = int(f.read().strip())
        
        log_info(f"尝试停止进程 PID: {pid}")
        
        if os.name == 'nt':  # Windows
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                         capture_output=True, check=False)
        else:  # Unix/Linux
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # 进程已经停止
        
        # 删除PID文件
        os.remove(pid_file_path)
        log_success(f"进程 {pid} 已停止")
        return True
        
    except Exception as e:
        log_error(f"停止进程失败: {e}")
        return False

def restart_celery_worker():
    """重启Celery Worker"""
    log_info("重启Celery Worker...")
    
    # 项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_processor_dir = os.path.join(project_root, 'data-processor')
    python_exe = os.path.join(project_root, 'api-gateway', '.venv', 'Scripts', 'python.exe')
    pid_file = os.path.join(project_root, 'pids', 'celery-worker.pid')
    
    # 停止现有Worker
    kill_process_by_pid_file(pid_file)
    
    if not os.path.exists(python_exe):
        log_error(f"Python可执行文件不存在: {python_exe}")
        return False
    
    # 构建启动命令
    cmd = [
        python_exe, '-m', 'celery', '-A', 'tasks', 'worker',
        '-P', 'solo',  # Windows使用solo池
        '--concurrency=1',
        '--loglevel=info',
        '-Q', 'data_processing,ml_processing,indexing,celery'
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
        
        # 保存PID
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        log_success(f"Celery Worker已启动，PID: {process.pid}")
        return True
        
    except Exception as e:
        log_error(f"启动Worker失败: {e}")
        return False

def restart_celery_beat():
    """重启Celery Beat调度器"""
    log_info("重启Celery Beat调度器...")
    
    # 项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_processor_dir = os.path.join(project_root, 'data-processor')
    python_exe = os.path.join(project_root, 'api-gateway', '.venv', 'Scripts', 'python.exe')
    pid_file = os.path.join(project_root, 'pids', 'celery-beat.pid')
    
    # 停止现有Beat
    kill_process_by_pid_file(pid_file)
    
    if not os.path.exists(python_exe):
        log_error(f"Python可执行文件不存在: {python_exe}")
        return False
    
    # 构建启动命令
    cmd = [
        python_exe, '-m', 'celery', '-A', 'tasks', 'beat',
        '--loglevel=info'
    ]
    
    log_info(f"启动命令: {' '.join(cmd)}")
    log_info(f"工作目录: {data_processor_dir}")
    
    try:
        # 启动Beat进程
        process = subprocess.Popen(
            cmd,
            cwd=data_processor_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        # 保存PID
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        log_success(f"Celery Beat已启动，PID: {process.pid}")
        return True
        
    except Exception as e:
        log_error(f"启动Beat失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("Celery服务重启脚本")
    print("=" * 50)
    
    # 重启Worker
    worker_success = restart_celery_worker()
    
    # 等待一下
    time.sleep(3)
    
    # 重启Beat
    beat_success = restart_celery_beat()
    
    if worker_success and beat_success:
        log_success("所有Celery服务重启成功")
        log_info("等待服务完全启动...")
        time.sleep(5)
        log_info("服务重启完成")
    else:
        log_error("部分服务重启失败")
    
    return worker_success and beat_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
