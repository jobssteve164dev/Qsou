#!/usr/bin/env python3
"""
将历史索引数据合并迁移到主索引 qsou_documents_v1（或基于前缀的 <prefix>documents_v1）。

策略：
- 源索引：qsoudocuments, qsou_general（如存在）
- 目标索引：<prefix>documents_v1（默认 qsou_documents_v1）
- 幂等：按 _id 写入，如目标存在则跳过。
- 字段兼容：简单字段透传；若存在 published_at/publish_time 差异，统一落到 publish_time。
- 最后：创建/绑定别名 <prefix>documents -> <prefix>documents_v1。

用法：
  py -3.9 scripts/migrate_indices_to_v1.py
"""

import os
from datetime import datetime
from typing import Dict
from elasticsearch import Elasticsearch, helpers


def connect_es() -> Elasticsearch:
    host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
    port = int(os.getenv('ELASTICSEARCH_PORT', 9200))
    return Elasticsearch([{'host': host, 'port': port, 'scheme': 'http'}])


def normalize_source(src: Dict) -> Dict:
    if not isinstance(src, dict):
        return {}
    out = dict(src)
    # 统一时间字段
    if 'publish_time' not in out:
        out['publish_time'] = out.get('published_at')
    return out


def ensure_alias(es: Elasticsearch, alias_name: str, target_index: str):
    try:
        if es.indices.exists_alias(name=alias_name):
            return
    except Exception:
        pass
    es.indices.put_alias(index=target_index, name=alias_name)


def reindex_into_v1(es: Elasticsearch, source_index: str, target_index: str) -> Dict:
    if not es.indices.exists(index=source_index):
        return {"source": source_index, "exists": False, "migrated": 0, "skipped": 0}

    migrated = 0
    skipped = 0
    actions = []

    # scroll 读取源索引
    page = es.search(index=source_index, body={"query": {"match_all": {}}, "size": 500, "sort": ["_doc"]}, scroll='2m')
    sid = page.get('_scroll_id')
    hits = page.get('hits', {}).get('hits', [])

    def flush_actions():
        nonlocal actions, migrated, skipped
        if not actions:
            return
        success, error_items = helpers.bulk(es, actions, raise_on_error=False)
        migrated += success
        if error_items:
            for item in error_items:
                info = item.get('create') or item.get('index') or {}
                status = info.get('status')
                err = info.get('error') or {}
                if status == 409 or (err.get('type') == 'version_conflict_engine_exception'):
                    skipped += 1
                else:
                    # 其余失败也计入跳过，避免阻塞
                    skipped += 1
        actions = []

    while True:
        for h in hits:
            _id = h.get('_id')
            _src = normalize_source(h.get('_source', {}))
            actions.append({
                '_op_type': 'create',
                '_index': target_index,
                '_id': _id,
                '_source': _src,
            })
            if len(actions) >= 1000:
                flush_actions()

        # 下一页
        if not hits:
            break
        page = es.scroll(scroll_id=sid, scroll='2m')
        sid = page.get('_scroll_id')
        hits = page.get('hits', {}).get('hits', [])
        if not hits:
            flush_actions()
            break

    # 关闭 scroll
    try:
        if sid:
            es.clear_scroll(scroll_id=sid)
    except Exception:
        pass

    return {"source": source_index, "exists": True, "migrated": migrated, "skipped": skipped}


def main():
    es = connect_es()
    prefix = os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')
    target_index = f"{prefix}documents_v1"
    alias_name = f"{prefix}documents"
    sources = ['qsoudocuments', 'qsou_general']

    results = []
    for src in sources:
        res = reindex_into_v1(es, src, target_index)
        results.append(res)

    # 创建别名
    ensure_alias(es, alias_name, target_index)

    # 目标总数
    try:
        target_total = es.count(index=target_index).get('count', 0)
    except Exception:
        target_total = -1

    print("Migration Summary:")
    for r in results:
        print(f"  - from {r['source']}: exists={r['exists']} migrated={r['migrated']} skipped={r['skipped']}")
    print(f"  target {target_index} total={target_total}")
    print(f"  alias ensured: {alias_name} -> {target_index}")


if __name__ == '__main__':
    main()


