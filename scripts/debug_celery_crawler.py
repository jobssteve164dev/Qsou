#!/usr/bin/env python3
"""
调试Celery爬虫任务执行情况
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'data-processor'))

def test_celery_connection():
    """测试Celery连接"""
    print("=== 测试Celery连接 ===")
    try:
        from tasks import app
        inspect = app.control.inspect()
        
        # 检查活跃的worker
        active_workers = inspect.active()
        print(f"活跃的Worker: {active_workers}")
        
        # 检查注册的任务
        registered_tasks = inspect.registered()
        print(f"注册的任务: {registered_tasks}")
        
        return True
    except Exception as e:
        print(f"Celery连接失败: {e}")
        return False

def test_manual_task():
    """手动测试任务执行"""
    print("\n=== 手动测试任务执行 ===")
    try:
        from tasks import launch_crawler
        
        print("提交爬虫任务...")
        result = launch_crawler.delay('financial_news')
        print(f"任务ID: {result.id}")
        
        # 等待任务完成
        print("等待任务完成...")
        for i in range(30):  # 最多等待30秒
            status = result.status
            print(f"状态: {status}")
            
            if result.ready():
                print(f"任务完成! 结果: {result.result}")
                return True
            
            time.sleep(1)
        
        print("任务超时")
        return False
        
    except Exception as e:
        print(f"任务执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_scrapy():
    """直接测试Scrapy命令"""
    print("\n=== 直接测试Scrapy命令 ===")
    try:
        crawler_dir = os.path.join(project_root, 'crawler')
        cmd = ['scrapy', 'crawl', 'financial_news', '-L', 'INFO', '-s', 'CLOSESPIDER_ITEMCOUNT=1']
        
        print(f"执行命令: {' '.join(cmd)}")
        print(f"工作目录: {crawler_dir}")
        
        result = subprocess.run(
            cmd,
            cwd=crawler_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(f"返回码: {result.returncode}")
        print(f"标准输出: {result.stdout}")
        print(f"标准错误: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Scrapy命令执行失败: {e}")
        return False

def check_logs():
    """检查日志文件"""
    print("\n=== 检查日志文件 ===")
    
    log_files = [
        'logs/celery-worker.log',
        'logs/celery-beat.log',
        'crawler/logs/scrapy.log'
    ]
    
    for log_file in log_files:
        log_path = os.path.join(project_root, log_file)
        if os.path.exists(log_path):
            print(f"\n{log_file} 最后修改时间: {datetime.fromtimestamp(os.path.getmtime(log_path))}")
            print(f"文件大小: {os.path.getsize(log_path)} 字节")
            
            # 显示最后几行
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"最后5行:")
                    for line in lines[-5:]:
                        print(f"  {line.strip()}")
            except Exception as e:
                print(f"读取日志失败: {e}")
        else:
            print(f"{log_file} 不存在")

if __name__ == "__main__":
    print(f"调试时间: {datetime.now()}")
    print(f"项目根目录: {project_root}")
    
    # 测试步骤
    steps = [
        ("Celery连接", test_celery_connection),
        ("直接Scrapy", test_direct_scrapy),
        ("手动任务", test_manual_task),
        ("日志检查", check_logs)
    ]
    
    results = {}
    for step_name, step_func in steps:
        print(f"\n{'='*50}")
        print(f"执行步骤: {step_name}")
        print('='*50)
        
        try:
            result = step_func()
            results[step_name] = result
            print(f"结果: {'成功' if result else '失败'}")
        except Exception as e:
            print(f"步骤执行异常: {e}")
            results[step_name] = False
    
    # 总结
    print(f"\n{'='*50}")
    print("调试总结")
    print('='*50)
    for step_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{step_name}: {status}")
