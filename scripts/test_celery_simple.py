#!/usr/bin/env python3
"""
简单测试Celery任务执行
"""

import sys
import os
import time
from datetime import datetime

# 添加data-processor到路径
sys.path.insert(0, os.getcwd())

print(f"=== 测试Celery任务执行 - {datetime.now()} ===")

try:
    from tasks import launch_crawler
    print("成功导入launch_crawler任务")
    
    # 手动提交任务
    print("提交任务到Celery...")
    result = launch_crawler.delay('financial_news')
    print(f"任务ID: {result.id}")
    print(f"初始状态: {result.status}")
    
    # 等待任务执行
    print("等待任务执行...")
    for i in range(10):  # 等待20秒
        time.sleep(2)
        status = result.status
        print(f"等待{i*2}秒后状态: {status}")
        
        if result.ready():
            print(f"任务完成! 结果: {result.result}")
            break
    else:
        print("任务执行超时")
        
except Exception as e:
    print(f"任务执行失败: {e}")
    import traceback
    traceback.print_exc()
