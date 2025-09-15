#!/usr/bin/env python3
"""
服务状态检查脚本
检查所有关键服务的运行状态
"""

import requests
import psycopg2
import redis
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()


def check_service_status():
    """检查所有服务状态"""
    print("📊 服务状态检查报告")
    print("=" * 40)
    
    services_status = {}
    
    # 检查 PostgreSQL
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="qsou_investment_intel",
            user="qsou",
            password="your_password"
        )
        conn.close()
        services_status['PostgreSQL'] = '✅ 运行中'
    except:
        services_status['PostgreSQL'] = '❌ 离线'
    
    # 检查 Redis
    try:
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        services_status['Redis'] = '✅ 运行中'
    except:
        services_status['Redis'] = '❌ 离线'
    
    # 检查 Elasticsearch
    try:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        if es.ping():
            info = es.info()
            services_status['Elasticsearch'] = f"✅ 运行中 ({info['version']['number']})"
        else:
            services_status['Elasticsearch'] = '❌ 离线'
    except:
        services_status['Elasticsearch'] = '❌ 离线'
    
    # 检查 Qdrant
    try:
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()
        services_status['Qdrant'] = f"✅ 运行中 ({len(collections.collections)} 个集合)"
    except:
        services_status['Qdrant'] = '❌ 离线'
    
    # 检查 API 服务
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            services_status['API 服务'] = '✅ 运行中'
        else:
            services_status['API 服务'] = f"⚠️  响应异常 ({response.status_code})"
    except:
        services_status['API 服务'] = '❌ 离线'
    
    # 检查前端服务
    try:
        response = requests.get('http://localhost:3000', timeout=5)
        if response.status_code == 200:
            services_status['前端服务'] = '✅ 运行中'
        else:
            services_status['前端服务'] = f"⚠️  响应异常 ({response.status_code})"
    except:
        services_status['前端服务'] = '❌ 离线'
    
    # 输出结果
    for service, status in services_status.items():
        print(f"{service:<15} {status}")
    
    print("=" * 40)
    
    # 统计
    online_count = sum(1 for status in services_status.values() if '✅' in status)
    total_count = len(services_status)
    print(f"服务状态: {online_count}/{total_count} 在线")
    
    return services_status


if __name__ == "__main__":
    check_service_status()
