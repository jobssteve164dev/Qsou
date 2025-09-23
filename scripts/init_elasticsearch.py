#!/usr/bin/env python3
"""
Elasticsearch 初始化脚本
创建索引模板和必要的索引
"""

import os
import sys
import json
from elasticsearch import Elasticsearch
from elasticsearch import helpers
from datetime import datetime
from dateutil import parser as date_parser
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


def backfill_from_qdrant_to_es(es_host: str = None,
                               es_port: int = None,
                               qdrant_host: str = None,
                               qdrant_port: int = None,
                               collection: str = None,
                               alias: str = None,
                               batch_size: int = 500) -> bool:
    """
    将Qdrant集合中的payload文档回填到Elasticsearch（幂等）。
    仅在ES中不存在相同ID时写入，避免重复。
    """
    import os
    from qdrant_client import QdrantClient
    
    es_host = es_host or os.getenv('ELASTICSEARCH_HOST', 'localhost')
    es_port = int(es_port or os.getenv('ELASTICSEARCH_PORT', 9200))
    qdrant_host = qdrant_host or os.getenv('QDRANT_HOST', 'localhost')
    qdrant_port = int(qdrant_port or os.getenv('QDRANT_PORT', 6333))
    collection = collection or os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')
    alias = alias or f"{os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')}documents"

    es = Elasticsearch([{'host': es_host, 'port': es_port, 'scheme': 'http'}])
    qd = QdrantClient(host=qdrant_host, port=qdrant_port)

    # 获取总数
    info = qd.get_collection(collection)
    try:
        total = int(getattr(info, 'points_count', 0) or 0)
    except Exception:
        total = 0
    if not total:
        print("No points to backfill from Qdrant.")
        return True

    print(f"Backfilling from Qdrant '{collection}' -> ES alias '{alias}', total points: {total}")

    # 统计 & 日志
    offset = 0
    processed = 0
    already_exists = 0
    failed = 0
    errors_by_type = {}
    failed_log_path = os.path.join('logs', 'backfill_failures.jsonl')
    try:
        os.makedirs(os.path.dirname(failed_log_path), exist_ok=True)
    except Exception:
        pass
    while offset < total:
        limit = min(batch_size, total - offset)
        points, next_offset = qd.scroll(collection_name=collection,
                                        with_payload=True,
                                        with_vectors=False,
                                        limit=limit,
                                        offset=offset)
        if not points:
            break

        actions = []
        # 预查询已存在文档，减少409冲突
        ids = [str(p.id) for p in points]
        existing_ids = set()
        try:
            mget = es.mget(index=alias, ids=ids, _source=False, stored_fields=False)
            for doc in (mget.get('docs') or []):
                if doc.get('found') and doc.get('_id'):
                    existing_ids.add(str(doc['_id']))
        except Exception:
            # mget 失败则退化为无预查询
            existing_ids = set()

        for p in points:
            doc_id = str(p.id)
            if doc_id in existing_ids:
                already_exists += 1
                continue
            payload = dict(p.payload or {})
            # 规范化字段，避免映射冲突
            title = payload.get('title', '') or ''
            content = payload.get('content', '') or ''
            source = payload.get('source', '') or ''
            url = payload.get('url')
            tags_val = payload.get('tags', [])
            if isinstance(tags_val, str):
                tags = [tags_val]
            elif isinstance(tags_val, (list, tuple)):
                tags = [str(t) for t in tags_val]
            else:
                tags = []

            # 解析发布时间，落到模板中的 publish_time
            publish_time = None
            raw_published_at = payload.get('published_at') or payload.get('timestamp')
            if isinstance(raw_published_at, (int, float)):
                try:
                    publish_time = datetime.fromtimestamp(float(raw_published_at)).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    publish_time = None
            elif isinstance(raw_published_at, str) and raw_published_at.strip():
                try:
                    dt = date_parser.parse(raw_published_at)
                    publish_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    publish_time = None

            src = {
                'title': title,
                'content': content,
                'source': source,
                'url': url,
                'publish_time': publish_time,
                'tags': tags,
            }
            actions.append({
                '_op_type': 'create',  # 幂等：已存在则忽略
                '_index': alias,
                '_id': doc_id,
                '_source': src,
            })

        if actions:
            success, error_items = helpers.bulk(es, actions, raise_on_error=False)
            processed += success
            # 统计失败分类
            if error_items:
                for item in error_items:
                    info = item.get('create') or item.get('index') or {}
                    status = info.get('status')
                    err = info.get('error') or {}
                    err_type = (err.get('type') or '').strip()
                    reason = (err.get('reason') or '').strip()
                    doc_id = info.get('_id')
                    if status == 409 or err_type == 'version_conflict_engine_exception':
                        already_exists += 1
                        continue
                    failed += 1
                    errors_by_type[err_type] = errors_by_type.get(err_type, 0) + 1
                    # 记录失败详情（精简字段）
                    try:
                        with open(failed_log_path, 'a', encoding='utf-8') as flog:
                            flog.write(json.dumps({
                                'id': doc_id,
                                'status': status,
                                'error_type': err_type,
                                'reason': reason,
                                'index': info.get('_index'),
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
            print(f"Indexed {processed}/{total} (this batch success={success}, exists={already_exists}, failed={failed})")
        if next_offset is None:
            offset = offset + limit
        else:
            try:
                offset = int(next_offset)
            except Exception:
                offset = offset + limit

    # 汇总日志
    if failed > 0:
        print("\n[Backfill Summary]")
        print(f"  success_total={processed}, already_exists={already_exists}, failed_total={failed}")
        print(f"  failure_log={failed_log_path}")
        if errors_by_type:
            print("  errors_by_type:")
            for k, v in errors_by_type.items():
                print(f"    - {k or 'unknown'}: {v}")
    else:
        print("\n[Backfill Summary] no failures detected")
    print("Backfill completed.")
    return True


if __name__ == "__main__":
    main()
