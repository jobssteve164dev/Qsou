#!/usr/bin/env python3
"""
Celery任务调度和执行测试脚本

测试内容：
1. Celery Worker连接状态
2. Celery Beat调度器状态
3. 任务队列状态
4. 手动触发任务执行
5. 定时任务调度验证
"""

import sys
import os
import time
import subprocess
from datetime import datetime, timedelta

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'data-processor'))

def log_info(message):
    """打印信息日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] {message}")

def log_error(message):
    """打印错误日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {message}")

def log_success(message):
    """打印成功日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] {message}")

def log_warning(message):
    """打印警告日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WARNING] {message}")

def test_celery_worker_connection():
    """测试Celery Worker连接"""
    log_info("测试Celery Worker连接...")
    
    try:
        from celery import Celery
        from tasks import app
        
        # 检查worker状态
        inspect = app.control.inspect()
        
        # 尝试多种检查方法
        stats = inspect.stats()
        active = inspect.active()
        scheduled = inspect.scheduled()
        reserved = inspect.reserved()
        
        if stats:
            log_success(f"Celery Worker连接成功，发现 {len(stats)} 个worker")
            for worker_name, worker_stats in stats.items():
                log_info(f"  - Worker: {worker_name}")
                log_info(f"    池类型: {worker_stats.get('pool', {}).get('implementation', 'unknown')}")
                log_info(f"    并发数: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')}")
        else:
            log_warning("未发现任何Celery Worker")
            
            # 尝试ping检查
            log_info("尝试ping检查...")
            ping_result = inspect.ping()
            if ping_result:
                log_success(f"Worker响应ping: {list(ping_result.keys())}")
                return True
            else:
                log_error("Worker未响应ping")
                return False
            
        return True
        
    except Exception as e:
        log_error(f"Celery Worker连接测试失败: {e}")
        return False

def test_celery_beat_scheduler():
    """测试Celery Beat调度器"""
    log_info("测试Celery Beat调度器...")
    
    try:
        from tasks import app
        
        # 检查调度器状态
        inspect = app.control.inspect()
        scheduled = inspect.scheduled()
        active = inspect.active()
        reserved = inspect.reserved()
        
        log_info("调度器状态检查:")
        if scheduled:
            log_success(f"发现 {len(scheduled)} 个worker的调度任务")
            for worker, tasks in scheduled.items():
                log_info(f"  - Worker {worker}: {len(tasks)} 个调度任务")
        else:
            log_warning("未发现调度任务")
            
        if active:
            log_info(f"发现 {len(active)} 个worker的活跃任务")
            for worker, tasks in active.items():
                log_info(f"  - Worker {worker}: {len(tasks)} 个活跃任务")
        else:
            log_info("当前无活跃任务")
            
        if reserved:
            log_info(f"发现 {len(reserved)} 个worker的保留任务")
            for worker, tasks in reserved.items():
                log_info(f"  - Worker {worker}: {len(tasks)} 个保留任务")
        else:
            log_info("当前无保留任务")
            
        return True
        
    except Exception as e:
        log_error(f"Celery Beat调度器测试失败: {e}")
        return False

def test_task_registration():
    """测试任务注册"""
    log_info("测试任务注册...")
    
    try:
        from tasks import app
        
        # 获取注册的任务
        registered_tasks = list(app.tasks.keys())
        
        log_info(f"已注册的任务数量: {len(registered_tasks)}")
        
        # 检查关键任务
        key_tasks = [
            'tasks.launch_crawler',
            'tasks.process_crawled_data',
            'tasks.analyze_intelligence',
            'tasks.health_check'
        ]
        
        for task_name in key_tasks:
            if task_name in registered_tasks:
                log_success(f"✓ 任务已注册: {task_name}")
            else:
                log_error(f"✗ 任务未注册: {task_name}")
                
        return True
        
    except Exception as e:
        log_error(f"任务注册测试失败: {e}")
        return False

