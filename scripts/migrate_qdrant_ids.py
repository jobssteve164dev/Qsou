#!/usr/bin/env python3
"""
Qdrant 点ID迁移为“确定性ID”脚本

目标：
- 将集合中使用随机UUID的旧点，迁移为与ES一致的确定性文档ID：
  1) content_hash 存在则用之；
  2) 否则 url|title|publish_time 的MD5；
  3) 若仍不可得，保留原ID（跳过）。

实现策略（安全、幂等）：
- 不直接修改ID（Qdrant不支持改ID），采用“创建新点 + 删除旧点”的方式。
- 若目标ID已存在点，则：
  - 比较payload（保留更完整者，或直接跳过，仅删除旧点）；
  - 默认不覆盖已存在点（--prefer-existing）。

用法：
  Dry-run（只统计不执行写操作）：
    py -3.9 scripts/migrate_qdrant_ids.py --dry-run --limit 1000

  执行迁移：
    py -3.9 scripts/migrate_qdrant_ids.py --batch-size 200
"""

import os
import sys
import hashlib
import json
from datetime import datetime
from typing import Dict, Tuple

import argparse

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, PointIdsList


def deterministic_id(payload: Dict) -> str:
    content_hash = (payload or {}).get('content_hash')
    if content_hash and isinstance(content_hash, str) and content_hash.strip():
        return content_hash
    url = str((payload or {}).get('url') or '')
    title = str((payload or {}).get('title') or '')
    publish_time = str((payload or {}).get('publish_time') or (payload or {}).get('published_at') or '')
    basis = f"{url}|{title}|{publish_time}"
    if basis.strip():
        return hashlib.md5(basis.encode('utf-8')).hexdigest()
    return ''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=os.getenv('QDRANT_HOST', 'localhost'))
    parser.add_argument('--port', type=int, default=int(os.getenv('QDRANT_PORT', 6333)))
    parser.add_argument('--collection', default=os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents'))
    parser.add_argument('--batch-size', type=int, default=200)
    parser.add_argument('--limit', type=int, default=0, help='仅处理前N条（0表示全量）')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--prefer-existing', action='store_true', help='当新ID已存在时保留现有点并删除旧点（默认行为）')
    args = parser.parse_args()

    qd = QdrantClient(host=args.host, port=args.port)

    info = qd.get_collection(args.collection)
    total = int(getattr(info, 'points_count', 0) or 0)
    print(f"Collection: {args.collection}, total points: {total}")

    processed = 0
    updated = 0
    skipped = 0
    conflicts = 0
    created = 0
    deleted = 0

    log_path = os.path.join('logs', 'qdrant_id_migration.jsonl')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        os.remove(log_path)
    except OSError:
        pass

    # 确保数值类型
    try:
        total = int(total)
    except Exception:
        total = 0
    offset = 0
    while int(offset) < int(total):
        limit = min(args.batch_size, total - offset)
        points, next_offset = qd.scroll(collection_name=args.collection,
                                        with_payload=True,
                                        with_vectors=True,
                                        limit=limit,
                                        offset=offset)
        if not points:
            break

        for p in points:
            processed += 1
            old_id = str(p.id)
            payload = dict(p.payload or {})
            new_id = deterministic_id(payload)
            if not new_id or new_id == old_id:
                skipped += 1
                continue

            # 若目标ID已存在
            exists = False
            try:
                exists = qd.retrieve(collection_name=args.collection, ids=[new_id])
                exists = bool(exists)
            except Exception:
                exists = False

            if exists:
                conflicts += 1
                # 默认保留已存在点，仅删除旧点（若旧点与新点不同）
                if not args.dry_run:
                    if old_id != new_id:
                        qd.delete(collection_name=args.collection, points_selector=PointIdsList(points=[old_id]))
                        deleted += 1
                # 记录日志
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'action': 'conflict_keep_existing_delete_old',
                        'old_id': old_id,
                        'new_id': new_id
                    }, ensure_ascii=False) + "\n")
                continue

            # 创建新点并删除旧点
            if not args.dry_run:
                try:
                    qd.upsert(collection_name=args.collection,
                              points=[PointStruct(id=new_id, vector=p.vector, payload=payload)])
                    created += 1
                    qd.delete(collection_name=args.collection, points_selector=PointIdsList(points=[old_id]))
                    deleted += 1
                except Exception as e:
                    with open(log_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'action': 'error', 'old_id': old_id, 'new_id': new_id, 'error': str(e)}, ensure_ascii=False) + "\n")
                    continue

            updated += 1
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'action': 'migrated', 'old_id': old_id, 'new_id': new_id}, ensure_ascii=False) + "\n")

            if args.limit and processed >= args.limit:
                break

        if args.limit and processed >= args.limit:
            break

        offset = next_offset if next_offset is not None else (int(offset) + int(limit))
        try:
            offset = int(offset)
        except Exception:
            offset = int(offset) if isinstance(offset, int) else 0

        print(f"progress: processed={processed} updated={updated} created={created} deleted={deleted} skipped={skipped} conflicts={conflicts}")

    print("\nSummary:")
    print(f"  processed={processed} updated={updated} created={created} deleted={deleted} skipped={skipped} conflicts={conflicts}")
    print(f"  log={log_path}")


if __name__ == '__main__':
    main()


