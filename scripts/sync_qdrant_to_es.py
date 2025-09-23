#!/usr/bin/env python3
"""
Qdrant到ES数据回填脚本

将Qdrant中的文档数据回填到Elasticsearch，确保数据一致性
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.parse

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False
    print("❌ elasticsearch包未安装，请先安装: pip install elasticsearch")

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("❌ qdrant-client包未安装，请先安装: pip install qdrant-client")


class QdrantToESSyncer:
    """Qdrant到ES数据同步器"""
    
    def __init__(self, 
                 qdrant_url: str = "http://localhost:6333",
                 es_url: str = "http://localhost:9200",
                 collection_name: str = "investment_documents",
                 es_index_name: str = "qsou_documents"):
        """
        初始化同步器
        
        Args:
            qdrant_url: Qdrant服务URL
            es_url: Elasticsearch服务URL
            collection_name: Qdrant集合名称
            es_index_name: ES索引名称
        """
        self.qdrant_url = qdrant_url
        self.es_url = es_url
        self.collection_name = collection_name
        self.es_index_name = es_index_name
        
        # 初始化客户端
        self.qdrant_client = None
        self.es_client = None
        
        self.stats = {
            'total_points': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    def initialize_clients(self) -> bool:
        """初始化客户端连接"""
        print("🔌 初始化客户端连接...")
        
        # 初始化Qdrant客户端
        if QDRANT_AVAILABLE:
            try:
                self.qdrant_client = QdrantClient(url=self.qdrant_url)
                # 测试连接
                collections = self.qdrant_client.get_collections()
                print(f"✅ Qdrant连接成功，发现 {len(collections.collections)} 个集合")
            except Exception as e:
                print(f"❌ Qdrant连接失败: {e}")
                return False
        else:
            print("❌ Qdrant客户端不可用")
            return False
        
        # 初始化ES客户端
        if ES_AVAILABLE:
            try:
                self.es_client = Elasticsearch([self.es_url])
                # 测试连接
                if self.es_client.ping():
                    print("✅ Elasticsearch连接成功")
                else:
                    print("❌ Elasticsearch连接失败")
                    return False
            except Exception as e:
                print(f"❌ Elasticsearch连接失败: {e}")
                return False
        else:
            print("❌ Elasticsearch客户端不可用")
            return False
        
        return True
    
    def get_qdrant_stats(self) -> Dict[str, Any]:
        """获取Qdrant统计信息"""
        try:
            # 使用HTTP API获取集合信息
            url = f"{self.qdrant_url}/collections/{self.collection_name}"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
            
            result = data['result']
            return {
                'points_count': result.get('points_count', 0),
                'indexed_vectors_count': result.get('indexed_vectors_count', 0),
                'status': result.get('status', 'unknown')
            }
        except Exception as e:
            print(f"❌ 获取Qdrant统计失败: {e}")
            return {}
    
    def get_es_stats(self) -> Dict[str, Any]:
        """获取ES统计信息"""
        try:
            # 检查索引是否存在
            if not self.es_client.indices.exists(index=self.es_index_name):
                print(f"⚠️  ES索引 {self.es_index_name} 不存在，将创建")
                self.create_es_index()
            
            # 获取文档数量
            count_result = self.es_client.count(index=self.es_index_name)
            return {
                'count': count_result['count'],
                'index_exists': True
            }
        except Exception as e:
            print(f"❌ 获取ES统计失败: {e}")
            return {'count': 0, 'index_exists': False}
    
    def create_es_index(self):
        """创建ES索引"""
        try:
            mapping = {
                "mappings": {
                    "properties": {
                        "title": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "summary": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "source": {
                            "type": "keyword"
                        },
                        "url": {
                            "type": "keyword"
                        },
                        "timestamp": {
                            "type": "date"
                        },
                        "category": {
                            "type": "keyword"
                        },
                        "tags": {
                            "type": "keyword"
                        },
                        "quality_score": {
                            "type": "float"
                        },
                        "sentiment": {
                            "type": "object"
                        },
                        "entities": {
                            "type": "keyword"
                        },
                        "keywords": {
                            "type": "keyword"
                        }
                    }
                }
            }
            
            self.es_client.indices.create(index=self.es_index_name, body=mapping)
            print(f"✅ 创建ES索引: {self.es_index_name}")
        except Exception as e:
            print(f"❌ 创建ES索引失败: {e}")
            raise
    
    def fetch_qdrant_points(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """从Qdrant获取点数据"""
        try:
            # 使用HTTP API获取点数据
            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll"
            payload = {
                "limit": limit,
                "offset": offset,
                "with_payload": True,
                "with_vector": False  # 不需要向量数据
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
            print(f"❌ 获取Qdrant点数据失败: {e}")
            return []
    
    def check_document_exists_in_es(self, doc_id: str) -> bool:
        """检查文档是否已存在于ES中"""
        try:
            return self.es_client.exists(index=self.es_index_name, id=doc_id)
        except:
            return False
    
    def prepare_es_document(self, point: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """准备ES文档数据"""
        try:
            payload = point.get('payload', {})
            doc_id = str(point.get('id', ''))
            
            if not doc_id or not payload:
                return None
            
            # 构建ES文档
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
            
            return es_doc
        except Exception as e:
            print(f"❌ 准备ES文档失败: {e}")
            return None
    
    def sync_batch(self, points: List[Dict[str, Any]]) -> Dict[str, int]:
        """同步一批数据"""
        batch_stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        # 准备批量操作
        bulk_actions = []
        
        for point in points:
            try:
                doc_id = str(point.get('id', ''))
                if not doc_id:
                    batch_stats['failed'] += 1
                    continue
                
                # 检查是否已存在
                if self.check_document_exists_in_es(doc_id):
                    batch_stats['skipped'] += 1
                    continue
                
                # 准备文档
                es_doc = self.prepare_es_document(point)
                if not es_doc:
                    batch_stats['failed'] += 1
                    continue
                
                # 添加到批量操作
                action = {
                    '_index': self.es_index_name,
                    '_id': doc_id,
                    '_source': es_doc
                }
                bulk_actions.append(action)
                
            except Exception as e:
                print(f"❌ 处理点数据失败: {e}")
                batch_stats['failed'] += 1
        
        # 执行批量索引
        if bulk_actions:
            try:
                success_count, failed_items = bulk(
                    self.es_client,
                    bulk_actions,
                    chunk_size=100,
                    request_timeout=30
                )
                batch_stats['success'] = success_count
                batch_stats['failed'] += len(failed_items)
            except Exception as e:
                print(f"❌ 批量索引失败: {e}")
                batch_stats['failed'] += len(bulk_actions)
        
        return batch_stats
    
    def run_sync(self, batch_size: int = 1000) -> bool:
        """执行同步"""
        print("🚀 开始数据同步...")
        self.stats['start_time'] = datetime.now()
        
        # 获取统计信息
        qdrant_stats = self.get_qdrant_stats()
        es_stats = self.get_es_stats()
        
        print(f"📊 同步前统计:")
        print(f"  - Qdrant向量数: {qdrant_stats.get('points_count', 0):,}")
        print(f"  - ES文档数: {es_stats.get('count', 0):,}")
        print(f"  - 需要同步: {qdrant_stats.get('points_count', 0) - es_stats.get('count', 0):,}")
        
        self.stats['total_points'] = qdrant_stats.get('points_count', 0)
        
        # 分批处理
        offset = 0
        while offset < self.stats['total_points']:
            print(f"📦 处理批次: {offset + 1} - {min(offset + batch_size, self.stats['total_points'])}")
            
            # 获取数据
            points = self.fetch_qdrant_points(limit=batch_size, offset=offset)
            if not points:
                print("⚠️  没有更多数据，结束同步")
                break
            
            # 同步批次
            batch_stats = self.sync_batch(points)
            
            # 更新统计
            self.stats['processed'] += len(points)
            self.stats['success'] += batch_stats['success']
            self.stats['failed'] += batch_stats['failed']
            self.stats['skipped'] += batch_stats['skipped']
            
            print(f"  ✅ 成功: {batch_stats['success']}, ❌ 失败: {batch_stats['failed']}, ⏭️  跳过: {batch_stats['skipped']}")
            
            # 更新偏移量
            offset += len(points)
            
            # 短暂休息
            time.sleep(0.1)
        
        self.stats['end_time'] = datetime.now()
        return True
    
    def print_final_stats(self):
        """打印最终统计"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print("\n" + "=" * 60)
        print("📊 同步完成统计")
        print("=" * 60)
        print(f"总处理时间: {duration:.2f} 秒")
        print(f"总向量数: {self.stats['total_points']:,}")
        print(f"已处理: {self.stats['processed']:,}")
        print(f"成功同步: {self.stats['success']:,}")
        print(f"失败: {self.stats['failed']:,}")
        print(f"跳过(已存在): {self.stats['skipped']:,}")
        
        if self.stats['success'] > 0:
            print(f"同步速率: {self.stats['success'] / duration:.2f} 文档/秒")
        
        # 获取最终统计
        qdrant_stats = self.get_qdrant_stats()
        es_stats = self.get_es_stats()
        
        print(f"\n📈 同步后统计:")
        print(f"  - Qdrant向量数: {qdrant_stats.get('points_count', 0):,}")
        print(f"  - ES文档数: {es_stats.get('count', 0):,}")
        
        diff = qdrant_stats.get('points_count', 0) - es_stats.get('count', 0)
        if diff == 0:
            print("  ✅ 数据完全一致！")
        else:
            print(f"  ⚠️  仍有差异: {diff:,}")


def main():
    """主函数"""
    print("🔄 Qdrant到ES数据回填脚本")
    print("=" * 60)
    
    # 检查依赖
    if not ES_AVAILABLE or not QDRANT_AVAILABLE:
        print("❌ 缺少必要依赖，请先安装:")
        print("   pip install elasticsearch qdrant-client")
        return False
    
    # 创建同步器
    syncer = QdrantToESSyncer()
    
    # 初始化客户端
    if not syncer.initialize_clients():
        print("❌ 客户端初始化失败")
        return False
    
    # 执行同步
    try:
        success = syncer.run_sync(batch_size=500)  # 使用较小的批次大小
        syncer.print_final_stats()
        return success
    except KeyboardInterrupt:
        print("\n⚠️  用户中断同步")
        return False
    except Exception as e:
        print(f"❌ 同步过程中发生错误: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