def test_manual_task_execution():
    """测试手动任务执行"""
    log_info("测试手动任务执行...")
    
    try:
        from tasks import launch_crawler
        
        # 提交一个测试任务
        log_info("提交测试任务: launch_crawler('financial_news')")
        result = launch_crawler.delay('financial_news')
        
        log_info(f"任务ID: {result.id}")
        log_info(f"初始状态: {result.status}")
        
        # 等待任务执行
        log_info("等待任务执行...")
        timeout = 30
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = result.status
            log_info(f"任务状态: {status}")
            
            if result.ready():
                if result.successful():
                    log_success(f"任务执行成功! 结果: {result.result}")
                else:
                    log_error(f"任务执行失败: {result.result}")
                break
                
            time.sleep(2)
        else:
            log_warning("任务执行超时")
            
        return result.ready() and result.successful()
        
    except Exception as e:
        log_error(f"手动任务执行测试失败: {e}")
        return False

def test_beat_schedule_configuration():
    """测试Beat调度配置"""
    log_info("测试Beat调度配置...")
    
    try:
        from tasks import app
        
        # 从Celery应用获取beat_schedule配置
        beat_schedule = app.conf.beat_schedule
        
        log_info(f"调度配置数量: {len(beat_schedule)}")
        
        # 检查关键调度任务
        key_schedules = [
            'crawl-financial-news-every-15m',
            'crawl-company-announcement-every-30m'
        ]
        
        for schedule_name in key_schedules:
            if schedule_name in beat_schedule:
                schedule_config = beat_schedule[schedule_name]
                log_success(f"✓ 调度任务已配置: {schedule_name}")
                log_info(f"  任务: {schedule_config['task']}")
                log_info(f"  调度: {schedule_config['schedule']}")
                log_info(f"  参数: {schedule_config.get('args', [])}")
            else:
                log_error(f"✗ 调度任务未配置: {schedule_name}")
                
        return True
        
    except Exception as e:
        log_error(f"Beat调度配置测试失败: {e}")
        return False

def test_redis_connection():
    """测试Redis连接"""
    log_info("测试Redis连接...")
    
    try:
        import redis
        
        # 连接到Redis
        r = redis.Redis(host='localhost', port=6379, db=1)
        
        # 测试连接
        r.ping()
        log_success("Redis连接成功")
        
        # 检查队列状态
        queue_length = r.llen('celery')
        log_info(f"Celery队列长度: {queue_length}")
        
        # 检查结果后端
        r_results = redis.Redis(host='localhost', port=6379, db=2)
        r_results.ping()
        log_success("Redis结果后端连接成功")
        
        return True
        
    except Exception as e:
        log_error(f"Redis连接测试失败: {e}")
        return False

def test_scrapy_availability():
    """测试Scrapy可用性"""
    log_info("测试Scrapy可用性...")
    
    try:
        import scrapy
        log_success(f"Scrapy版本: {scrapy.__version__}")
        
        # 测试scrapy命令
        crawler_dir = os.path.join(project_root, 'crawler')
        python_exe = os.path.join(project_root, 'api-gateway', '.venv', 'Scripts', 'python.exe')
        
        if os.path.exists(python_exe):
            result = subprocess.run([
                python_exe, '-m', 'scrapy', 'crawl', 'financial_news',
                '-L', 'INFO', '-s', 'CLOSESPIDER_ITEMCOUNT=1'
            ], cwd=crawler_dir, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                log_success("Scrapy命令执行成功")
            else:
                log_warning(f"Scrapy命令执行返回码: {result.returncode}")
                if result.stderr:
                    log_warning(f"错误输出: {result.stderr[:200]}...")
        else:
            log_error(f"Python可执行文件不存在: {python_exe}")
            return False
            
        return True
        
    except Exception as e:
        log_error(f"Scrapy可用性测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("Celery任务调度和执行测试")
    print("=" * 60)
    print()
    
    tests = [
        ("Redis连接", test_redis_connection),
        ("Celery Worker连接", test_celery_worker_connection),
        ("任务注册", test_task_registration),
        ("Beat调度配置", test_beat_schedule_configuration),
        ("Celery Beat调度器", test_celery_beat_scheduler),
        ("Scrapy可用性", test_scrapy_availability),
        ("手动任务执行", test_manual_task_execution),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            log_error(f"测试 {test_name} 发生异常: {e}")
            results[test_name] = False
        print()
    
    # 输出测试结果摘要
    print("=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:20} : {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        log_success("所有测试通过！")
    else:
        log_warning(f"有 {total - passed} 个测试失败")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
