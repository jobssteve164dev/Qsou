#!/usr/bin/env python3
"""
爬虫集成测试脚本

测试爬虫与数据处理系统的集成
"""

import os
import sys
import asyncio
import requests
import json
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def test_api_connection():
    """测试API连接"""
    print("🔍 测试API连接...")
    
    try:
        # 测试API网关健康检查
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API网关连接正常")
            return True
        else:
            print(f"❌ API网关响应异常: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ API网关连接失败: {str(e)}")
        return False

def test_data_processing_api():
    """测试数据处理API"""
    print("🔍 测试数据处理API...")
    
    try:
        # 测试数据处理API状态
        response = requests.get("http://localhost:8000/api/v1/process/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print("✅ 数据处理API正常")
            print(f"   Celery连接: {status.get('celery_connected', False)}")
            return True
        else:
            print(f"❌ 数据处理API响应异常: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 数据处理API连接失败: {str(e)}")
        return False

def test_crawler_data_submission():
    """测试爬虫数据提交"""
    print("🔍 测试爬虫数据提交...")
    
    # 创建测试数据
    test_documents = [
        {
            "id": "test_news_001",
            "type": "news",
            "title": "测试财经新闻标题",
            "content": "这是一条测试财经新闻内容，用于验证爬虫与数据处理系统的集成。内容包含投资、股票、市场等关键词。",
            "url": "https://example.com/news/001",
            "source": "test_source",
            "publish_time": datetime.now().isoformat(),
            "author": "测试作者",
            "tags": ["财经", "股票", "投资"],
            "category": "股票",
            "crawl_time": datetime.now().isoformat(),
            "content_length": 50,
            "metadata": {
                "crawler": "test_spider",
                "domain": "example.com",
                "language": "zh-CN"
            }
        },
        {
            "id": "test_announcement_001",
            "type": "announcement",
            "title": "测试公司公告标题",
            "content": "这是一条测试公司公告内容，用于验证爬虫与数据处理系统的集成。内容包含公司、公告、财务等关键词。",
            "url": "https://example.com/announcement/001",
            "source": "test_exchange",
            "exchange": "测试交易所",
            "company_name": "测试公司",
            "stock_code": "000001",
            "announcement_type": "财务报告",
            "publish_time": datetime.now().isoformat(),
            "announcement_id": "TEST001",
            "crawl_time": datetime.now().isoformat(),
            "content_length": 50,
            "is_important": True,
            "metadata": {
                "crawler": "test_spider",
                "domain": "example.com",
                "language": "zh-CN"
            }
        }
    ]
    
    try:
        # 提交测试数据
        payload = {
            "documents": test_documents,
            "source": "test_crawler",
            "batch_id": f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "enable_elasticsearch": True,
            "enable_vector_store": True,
            "enable_nlp_processing": True
        }
        
        response = requests.post(
            "http://localhost:8000/api/v1/process/process",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 爬虫数据提交成功")
            print(f"   处理状态: {result.get('status')}")
            print(f"   处理数量: {result.get('processed_count')}")
            print(f"   失败数量: {result.get('failed_count')}")
            print(f"   批次ID: {result.get('batch_id')}")
            return True
        else:
            print(f"❌ 爬虫数据提交失败: {response.status_code}")
            print(f"   响应内容: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 爬虫数据提交异常: {str(e)}")
        return False

def test_search_functionality():
    """测试搜索功能"""
    print("🔍 测试搜索功能...")
    
    try:
        # 测试搜索API
        search_payload = {
            "query": "测试财经新闻",
            "search_type": "hybrid",
            "page": 1,
            "page_size": 10
        }
        
        response = requests.post(
            "http://localhost:8000/api/v1/search/",
            json=search_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 搜索功能正常")
            print(f"   搜索结果数量: {result.get('total_count', 0)}")
            print(f"   搜索时间: {result.get('search_time_ms', 0)}ms")
            return True
        else:
            print(f"❌ 搜索功能异常: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 搜索功能测试失败: {str(e)}")
        return False

def main():
    """主函数"""
    print("=== 爬虫集成测试 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 测试步骤
    tests = [
        ("API连接测试", test_api_connection),
        ("数据处理API测试", test_data_processing_api),
        ("爬虫数据提交测试", test_crawler_data_submission),
        ("搜索功能测试", test_search_functionality)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"📋 {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {str(e)}")
            results.append((test_name, False))
        print()
    
    # 输出测试结果
    print("=== 测试结果汇总 ===")
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print()
    print(f"总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！爬虫集成正常！")
        return True
    else:
        print("⚠️  部分测试失败，请检查系统配置")
        return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试执行失败: {str(e)}")
        sys.exit(1)
