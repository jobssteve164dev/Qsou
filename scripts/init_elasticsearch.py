#!/usr/bin/env python3
"""
Elasticsearch 初始化脚本
创建索引模板和必要的索引
"""

import os
import sys
import json
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def connect_elasticsearch():
    """连接 Elasticsearch"""
    try:
        es = Elasticsearch([{
            'host': os.getenv('ELASTICSEARCH_HOST', 'localhost'),
            'port': int(os.getenv('ELASTICSEARCH_PORT', 9200))
        }])
        
        # 测试连接
        if not es.ping():
            raise ConnectionError("无法连接到 Elasticsearch")
        
        info = es.info()
        print(f"✅ 已连接到 Elasticsearch {info['version']['number']}")
        return es
        
    except Exception as e:
        print(f"❌ Elasticsearch 连接失败: {e}")
        return None


def create_index_template(es):
    """创建索引模板"""
    try:
        # 读取索引模板配置
        template_path = "config/elasticsearch/index_template.json"
        if not os.path.exists(template_path):
            print(f"❌ 索引模板文件不存在: {template_path}")
            return False
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_config = json.load(f)
        
        # 创建索引模板
        es.indices.put_index_template(
            name='qsou-investment-template',
            body=template_config
        )
        
        print("✅ 索引模板创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 索引模板创建失败: {e}")
        return False


def create_indices(es):
    """创建基础索引"""
    try:
        prefix = os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')
        indices = [
            f'{prefix}news',           # 财经新闻
            f'{prefix}announcements',  # 公司公告
            f'{prefix}reports',        # 研究报告
            f'{prefix}documents'       # 通用文档
        ]
        
        for index_name in indices:
            if not es.indices.exists(index=index_name):
                es.indices.create(index=index_name)
                print(f"✅ 创建索引: {index_name}")
            else:
                print(f"ℹ️  索引已存在: {index_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 索引创建失败: {e}")
        return False


def create_ingest_pipelines(es):
    """创建数据处理管道"""
    try:
        # 创建文本处理管道
        pipeline_config = {
            "description": "Qsou投资情报文档处理管道",
            "processors": [
                {
                    "set": {
                        "field": "processed_time",
                        "value": "{{_ingest.timestamp}}"
                    }
                },
                {
                    "script": {
                        "description": "计算阅读时间 (按250词/分钟)",
                        "source": """
                        if (ctx.content != null) {
                            int wordCount = ctx.content.length() / 5;
                            ctx.word_count = wordCount;
                            ctx.reading_time = Math.max(1, Math.round(wordCount / 250.0));
                        }
                        """
                    }
                },
                {
                    "remove": {
                        "field": ["content_raw"],
                        "ignore_missing": true
                    }
                }
            ]
        }
        
        es.ingest.put_pipeline(
            id='qsou-document-pipeline',
            body=pipeline_config
        )
        
        print("✅ 数据处理管道创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 数据处理管道创建失败: {e}")
        return False


def verify_setup(es):
    """验证设置"""
    try:
        # 检查索引模板
        templates = es.indices.get_index_template(name='qsou-investment-template')
        if templates['index_templates']:
            print("✅ 索引模板验证通过")
        
        # 检查索引
        prefix = os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')
        indices = es.indices.get(index=f'{prefix}*')
        print(f"✅ 发现 {len(indices)} 个索引")
        
        # 检查管道
        pipeline = es.ingest.get_pipeline(id='qsou-document-pipeline')
        if pipeline:
            print("✅ 数据处理管道验证通过")
        
        # 插入测试文档
        test_doc = {
            "title": "Elasticsearch 测试文档",
            "content": "这是一个测试文档，用于验证索引配置是否正确。包含中文分词测试：股票、证券、投资、金融市场。",
            "source": "test",
            "category": "test",
            "sentiment_score": 0.5,
            "publish_time": "2025-01-27 12:00:00"
        }
        
        result = es.index(
            index=f'{prefix}documents',
            body=test_doc,
            pipeline='qsou-document-pipeline'
        )
        
        if result['result'] == 'created':
            print("✅ 测试文档插入成功")
            
            # 刷新索引
            es.indices.refresh(index=f'{prefix}documents')
            
            # 测试搜索
            search_result = es.search(
                index=f'{prefix}documents',
                body={
                    "query": {
                        "match": {
                            "content": "测试"
                        }
                    }
                }
            )
            
            if search_result['hits']['total']['value'] > 0:
                print("✅ 搜索功能验证通过")
                
                # 删除测试文档
                es.delete(index=f'{prefix}documents', id=result['_id'])
                print("✅ 测试文档清理完成")
            else:
                print("⚠️  搜索功能可能存在问题")
        
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def main():
    """主函数"""
    print("🔍 开始初始化 Elasticsearch...")
    print("=" * 50)
    
    # 连接 Elasticsearch
    es = connect_elasticsearch()
    if not es:
        sys.exit(1)
    
    # 创建索引模板
    if not create_index_template(es):
        print("❌ 索引模板创建失败，退出...")
        sys.exit(1)
    
    # 创建索引
    if not create_indices(es):
        print("❌ 索引创建失败，退出...")
        sys.exit(1)
    
    # 创建处理管道
    if not create_ingest_pipelines(es):
        print("❌ 处理管道创建失败，退出...")
        sys.exit(1)
    
    # 验证设置
    if not verify_setup(es):
        print("❌ 验证失败，退出...")
        sys.exit(1)
    
    print("=" * 50)
    print("🎉 Elasticsearch 初始化完成！")
    print("\n📋 创建的资源:")
    print("  - 索引模板: qsou-investment-template")
    print("  - 索引: qsou_news, qsou_announcements, qsou_reports, qsou_documents")
    print("  - 处理管道: qsou-document-pipeline")
    print("\n🔍 验证:")
    print(f"  访问 http://localhost:9200/_cat/indices/qsou_* 查看索引")
    print(f"  访问 http://localhost:9200/_template/qsou-investment-template 查看模板")
    
    return True


if __name__ == "__main__":
    main()
