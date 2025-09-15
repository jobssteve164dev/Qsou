#!/usr/bin/env python3
"""
验证本地开发环境安装脚本
检查所有必需的服务是否正常运行
"""

import sys
import time
import json
import requests
import psycopg2
import redis
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException


def print_status(service_name, status, message=""):
    """打印服务状态"""
    status_symbol = "✅" if status else "❌"
    print(f"{status_symbol} {service_name}: {message}")
    return status


def test_postgresql():
    """测试 PostgreSQL 连接"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",  # 连接默认数据库
            user="postgres"
        )
        conn.close()
        return print_status("PostgreSQL", True, "连接成功")
    except psycopg2.Error as e:
        return print_status("PostgreSQL", False, f"连接失败: {e}")


def test_redis():
    """测试 Redis 连接"""
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        return print_status("Redis", True, "连接成功")
    except redis.RedisError as e:
        return print_status("Redis", False, f"连接失败: {e}")


def test_elasticsearch():
    """测试 Elasticsearch 连接"""
    try:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
        info = es.info()
        version = info['version']['number']
        return print_status("Elasticsearch", True, f"连接成功 (版本: {version})")
    except Exception as e:
        return print_status("Elasticsearch", False, f"连接失败: {e}")


def test_qdrant():
    """测试 Qdrant 连接"""
    try:
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()
        return print_status("Qdrant", True, "连接成功")
    except ResponseHandlingException as e:
        return print_status("Qdrant", False, f"连接失败: {e}")
    except Exception as e:
        return print_status("Qdrant", False, f"连接失败: {e}")


def test_python_packages():
    """测试 Python 包导入"""
    packages = [
        ('fastapi', 'FastAPI'),
        ('scrapy', 'Scrapy'),
        ('celery', 'Celery'),
        ('torch', 'PyTorch'),
        ('transformers', 'Transformers'),
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy')
    ]
    
    all_success = True
    for package, display_name in packages:
        try:
            __import__(package)
            print_status(f"Python包: {display_name}", True, "导入成功")
        except ImportError:
            print_status(f"Python包: {display_name}", False, "导入失败")
            all_success = False
    
    return all_success


def test_java():
    """测试 Java 环境"""
    import subprocess
    try:
        result = subprocess.run(
            ['java', '-version'], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            version_line = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
            return print_status("Java", True, version_line)
        else:
            return print_status("Java", False, "未找到 Java")
    except FileNotFoundError:
        return print_status("Java", False, "未安装 Java")


def test_nodejs():
    """测试 Node.js 环境"""
    import subprocess
    try:
        result = subprocess.run(
            ['node', '--version'], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return print_status("Node.js", True, f"版本: {version}")
        else:
            return print_status("Node.js", False, "版本检查失败")
    except FileNotFoundError:
        return print_status("Node.js", False, "未安装 Node.js")


def main():
    """主函数"""
    print("🔍 开始验证 Qsou 投资情报搜索引擎开发环境...")
    print("=" * 60)
    
    # 基础环境检查
    print("\n📋 基础环境检查:")
    java_ok = test_java()
    python_ok = test_python_packages()
    nodejs_ok = test_nodejs()
    
    # 服务连接检查
    print("\n🔌 服务连接检查:")
    postgresql_ok = test_postgresql()
    redis_ok = test_redis()
    elasticsearch_ok = test_elasticsearch()
    qdrant_ok = test_qdrant()
    
    print("\n" + "=" * 60)
    
    # 总结结果
    all_services = [java_ok, python_ok, nodejs_ok, postgresql_ok, redis_ok, elasticsearch_ok, qdrant_ok]
    success_count = sum(all_services)
    total_count = len(all_services)
    
    if success_count == total_count:
        print("🎉 所有服务验证通过！开发环境已准备就绪。")
        print("\n🚀 下一步操作:")
        print("1. 运行 'python scripts/init_database.py' 初始化数据库")
        print("2. 运行 'python scripts/init_elasticsearch.py' 创建搜索索引")
        print("3. 开始开发！")
        return True
    else:
        failed_count = total_count - success_count
        print(f"⚠️  {failed_count} 个服务验证失败，请检查安装配置。")
        print("\n📖 请参考 'docs/local-development-setup.md' 获取详细安装指南。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
