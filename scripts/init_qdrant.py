#!/usr/bin/env python3
"""
Qdrant 向量数据库初始化脚本
创建集合和配置向量搜索
"""

import os
import sys
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import ResponseHandlingException
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def connect_qdrant():
    """连接 Qdrant"""
    try:
        client = QdrantClient(
            host=os.getenv('QDRANT_HOST', 'localhost'),
            port=int(os.getenv('QDRANT_PORT', 6333))
        )
        
        # 测试连接
        collections = client.get_collections()
        print(f"✅ 已连接到 Qdrant，发现 {len(collections.collections)} 个集合")
        return client
        
    except ResponseHandlingException as e:
        print(f"❌ Qdrant 连接失败: {e}")
        return None
    except Exception as e:
        print(f"❌ Qdrant 连接失败: {e}")
        return None


def create_collections(client):
    """创建向量集合"""
    try:
        collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')
        vector_dimension = int(os.getenv('EMBEDDING_DIMENSION', 768))
        
        # 检查集合是否存在
        try:
            collection_info = client.get_collection(collection_name)
            print(f"ℹ️  集合 {collection_name} 已存在")
            return True
        except ResponseHandlingException:
            # 集合不存在，创建新集合
            pass
        
        # 创建主要文档集合
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_dimension,
                distance=Distance.COSINE
            ),
            optimizers_config={
                "default_segment_number": 2,
                "max_segment_size_kb": 20_000,
                "memmap_threshold_kb": 50_000,
                "indexing_threshold_kb": 20_000,
                "flush_interval_sec": 30,
                "max_optimization_threads": 2
            },
            hnsw_config={
                "m": 16,
                "ef_construct": 100,
                "full_scan_threshold": 10_000,
                "max_indexing_threads": 2
            }
        )
        
        print(f"✅ 创建集合: {collection_name} (维度: {vector_dimension})")
        
        # 创建新闻集合（如果需要分类存储）
        news_collection = f"{collection_name}_news"
        client.create_collection(
            collection_name=news_collection,
            vectors_config=VectorParams(
                size=vector_dimension,
                distance=Distance.COSINE
            )
        )
        print(f"✅ 创建集合: {news_collection}")
        
        # 创建公告集合
        announcement_collection = f"{collection_name}_announcements"
        client.create_collection(
            collection_name=announcement_collection,
            vectors_config=VectorParams(
                size=vector_dimension,
                distance=Distance.COSINE
            )
        )
        print(f"✅ 创建集合: {announcement_collection}")
        
        return True
        
    except Exception as e:
        print(f"❌ 集合创建失败: {e}")
        return False


def create_test_vectors(client):
    """创建测试向量数据"""
    try:
        collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')
        vector_dimension = int(os.getenv('EMBEDDING_DIMENSION', 768))
        
        # 创建测试向量数据
        test_points = []
        
        # 测试文档1：关于股票的
        stock_vector = np.random.rand(vector_dimension).astype(np.float32)
        stock_vector = stock_vector / np.linalg.norm(stock_vector)  # 归一化
        
        test_points.append(PointStruct(
            id=1,
            vector=stock_vector.tolist(),
            payload={
                "title": "A股市场分析报告",
                "content": "本报告分析了当前A股市场的投资机会和风险因素，包括宏观经济环境、政策影响等。",
                "category": "股票分析",
                "source": "test_source",
                "tags": ["股票", "A股", "市场分析"],
                "publish_time": "2025-01-27T12:00:00Z",
                "importance_score": 0.8
            }
        ))
        
        # 测试文档2：关于债券的
        bond_vector = np.random.rand(vector_dimension).astype(np.float32)
        bond_vector = bond_vector / np.linalg.norm(bond_vector)
        
        test_points.append(PointStruct(
            id=2,
            vector=bond_vector.tolist(),
            payload={
                "title": "企业债券投资策略",
                "content": "分析企业债券市场的投资机会，包括信用风险评估和收益率预期。",
                "category": "债券投资",
                "source": "test_source",
                "tags": ["债券", "企业债", "投资策略"],
                "publish_time": "2025-01-27T11:00:00Z",
                "importance_score": 0.6
            }
        ))
        
        # 测试文档3：关于基金的
        fund_vector = np.random.rand(vector_dimension).astype(np.float32)
        fund_vector = fund_vector / np.linalg.norm(fund_vector)
        
        test_points.append(PointStruct(
            id=3,
            vector=fund_vector.tolist(),
            payload={
                "title": "基金定投策略研究",
                "content": "探讨基金定投的优势和适合的市场环境，为投资者提供专业建议。",
                "category": "基金投资",
                "source": "test_source",
                "tags": ["基金", "定投", "投资策略"],
                "publish_time": "2025-01-27T10:00:00Z",
                "importance_score": 0.7
            }
        ))
        
        # 批量插入测试数据
        client.upsert(
            collection_name=collection_name,
            points=test_points
        )
        
        print(f"✅ 插入 {len(test_points)} 个测试向量点")
        return True
        
    except Exception as e:
        print(f"❌ 测试向量创建失败: {e}")
        return False


