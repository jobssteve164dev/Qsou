"""
Celery配置文件
"""
import os
import sys

# Broker配置
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

# 序列化配置
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'Asia/Shanghai'
enable_utc = True

# Worker配置
worker_concurrency = int(os.getenv('CELERY_WORKERS', 4))
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 50  # 防止内存泄漏

# Windows特定配置
if sys.platform == 'win32':
    # Windows上使用solo池而不是prefork池，避免权限问题
    worker_pool = 'solo'
    # 或者使用threads池
    # worker_pool = 'threads'
    
    # 减少并发数
    worker_concurrency = 1
    
    # 禁用某些可能导致问题的优化
    worker_disable_rate_limits = True
    task_always_eager = False
else:
    # Linux/Mac使用prefork池
    worker_pool = 'prefork'

# 任务配置
task_soft_time_limit = 300  # 5分钟软超时
task_time_limit = 600  # 10分钟硬超时
task_acks_late = True
task_reject_on_worker_lost = True

# 任务路由
task_routes = {
    'tasks.process_crawled_data': {'queue': 'data_processing'},
    'tasks.generate_embeddings': {'queue': 'ml_processing'},
    'tasks.update_search_index': {'queue': 'indexing'},
    'tasks.analyze_intelligence': {'queue': 'analysis'},
}

# 任务优先级
task_inherit_parent_priority = True
task_default_priority = 5
task_default_queue = 'celery'

# 结果后端配置
result_expires = 3600  # 结果过期时间（秒）
result_persistent = True
result_compression = 'gzip'

# 日志配置
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# 监控配置
worker_send_task_events = True
task_send_sent_event = True

# Beat调度器配置（如果使用）
beat_schedule = {
    'cleanup-expired-results': {
        'task': 'tasks.cleanup_expired_results',
        'schedule': 3600.0,  # 每小时执行一次
    },
    'health-check': {
        'task': 'tasks.health_check',
        'schedule': 60.0,  # 每分钟执行一次
    },
}

# 连接池配置
broker_pool_limit = 10
broker_connection_retry = True
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10

# 消息确认配置
task_track_started = True
task_publish_retry = True
task_publish_retry_policy = {
    'max_retries': 3,
    'interval_start': 0,
    'interval_step': 0.2,
    'interval_max': 0.2,
}
