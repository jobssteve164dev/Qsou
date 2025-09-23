#!/usr/bin/env python3
"""
简单回填脚本 - 使用HTTP API
"""

import urllib.request
import json
import time

def get_qdrant_points(limit=100, offset=0):
    """获取Qdrant点数据"""
    try:
        url = "http://127.0.0.1:6333/collections/investment_documents/points/scroll"
        payload = {
            "limit": limit,
            "offset": offset,
            "with_payload": True,
            "with_vector": False
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as r:
            response = json.loads(r.read().decode())
        
        return response.get('result', {}).get('points', [])
    except Exception as e:
        print(f"获取Qdrant数据失败: {e}")
        return []

def check_es_exists(doc_id):
    """检查ES文档是否存在"""
    try:
        url = f"http://127.0.0.1:9200/qsou_documents_v1/_doc/{doc_id}"
        req = urllib.request.Request(url)
        req.get_method = lambda: 'HEAD'
        
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except:
        return False

def index_to_es(doc_id, document):
    """索引到ES"""
    try:
        url = f"http://127.0.0.1:9200/qsou_documents_v1/_doc/{doc_id}"
        data = json.dumps(document).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        req.get_method = lambda: 'PUT'
        
        with urllib.request.urlopen(req, timeout=10) as r:
            response = json.loads(r.read().decode())
            return response.get('result') in ['created', 'updated']
    except Exception as e:
        print(f"索引失败 {doc_id}: {e}")
        return False

def main():
    print("🔄 简单回填脚本")
    print("=" * 40)
    
    # 获取统计
    try:
        qd_url = "http://127.0.0.1:6333/collections/investment_documents"
        with urllib.request.urlopen(qd_url, timeout=5) as r:
            qd_data = json.loads(r.read().decode())
        qd_count = qd_data['result']['points_count']
        
        es_url = "http://127.0.0.1:9200/qsou_documents_v1/_count"
        with urllib.request.urlopen(es_url, timeout=5) as r:
            es_data = json.loads(r.read().decode())
        es_count = es_data['count']
        
        print(f"Qdrant向量数: {qd_count}")
        print(f"ES文档数: {es_count}")
        print(f"需要同步: {qd_count - es_count}")
        
        if qd_count <= es_count:
            print("✅ 数据已同步")
            return
            
    except Exception as e:
        print(f"获取统计失败: {e}")
        return
    
    # 开始同步
    print("\n🚀 开始同步...")
    
    stats = {'success': 0, 'failed': 0, 'skipped': 0}
    batch_size = 100
    offset = 0
    
    while offset < qd_count:
        print(f"📦 处理批次: {offset + 1} - {min(offset + batch_size, qd_count)}")
        
        points = get_qdrant_points(limit=batch_size, offset=offset)
        if not points:
            break
        
        for point in points:
            try:
                doc_id = str(point.get('id', ''))
                payload = point.get('payload', {})
                
                if not doc_id or not payload:
                    stats['failed'] += 1
                    continue
                
                # 检查是否已存在
                if check_es_exists(doc_id):
                    stats['skipped'] += 1
                    continue
                
                # 准备文档
                es_doc = {
                    'id': doc_id,
                    'title': payload.get('title', ''),
                    'content': payload.get('content', ''),
                    'summary': payload.get('summary', ''),
                    'source': payload.get('source', ''),
                    'url': payload.get('url', ''),
                    'timestamp': payload.get('timestamp', ''),
                    'category': payload.get('category', 'general'),
                    'tags': payload.get('tags', []),
                    'quality_score': payload.get('quality_score', 0.0),
                    'sentiment': payload.get('sentiment', {}),
                    'entities': payload.get('entities', []),
                    'keywords': payload.get('keywords', [])
                }
                
                # 索引到ES
                if index_to_es(doc_id, es_doc):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                print(f"处理点失败: {e}")
                stats['failed'] += 1
        
        print(f"  ✅ 成功: {stats['success']}, ❌ 失败: {stats['failed']}, ⏭️  跳过: {stats['skipped']}")
        
        offset += len(points)
        time.sleep(0.1)
    
    # 最终统计
    print(f"\n📊 同步完成:")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    print(f"  跳过: {stats['skipped']}")
    
    # 验证
    try:
        with urllib.request.urlopen(es_url, timeout=5) as r:
            new_es_data = json.loads(r.read().decode())
        new_es_count = new_es_data['count']
        
        print(f"\n📈 最终统计:")
        print(f"  Qdrant: {qd_count}")
        print(f"  ES: {new_es_count}")
        
        if qd_count == new_es_count:
            print("  ✅ 数据完全一致！")
        else:
            print(f"  ⚠️  仍有差异: {qd_count - new_es_count}")
            
    except Exception as e:
        print(f"验证失败: {e}")

if __name__ == "__main__":
    main()