def verify_setup(client):
    """验证设置"""
    try:
        collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')
        
        # 检查集合信息
        collection_info = client.get_collection(collection_name)
        print(f"✅ 集合 {collection_name} 信息验证通过")
        print(f"   - 向量维度: {collection_info.config.params.vectors.size}")
        print(f"   - 距离度量: {collection_info.config.params.vectors.distance}")
        print(f"   - 点数量: {collection_info.points_count}")
        
        # 测试搜索功能
        if collection_info.points_count > 0:
            # 执行相似度搜索
            query_vector = np.random.rand(
                int(os.getenv('EMBEDDING_DIMENSION', 768))
            ).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                limit=3
            )
            
            if search_result:
                print(f"✅ 相似度搜索验证通过，返回 {len(search_result)} 个结果")
                for i, result in enumerate(search_result):
                    print(f"   - 结果 {i+1}: {result.payload.get('title', 'N/A')} "
                          f"(相似度: {result.score:.4f})")
            else:
                print("⚠️  相似度搜索返回空结果")
        
        # 测试过滤搜索
        if collection_info.points_count > 0:
            filter_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                query_filter={
                    "must": [
                        {
                            "key": "category",
                            "match": {
                                "value": "股票分析"
                            }
                        }
                    ]
                },
                limit=5
            )
            
            print(f"✅ 过滤搜索验证通过，返回 {len(filter_result)} 个结果")
        
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def cleanup_test_data(client):
    """清理测试数据"""
    try:
        collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')
        
        # 删除测试点
        client.delete(
            collection_name=collection_name,
            points_selector=[1, 2, 3]
        )
        
        print("✅ 测试数据清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试数据清理失败: {e}")
        return False


def main():
    """主函数"""
    print("🔮 开始初始化 Qdrant 向量数据库...")
    print("=" * 50)
    
    # 连接 Qdrant
    client = connect_qdrant()
    if not client:
        sys.exit(1)
    
    # 创建集合
    if not create_collections(client):
        print("❌ 集合创建失败，退出...")
        sys.exit(1)
    
    # 创建测试数据
    if not create_test_vectors(client):
        print("❌ 测试数据创建失败，退出...")
        sys.exit(1)
    
    # 验证设置
    if not verify_setup(client):
        print("❌ 验证失败，退出...")
        sys.exit(1)
    
    # 清理测试数据
    if not cleanup_test_data(client):
        print("⚠️  测试数据清理失败，但不影响功能")
    
    print("=" * 50)
    print("🎉 Qdrant 初始化完成！")
    print("\n📋 创建的集合:")
    print("  - investment_documents (主集合)")
    print("  - investment_documents_news (新闻)")
    print("  - investment_documents_announcements (公告)")
    print("\n🔍 验证:")
    print(f"  访问 http://localhost:6333/collections 查看集合列表")
    print(f"  使用 Qdrant Web UI: http://localhost:6333/dashboard")
    
    return True


if __name__ == "__main__":
    main()
