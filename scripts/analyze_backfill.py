#!/usr/bin/env python3
"""
分析 Qdrant 与 ES 差异并定位不可索引原因

功能：
- 扫描 Qdrant 指定集合的 ID 列表
- 批量在 ES 的多个索引中查询是否已存在这些文档
- 统计：已在主索引、已在其他索引、完全缺失
- 对缺失样本尝试写入主索引（create），记录错误类型与原因
- 输出日志到 logs/backfill_analysis.jsonl

用法：
  py -3.9 scripts/analyze_backfill.py
可选环境变量：
  ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_INDEX_PREFIX
  QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Tuple, Set

from elasticsearch import Elasticsearch, helpers
from dateutil import parser as date_parser
from qdrant_client import QdrantClient


def connect_es() -> Elasticsearch:
    host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
    port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
    return Elasticsearch([{'host': host, 'port': port, 'scheme': 'http'}])


def connect_qdrant() -> QdrantClient:
    host = os.getenv('QDRANT_HOST', 'localhost')
    port = int(os.getenv('QDRANT_PORT', 6333))
    return QdrantClient(host=host, port=port)


def normalize_doc(payload: Dict) -> Dict:
    title = (payload or {}).get('title', '') or ''
    content = (payload or {}).get('content', '') or ''
    source = (payload or {}).get('source', '') or ''
    url = (payload or {}).get('url')
    tags_val = (payload or {}).get('tags', [])
    if isinstance(tags_val, str):
        tags = [tags_val]
    elif isinstance(tags_val, (list, tuple)):
        tags = [str(t) for t in tags_val]
    else:
        tags = []

    publish_time = None
    raw_published_at = (payload or {}).get('published_at') or (payload or {}).get('timestamp')
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

    return {
        'title': title,
        'content': content,
        'source': source,
        'url': url,
        'publish_time': publish_time,
        'tags': tags,
    }


def main():
    es = connect_es()
    qd = connect_qdrant()

    prefix = os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')
    main_index = f'{prefix}documents_v1'
    other_indices = ['qsoudocuments', 'qsou_general']
    collection = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')

    info = qd.get_collection(collection)
    total = int(getattr(info, 'points_count', 0) or 0)
    print(f'Total Qdrant points: {total}')

    failed_log_path = os.path.join('logs', 'backfill_analysis.jsonl')
    os.makedirs(os.path.dirname(failed_log_path), exist_ok=True)
    try:
        os.remove(failed_log_path)
    except OSError:
        pass

    offset = 0
    batch_size = 500
    stats = {
        'checked': 0,
        'present_main': 0,
        'present_other': 0,
        'missing': 0,
        'write_success': 0,
        'write_failed': 0,
        'errors_by_type': {},
    }

    # 仅对缺失样本尝试写入，避免大规模重复创建
    sample_try_limit = 100

    while offset < total:
        limit = min(batch_size, total - offset)
        points, next_offset = qd.scroll(collection_name=collection,
                                        with_payload=True,
                                        with_vectors=False,
                                        limit=limit,
                                        offset=offset)
        if not points:
            break

        ids = [str(p.id) for p in points]
        # mget 跨索引查询存在性
        docs = []
        for id_ in ids:
            docs.append({'_index': main_index, '_id': id_})
            for idx in other_indices:
                docs.append({'_index': idx, '_id': id_})

    # 严格存在性检查：逐个 HEAD exists（数量较小可承受，保证结论可靠）
    present_by_id: Dict[str, Tuple[bool, bool]] = {id_: (False, False) for id_ in ids}
    for id_ in ids:
        in_main = False
        in_other = False
        try:
            in_main = bool(es.exists(index=main_index, id=id_))
        except Exception:
            in_main = False
        if not in_main:
            for idx in other_indices:
                try:
                    if es.indices.exists(index=idx) and es.exists(index=idx, id=id_):
                        in_other = True
                        break
                except Exception:
                    continue
        present_by_id[id_] = (in_main, in_other)

        # 统计并对缺失样本尝试写入
        actions = []
        id_to_src: Dict[str, Dict] = {}
        for p in points:
            id_ = str(p.id)
            in_main, in_other = present_by_id.get(id_, (False, False))
            stats['checked'] += 1
            if in_main:
                stats['present_main'] += 1
                continue
            if in_other:
                stats['present_other'] += 1
                continue
            stats['missing'] += 1

            if stats['write_success'] + stats['write_failed'] < sample_try_limit:
                src = normalize_doc(dict(p.payload or {}))
                id_to_src[id_] = src
                actions.append({
                    '_op_type': 'create',
                    '_index': main_index,
                    '_id': id_,
                    '_source': src,
                })

        if actions:
            success, error_items = helpers.bulk(es, actions, raise_on_error=False)
            stats['write_success'] += success
            if error_items:
                for item in error_items:
                    info = item.get('create') or item.get('index') or {}
                    status = info.get('status')
                    err = info.get('error') or {}
                    err_type = (err.get('type') or '').strip() or 'unknown'
                    reason = (err.get('reason') or '').strip()
                    doc_id = info.get('_id')
                    stats['write_failed'] += 1
                    stats['errors_by_type'][err_type] = stats['errors_by_type'].get(err_type, 0) + 1
                    # 写入失败详情
                    try:
                        with open(failed_log_path, 'a', encoding='utf-8') as flog:
                            flog.write(json.dumps({
                                'id': doc_id,
                                'status': status,
                                'error_type': err_type,
                                'reason': reason,
                                'index': info.get('_index'),
                                'source': id_to_src.get(doc_id),
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass

        # 下一批
        if next_offset is None:
            offset = offset + limit
        else:
            try:
                offset = int(next_offset)
            except Exception:
                offset = offset + limit

        # 简要进度
        print(f"Progress: checked={stats['checked']} main={stats['present_main']} other={stats['present_other']} missing={stats['missing']} write_ok={stats['write_success']} write_fail={stats['write_failed']}")

    print("\n=== Analysis Summary ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats['write_failed']:
        print(f"Failure details: {failed_log_path}")


if __name__ == '__main__':
    sys.exit(0 if main() is None else 0)


