#!/usr/bin/env python3
"""
爬虫调试脚本
用于测试爬虫任务是否能正常启动和执行
"""

import os
import sys
import time
import subprocess
import json
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_celery_connection():
    """测试Celery连接"""
    print("=== 测试Celery连接 ===")
    try:
        # 添加data-processor目录到路径
        data_processor_path = os.path.join(project_root, 'data-processor')
        if data_processor_path not in sys.path:
            sys.path.insert(0, data_processor_path)
        
        from tasks import app
        inspect = app.control.inspect()
        
        # 检查活跃的worker
        active_workers = inspect.active()
        print(f"活跃的Worker: {active_workers}")
        
        # 检查注册的任务
        registered_tasks = inspect.registered()
        print(f"注册的任务: {registered_tasks}")
        
        # 检查调度任务
        scheduled_tasks = inspect.scheduled()
        print(f"调度的任务: {scheduled_tasks}")
        
        return True
    except Exception as e:
        print(f"Celery连接测试失败: {e}")
        return False

def test_crawler_manual():
    """手动测试爬虫"""
    print("\n=== 手动测试爬虫 ===")
    try:
        # 添加data-processor目录到路径
        data_processor_path = os.path.join(project_root, 'data-processor')
        if data_processor_path not in sys.path:
            sys.path.insert(0, data_processor_path)
        
        from tasks import launch_crawler
        
        # 提交爬虫任务
        result = launch_crawler.delay('financial_news')
        print(f"爬虫任务已提交: {result.id}")
        
        # 等待任务完成
        print("等待任务完成...")
        for i in range(30):  # 最多等待30秒
            status = result.status
            print(f"任务状态: {status}")
            if status in ['SUCCESS', 'FAILURE']:
                break
            time.sleep(1)
        
        if result.ready():
            print(f"任务结果: {result.result}")
        else:
            print("任务超时")
            
        return result.ready()
    except Exception as e:
        print(f"手动测试爬虫失败: {e}")
        return False

def test_scrapy_direct():
    """直接测试Scrapy爬虫"""
    print("\n=== 直接测试Scrapy爬虫 ===")
    try:
        crawler_dir = os.path.join(project_root, 'crawler')
        
        # 检查爬虫目录
        if not os.path.exists(crawler_dir):
            print(f"爬虫目录不存在: {crawler_dir}")
            return False
        
        # 检查爬虫文件
        spider_file = os.path.join(crawler_dir, 'qsou_crawler', 'spiders', 'financial_news_spider.py')
        if not os.path.exists(spider_file):
            print(f"爬虫文件不存在: {spider_file}")
            return False
        
        # 运行爬虫
        cmd = [
            'scrapy', 'crawl', 'financial_news',
            '-L', 'INFO',
            '-s', 'LOG_FILE=logs/test_scrapy.log',
            '-s', 'LOG_ENABLED=1',
            '-s', 'CLOSESPIDER_ITEMCOUNT=5'  # 只爬取5条数据用于测试
        ]
        
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
        print(f"错误输出: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"直接测试Scrapy失败: {e}")
        return False

def check_beat_schedule():
    """检查Beat调度配置"""
    print("\n=== 检查Beat调度配置 ===")
    try:
        # 添加data-processor目录到路径
        data_processor_path = os.path.join(project_root, 'data-processor')
        if data_processor_path not in sys.path:
            sys.path.insert(0, data_processor_path)
        
        from tasks import app
        
        beat_schedule = app.conf.beat_schedule
        print(f"Beat调度配置: {json.dumps(beat_schedule, indent=2, ensure_ascii=False)}")
        
        # 检查是否有爬虫相关的调度
        crawler_tasks = [k for k in beat_schedule.keys() if 'crawl' in k.lower()]
        print(f"爬虫相关调度任务: {crawler_tasks}")
        
        return len(crawler_tasks) > 0
        
    except Exception as e:
        print(f"检查Beat调度配置失败: {e}")
        return False

def main():
    """主函数"""
    print(f"爬虫调试脚本启动 - {datetime.now()}")
    print(f"项目根目录: {project_root}")
    
    # 测试结果
    results = {}
    
    # 1. 测试Celery连接
    results['celery_connection'] = test_celery_connection()
    
    # 2. 检查Beat调度配置
    results['beat_schedule'] = check_beat_schedule()
    
    # 3. 手动测试爬虫
    results['crawler_manual'] = test_crawler_manual()
    
    # 4. 直接测试Scrapy
    results['scrapy_direct'] = test_scrapy_direct()
    
    # 输出总结
    print("\n=== 测试结果总结 ===")
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
    
    # 诊断建议
    print("\n=== 诊断建议 ===")
    if not results['celery_connection']:
        print("- Celery连接失败，检查Redis服务和Worker状态")
    
    if not results['beat_schedule']:
        print("- Beat调度配置缺失，检查tasks.py中的beat_schedule配置")
    
    if not results['crawler_manual']:
        print("- 手动爬虫任务失败，检查任务定义和依赖")
    
    if not results['scrapy_direct']:
        print("- 直接Scrapy测试失败，检查爬虫代码和依赖")

if __name__ == '__main__':
    main()
