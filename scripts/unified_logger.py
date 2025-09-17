#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志收集器 - 轻量级、跨平台、高效
使用Python实现，避免shell进程管理问题
"""

import os
import sys
import time
import json
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import signal
import argparse

# Windows环境设置UTF-8编码
if sys.platform == 'win32':
    import locale
    # 设置输出编码为UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class UnifiedLogCollector:
    """统一日志收集器"""
    
    def __init__(self, 
                 log_dir: str = "logs",
                 output_file: str = "logs/unified.log",
                 max_lines: int = 50000,
                 check_interval: int = 1,
                 rotation_ratio: float = 0.8):
        """
        初始化日志收集器
        
        Args:
            log_dir: 日志目录
            output_file: 输出的统一日志文件
            max_lines: 最大行数
            check_interval: 检查间隔(秒)
            rotation_ratio: 轮转时保留的比例
        """
        self.log_dir = Path(log_dir)
        self.output_file = Path(output_file)
        self.max_lines = max_lines
        self.check_interval = check_interval
        self.rotation_ratio = rotation_ratio
        
        # 文件位置记录（避免重复读取）
        self.file_positions: Dict[Path, int] = {}
        
        # 日志队列
        self.log_queue = queue.Queue()
        
        # 运行标志
        self.running = False
        
        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 要监控的日志文件模式
        self.log_patterns = [
            "api.log",
            "frontend.log", 
            "celery-worker.log",
            "celery-flower.log",
            "elasticsearch.log",
            "qdrant.log",
            "redis.log"
        ]
        
    def start(self):
        """启动日志收集器"""
        self.running = True
        
        # 清理旧日志
        self._clean_unified_log()
        
        # 启动写入线程
        writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
        writer_thread.start()
        
        # 启动收集线程
        collector_thread = threading.Thread(target=self._collector_worker, daemon=True)
        collector_thread.start()
        
        print(f"✓ 统一日志收集器已启动")
        print(f"  - 输出文件: {self.output_file}")
        print(f"  - 最大行数: {self.max_lines}")
        print(f"  - 检查间隔: {self.check_interval}秒")
        print(f"  - 监控目录: {self.log_dir}")
        print(f"  - 按 Ctrl+C 停止")
        print()
        
        # 等待信号
        try:
            while self.running:
                time.sleep(1)
                # 定期输出状态
                if int(time.time()) % 30 == 0:
                    self._print_status()
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """停止日志收集器"""
        print("\n正在停止日志收集器...")
        self.running = False
        # 等待线程结束，但不要等太久
        max_wait = 5
        waited = 0
        while waited < max_wait and (threading.active_count() > 1):
            time.sleep(0.5)
            waited += 0.5
        print("✓ 日志收集器已停止")
        # 确保进程退出
        sys.exit(0)
        
    def _collector_worker(self):
        """收集日志的工作线程"""
        while self.running:
            try:
                # 查找所有匹配的日志文件
                for pattern in self.log_patterns:
                    log_file = self.log_dir / pattern
                    if log_file.exists():
                        self._collect_from_file(log_file)
                        
                # 也收集其他.log文件（排除unified.log）
                for log_file in self.log_dir.glob("*.log"):
                    # 比较绝对路径，避免路径差异导致的问题
                    if log_file.resolve() != self.output_file.resolve() and log_file.name != 'unified.log':
                        self._collect_from_file(log_file)
                        
            except Exception as e:
                print(f"收集错误: {e}")
                
            time.sleep(self.check_interval)
            
    def _collect_from_file(self, file_path: Path):
        """从单个文件收集日志"""
        try:
            # 跳过统一日志文件本身，避免递归
            if file_path.name == 'unified.log':
                return
                
            # 获取服务名
            service_name = file_path.stem
            
            # 获取上次读取位置
            last_position = self.file_positions.get(file_path, 0)
            
            # 获取当前文件大小
            current_size = file_path.stat().st_size
            
            # 如果文件变小了，说明被轮转了
            if current_size < last_position:
                last_position = 0
                
            # 如果有新内容
            if current_size > last_position:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_position)
                    
                    # 读取新行
                    for line in f:
                        line = line.strip()
                        if line:
                            # 添加时间戳和服务标识
                            log_entry = {
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'service': service_name,
                                'message': line
                            }
                            self.log_queue.put(log_entry)
                            
                    # 更新位置
                    self.file_positions[file_path] = f.tell()
                    
        except Exception as e:
            # 忽略单个文件的错误
            pass
            
    def _writer_worker(self):
        """写入日志的工作线程"""
        buffer = []
        last_flush = time.time()
        
        while self.running or not self.log_queue.empty():
            try:
                # 批量获取日志
                deadline = time.time() + 0.1
                while time.time() < deadline and len(buffer) < 100:
                    try:
                        entry = self.log_queue.get(timeout=0.1)
                        buffer.append(entry)
                    except queue.Empty:
                        break
                        
                # 定期写入或缓冲区满
                if buffer and (len(buffer) >= 100 or time.time() - last_flush > 1):
                    self._write_logs(buffer)
                    buffer.clear()
                    last_flush = time.time()
                    
                # 检查是否需要轮转
                if self.output_file.exists():
                    line_count = self._count_lines(self.output_file)
                    if line_count > self.max_lines:
                        self._rotate_log()
                        
            except Exception as e:
                print(f"写入错误: {e}")
                
    def _write_logs(self, entries: List[dict]):
        """批量写入日志"""
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                for entry in entries:
                    line = f"[{entry['timestamp']}] [{entry['service']}] {entry['message']}\n"
                    f.write(line)
        except Exception as e:
            print(f"写入失败: {e}")
            
    def _rotate_log(self):
        """轮转日志文件"""
        try:
            if not self.output_file.exists():
                return
                
            # 读取所有行
            with open(self.output_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # 保留一定比例的行
            keep_lines = int(self.max_lines * self.rotation_ratio)
            if len(lines) > keep_lines:
                lines = lines[-keep_lines:]
                
            # 写回文件
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SYSTEM] 日志已轮转\n")
                
        except Exception as e:
            print(f"轮转失败: {e}")
            
    def _clean_unified_log(self):
        """清理统一日志文件"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SYSTEM] ========== 日志收集器启动 ==========\n")
        except Exception as e:
            print(f"清理日志失败: {e}")
            
    def _count_lines(self, file_path: Path) -> int:
        """快速计算文件行数"""
        try:
            with open(file_path, 'rb') as f:
                return sum(1 for _ in f)
        except:
            return 0
            
    def _print_status(self):
        """打印状态信息"""
        try:
            if self.output_file.exists():
                line_count = self._count_lines(self.output_file)
                file_size = self.output_file.stat().st_size / 1024 / 1024  # MB
                queue_size = self.log_queue.qsize()
                
                status = f"[状态] 行数: {line_count}/{self.max_lines} | 大小: {file_size:.2f}MB | 队列: {queue_size}"
                print(f"\r{status}", end='', flush=True)
        except:
            pass
            
