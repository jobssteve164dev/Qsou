#!/usr/bin/env python3
"""
测试Celery任务执行
"""

import sys
import os
import time
from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'data-processor'))

def test_celery_task():
    """测试Celery任务执行"""
    print(f"=== Celery任务测试 - {datetime.now()} ===")
    
    try:
        from tasks import launch_crawler
        print("✅ 成功导入launch_crawler任务")
        
        # 提交任务
        print("📤 提交任务到Celery...")
        result = launch_crawler.delay('financial_news')
        print(f"📋 任务ID: {result.id}")
        print(f"📊 初始状态: {result.status}")
        
        # 等待执行
        print("⏳ 等待任务执行...")
        for i in range(15):  # 等待30秒
            time.sleep(2)
            status = result.status
            print(f"⏱️  等待{i*2}秒后状态: {status}")
            
            if result.ready():
                print(f"✅ 任务完成! 结果: {result.result}")
                return True
                
        print("❌ 任务执行超时")
        return False
        
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_celery_task()
    print(f"\n🎯 测试结果: {'成功' if success else '失败'}")
