#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务管理器 - 管理日志收集器和其他后台服务
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
import psutil
import argparse

# Windows环境设置UTF-8编码
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

class ServiceManager:
    """服务管理器"""
    
    def __init__(self, pid_dir="pids"):
        self.pid_dir = Path(pid_dir)
        self.pid_dir.mkdir(exist_ok=True)
        self.services = {}
        
    def register_service(self, name, pid):
        """注册服务"""
        self.services[name] = pid
        pid_file = self.pid_dir / f"{name}.pid"
        pid_file.write_text(str(pid))
        print(f"✓ 注册服务 {name} (PID: {pid})")
        
    def unregister_service(self, name):
        """注销服务"""
        if name in self.services:
            del self.services[name]
        pid_file = self.pid_dir / f"{name}.pid"
        if pid_file.exists():
            pid_file.unlink()
        print(f"✓ 注销服务 {name}")
        
    def get_service_pid(self, name):
        """获取服务PID"""
        pid_file = self.pid_dir / f"{name}.pid"
        if pid_file.exists():
            try:
                return int(pid_file.read_text().strip())
            except:
                pass
        return None
        
    def is_service_running(self, name):
        """检查服务是否运行"""
        pid = self.get_service_pid(name)
        if pid:
            try:
                process = psutil.Process(pid)
                return process.is_running()
            except:
                pass
        return False
        
    def stop_service(self, name, timeout=10):
        """停止服务"""
        pid = self.get_service_pid(name)
        if not pid:
            print(f"服务 {name} 未运行")
            return True
            
        try:
            process = psutil.Process(pid)
            print(f"停止服务 {name} (PID: {pid})...")
            
            # 发送终止信号
            process.terminate()
            
            # 等待进程退出
            try:
                process.wait(timeout=timeout)
                print(f"✓ 服务 {name} 已优雅停止")
            except psutil.TimeoutExpired:
                # 强制杀死
                print(f"服务 {name} 未响应，强制终止...")
                process.kill()
                process.wait(timeout=5)
                print(f"✓ 服务 {name} 已强制停止")
                
            self.unregister_service(name)
            return True
            
        except psutil.NoSuchProcess:
            print(f"服务 {name} 进程不存在")
            self.unregister_service(name)
            return True
        except Exception as e:
            print(f"停止服务 {name} 失败: {e}")
            return False
            
    def stop_all_services(self):
        """停止所有服务"""
        print("停止所有服务...")
        
        # 获取所有PID文件
        pid_files = list(self.pid_dir.glob("*.pid"))
        
        for pid_file in pid_files:
            service_name = pid_file.stem
            self.stop_service(service_name)
            
        print("✓ 所有服务已停止")
        
    def cleanup_dead_services(self):
        """清理已死亡的服务"""
        print("清理已死亡的服务...")
        
        pid_files = list(self.pid_dir.glob("*.pid"))
        
        for pid_file in pid_files:
            service_name = pid_file.stem
            if not self.is_service_running(service_name):
                print(f"清理死亡服务: {service_name}")
                self.unregister_service(service_name)
                
    def list_services(self):
        """列出所有服务"""
        print("\n服务状态:")
        print("-" * 40)
        
        pid_files = list(self.pid_dir.glob("*.pid"))
        
        if not pid_files:
            print("没有运行中的服务")
            return
            
        for pid_file in pid_files:
            service_name = pid_file.stem
            pid = self.get_service_pid(service_name)
            
            if self.is_service_running(service_name):
                try:
                    process = psutil.Process(pid)
                    cpu = process.cpu_percent(interval=0.1)
                    mem = process.memory_info().rss / 1024 / 1024  # MB
                    status = f"运行中 (CPU: {cpu:.1f}%, 内存: {mem:.1f}MB)"
                except:
                    status = "运行中"
            else:
                status = "已停止（PID文件存在）"
                
            print(f"{service_name:<20} PID: {pid:<8} {status}")
            
        print("-" * 40)
        
    def monitor_services(self, interval=5):
        """监控服务状态"""
        print(f"监控服务状态 (每{interval}秒刷新，按Ctrl+C退出)...")
        
        try:
            while True:
                os.system('cls' if sys.platform == 'win32' else 'clear')
                self.list_services()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n监控已停止")
            
def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='服务管理器')
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'list', 'monitor', 'cleanup'],
                        help='命令: start/stop/restart/list/monitor/cleanup')
    parser.add_argument('--service', type=str, help='服务名称')
    parser.add_argument('--all', action='store_true', help='所有服务')
    parser.add_argument('--interval', type=int, default=5, help='监控刷新间隔(秒)')
    
    args = parser.parse_args()
    
    manager = ServiceManager()
    
    if args.command == 'stop':
        if args.all:
            manager.stop_all_services()
        elif args.service:
            manager.stop_service(args.service)
        else:
            print("请指定 --service 或 --all")
            
    elif args.command == 'list':
        manager.list_services()
        
    elif args.command == 'monitor':
        manager.monitor_services(args.interval)
        
    elif args.command == 'cleanup':
        manager.cleanup_dead_services()
        
    else:
        print(f"未实现的命令: {args.command}")
        
if __name__ == '__main__':
    # 安装psutil（如果未安装）
    try:
        import psutil
    except ImportError:
        print("正在安装psutil...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psutil'])
        import psutil
        
    main()
