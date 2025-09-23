#!/usr/bin/env python3
"""
简化版Qdrant到ES回填脚本
使用HTTP API，不依赖Python客户端包
"""

import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

def get_qdrant_count():
    """获取Qdrant向量数量"""
    try:
        url = "http://127.0.0.1:6333/collections/investment_documents"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        return data['result']['points_count']
    except Exception as e:
        print(f"获取Qdrant数量失败: {e}")
        return 0

def get_es_count():
    """获取ES文档数量"""
    try:
        url = "http://127.0.0.1:9200/qsou_documents_v1/_count"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        return data['count']
    except Exception as e:
        print(f"获取ES数量失败: {e}")
        return 0

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
        print(f"获取Qdrant点数据失败: {e}")
        return []

def check_es_document_exists(doc_id):
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
    """索引文档到ES"""
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
            return response.get('result') == 'created' or response.get('result') == 'updated'
    except Exception as e:
        print(f"索引到ES失败 {doc_id}: {e}")
        return False

def prepare_es_document(point):
    """准备ES文档"""
    try:
        payload = point.get('payload', {})
        doc_id = str(point.get('id', ''))
        
        if not doc_id or not payload:
            return None, None
        
        es_doc = {
            'id': doc_id,
            'title': payload.get('title', ''),
            'content': payload.get('content', ''),
            'summary': payload.get('summary', ''),
            'source': payload.get('source', ''),
            'url': payload.get('url', ''),
            'timestamp': payload.get('timestamp', datetime.now().isoformat()),
            'category': payload.get('category', 'general'),
            'tags': payload.get('tags', []),
            'quality_score': payload.get('quality_score', 0.0),
            'sentiment': payload.get('sentiment', {}),
            'entities': payload.get('entities', []),
            'keywords': payload.get('keywords', [])
        }
        
        return doc_id, es_doc
    except Exception as e:
        print(f"准备ES文档失败: {e}")
        return None, None

def main():
    print("🔄 简化版Qdrant到ES回填脚本")
    print("=" * 50)
    
    # 获取当前统计
    qdrant_count = get_qdrant_count()
    es_count = get_es_count()
    
    print(f"📊 当前统计:")
    print(f"  - Qdrant向量数: {qdrant_count:,}")
    print(f"  - ES文档数: {es_count:,}")
    print(f"  - 需要同步: {qdrant_count - es_count:,}")
    
    if qdrant_count <= es_count:
        print("✅ 数据已同步，无需回填")
        return
    
    # 开始同步
    print(f"\n🚀 开始同步...")
    start_time = time.time()
    
    stats = {
        'processed': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    batch_size = 100
    offset = 0
    
    while offset < qdrant_count:
        print(f"📦 处理批次: {offset + 1} - {min(offset + batch_size, qdrant_count)}")
        
        # 获取数据
        points = get_qdrant_points(limit=batch_size, offset=offset)
        if not points:
            print("⚠️  没有更多数据")
            break
        
        # 处理每个点
        for point in points:
            stats['processed'] += 1
            
            try:
                doc_id, es_doc = prepare_es_document(point)
                if not doc_id or not es_doc:
                    stats['failed'] += 1
                    continue
                
                # 检查是否已存在
                if check_es_document_exists(doc_id):
                    stats['skipped'] += 1
                    continue
                
                # 索引到ES
                if index_to_es(doc_id, es_doc):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                print(f"❌ 处理点失败: {e}")
                stats['failed'] += 1
        
        print(f"  ✅ 成功: {stats['success']}, ❌ 失败: {stats['failed']}, ⏭️  跳过: {stats['skipped']}")
        
        offset += len(points)
        time.sleep(0.1)  # 短暂休息
    
    # 最终统计
    duration = time.time() - start_time
    print(f"\n📊 同步完成:")
    print(f"  处理时间: {duration:.2f} 秒")
    print(f"  已处理: {stats['processed']:,}")
    print(f"  成功同步: {stats['success']:,}")
    print(f"  失败: {stats['failed']:,}")
    print(f"  跳过: {stats['skipped']:,}")
    
    # 验证结果
    new_es_count = get_es_count()
    print(f"\n📈 同步后统计:")
    print(f"  - Qdrant向量数: {qdrant_count:,}")
    print(f"  - ES文档数: {new_es_count:,}")
    
    diff = qdrant_count - new_es_count
    if diff == 0:
        print("  ✅ 数据完全一致！")
    else:
        print(f"  ⚠️  仍有差异: {diff:,}")

if __name__ == "__main__":
    main()
