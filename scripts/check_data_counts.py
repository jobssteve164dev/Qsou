#!/usr/bin/env python3
"""
数据量统计脚本
查询ES和Qdrant中的数据量，分析一致性
"""

import urllib.request
import json
import sys
from datetime import datetime

def query_qdrant():
    """查询Qdrant数据量"""
    try:
        url = "http://127.0.0.1:6333/collections/investment_documents"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        
        result = data['result']
        return {
            'points_count': result.get('points_count', 0),
            'indexed_vectors_count': result.get('indexed_vectors_count', 0),
            'status': result.get('status', 'unknown'),
            'segments_count': result.get('segments_count', 0)
        }
    except Exception as e:
        print(f"Qdrant查询失败: {e}")
        return None

def query_elasticsearch():
    """查询Elasticsearch数据量"""
    try:
        # 查询所有相关索引
        indices = ['qsou_documents*', 'qsou_documents_v1', 'qsoudocuments', 'qsou_general']
        results = {}
        
        for index in indices:
            try:
                url = f"http://127.0.0.1:9200/{index}/_count"
                with urllib.request.urlopen(url, timeout=5) as r:
                    data = json.loads(r.read().decode())
                results[index] = data.get('count', 0)
            except:
                results[index] = 0
        
        return results
    except Exception as e:
        print(f"Elasticsearch查询失败: {e}")
        return None

def query_api_stats():
    """查询后端API统计"""
    try:
        url = "http://127.0.0.1:8888/api/v1/system/stats"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        
        return {
            'documents_count': data.get('documents_count', 0),
            'system_status': data.get('system_status', 'unknown'),
            'services': data.get('services', {})
        }
    except Exception as e:
        print(f"API统计查询失败: {e}")
        return None

def main():
    print("=" * 60)
    print("数据量统计报告")
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 查询Qdrant
    print("\n📊 Qdrant向量数据库:")
    qdrant_data = query_qdrant()
    if qdrant_data:
        print(f"  - 总向量数: {qdrant_data['points_count']:,}")
        print(f"  - 已索引向量数: {qdrant_data['indexed_vectors_count']:,}")
        print(f"  - 状态: {qdrant_data['status']}")
        print(f"  - 段数: {qdrant_data['segments_count']}")
        if qdrant_data['indexed_vectors_count'] == 0:
            print("  ⚠️  向量索引未优化，建议运行优化")
    else:
        print("  ❌ 无法连接到Qdrant")
    
    # 查询Elasticsearch
    print("\n📊 Elasticsearch文档数据库:")
    es_data = query_elasticsearch()
    if es_data:
        total_es_docs = 0
        for index, count in es_data.items():
            if count > 0:
                print(f"  - {index}: {count:,} 文档")
                total_es_docs += count
        print(f"  - 总计: {total_es_docs:,} 文档")
    else:
        print("  ❌ 无法连接到Elasticsearch")
    
    # 查询API统计
    print("\n📊 后端API统计:")
    api_data = query_api_stats()
    if api_data:
        print(f"  - 文档总数: {api_data['documents_count']:,}")
        print(f"  - 系统状态: {api_data['system_status']}")
        services = api_data.get('services', {})
        for service, status in services.items():
            status_icon = "✅" if status else "❌"
            print(f"  - {service}: {status_icon}")
    else:
        print("  ❌ 无法连接到后端API")
    
    # 数据一致性分析
    print("\n🔍 数据一致性分析:")
    if qdrant_data and es_data and api_data:
        qdrant_count = qdrant_data['points_count']
        es_total = sum(count for count in es_data.values())
        api_count = api_data['documents_count']
        
        print(f"  - Qdrant向量数: {qdrant_count:,}")
        print(f"  - ES文档总数: {es_total:,}")
        print(f"  - API统计数: {api_count:,}")
        
        # 分析一致性
        if qdrant_count == es_total == api_count:
            print("  ✅ 数据完全一致！")
        else:
            print("  ⚠️  数据存在差异:")
            if abs(qdrant_count - es_total) > 0:
                print(f"    - Qdrant与ES差异: {abs(qdrant_count - es_total):,}")
            if abs(api_count - es_total) > 0:
                print(f"    - API与ES差异: {abs(api_count - es_total):,}")
            
            # 建议
            if qdrant_count > es_total:
                print("  💡 建议: 执行回填脚本将Qdrant数据同步到ES")
            elif es_total > qdrant_count:
                print("  💡 建议: 检查向量化任务是否正常运行")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