class LogSearcher:
    """日志搜索工具"""
    
    @staticmethod
    def search(log_file: str, pattern: str, service: Optional[str] = None, level: Optional[str] = None):
        """搜索日志"""
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # 服务过滤
                    if service and f"[{service}]" not in line:
                        continue
                        
                    # 级别过滤
                    if level:
                        level_patterns = {
                            'ERROR': ['ERROR', 'EXCEPTION', 'FAILED', 'FATAL'],
                            'WARN': ['WARN', 'WARNING'],
                            'INFO': ['INFO'],
                            'DEBUG': ['DEBUG', 'TRACE']
                        }
                        if not any(p in line.upper() for p in level_patterns.get(level.upper(), [])):
                            continue
                            
                    # 模式匹配
                    if pattern.lower() in line.lower():
                        print(line.strip())
                        
        except Exception as e:
            print(f"搜索失败: {e}")
            
def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='统一日志收集器')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--output', type=str, default='logs/unified.log', help='输出文件')
    parser.add_argument('--max-lines', type=int, default=50000, help='最大行数')
    parser.add_argument('--interval', type=int, default=1, help='检查间隔(秒)')
    parser.add_argument('--search', type=str, help='搜索模式')
    parser.add_argument('--service', type=str, help='服务名过滤')
    parser.add_argument('--level', type=str, help='日志级别过滤')
    
    args = parser.parse_args()
    
    # 如果是搜索模式
    if args.search:
        LogSearcher.search(args.output, args.search, args.service, args.level)
        return
        
    # 加载配置
    config = {}
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass
            
    # 创建收集器
    collector = UnifiedLogCollector(
        output_file=args.output,
        max_lines=config.get('max_lines', args.max_lines),
        check_interval=config.get('interval', args.interval)
    )
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print(f"\n收到信号 {sig}，正在停止...")
        collector.stop()
        
    # 注册多种信号处理
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    if sys.platform == 'win32':
        # Windows特定的信号
        signal.signal(signal.SIGBREAK, signal_handler)  # Ctrl+Break
        # 注册控制台关闭处理器
        import atexit
        atexit.register(lambda: collector.stop() if collector.running else None)
        
    # 启动收集器
    collector.start()
    
if __name__ == '__main__':
    main()
