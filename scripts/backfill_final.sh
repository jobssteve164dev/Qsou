#!/bin/bash
# 最终回填脚本

echo "🔄 最终回填脚本"
echo "================"

# 获取当前统计
echo "📊 获取当前统计..."
QD_COUNT=$(curl -s http://127.0.0.1:6333/collections/investment_documents | grep -o '"points_count":[0-9]*' | cut -d: -f2)
ES_COUNT=$(curl -s http://127.0.0.1:9200/qsou_documents_v1/_count | grep -o '"count":[0-9]*' | cut -d: -f2)

echo "  - Qdrant向量数: $QD_COUNT"
echo "  - ES文档数: $ES_COUNT"
echo "  - 需要同步: $((QD_COUNT - ES_COUNT))"

if [ "$QD_COUNT" -le "$ES_COUNT" ]; then
    echo "✅ 数据已同步，无需回填"
    exit 0
fi

echo ""
echo "🚀 开始回填..."

# 创建临时目录
TEMP_DIR="/tmp/final_backfill_$$"
mkdir -p "$TEMP_DIR"

# 分批处理
BATCH_SIZE=20
OFFSET=0
SUCCESS_COUNT=0
FAILED_COUNT=0
SKIPPED_COUNT=0

while [ $OFFSET -lt $QD_COUNT ]; do
    echo "📦 处理批次: $((OFFSET + 1)) - $((OFFSET + BATCH_SIZE))"
    
    # 获取Qdrant数据
    curl -s -X POST "http://127.0.0.1:6333/collections/investment_documents/points/scroll" \
        -H "Content-Type: application/json" \
        -d "{\"limit\": $BATCH_SIZE, \"offset\": $OFFSET, \"with_payload\": true, \"with_vector\": false}" \
        > "$TEMP_DIR/batch.json"
    
    # 检查是否获取到数据
    if [ ! -s "$TEMP_DIR/batch.json" ]; then
        echo "⚠️  没有更多数据"
        break
    fi
    
    # 使用Python处理JSON
    python3 -c "
import json
import urllib.request
import sys

try:
    with open('$TEMP_DIR/batch.json', 'r') as f:
        data = json.load(f)
    
    points = data.get('result', {}).get('points', [])
    success = 0
    failed = 0
    skipped = 0
    
    for point in points:
        try:
            doc_id = point.get('id', '')
            payload = point.get('payload', {})
            
            if not doc_id or not payload:
                failed += 1
                continue
            
            # 检查ES中是否已存在
            try:
                req = urllib.request.Request(f'http://127.0.0.1:9200/qsou_documents_v1/_doc/{doc_id}')
                req.get_method = lambda: 'HEAD'
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        skipped += 1
                        continue
            except:
                pass
            
            # 准备ES文档
            es_doc = {
                'id': doc_id,
                'title': payload.get('title', ''),
                'content': payload.get('content', ''),
                'summary': payload.get('summary', ''),
                'source': payload.get('source', ''),
                'url': payload.get('url', ''),
                'timestamp': payload.get('publish_time', payload.get('crawl_time', '')),
                'category': 'general',
                'tags': [],
                'quality_score': payload.get('importance_score', 0.0),
                'sentiment': {},
                'entities': [],
                'keywords': []
            }
            
            # 索引到ES
            data = json.dumps(es_doc).encode('utf-8')
            req = urllib.request.Request(
                f'http://127.0.0.1:9200/qsou_documents_v1/_doc/{doc_id}',
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            req.get_method = lambda: 'PUT'
            
            with urllib.request.urlopen(req, timeout=10) as r:
                response = json.loads(r.read().decode())
                if response.get('result') in ['created', 'updated']:
                    success += 1
                else:
                    failed += 1
                    
        except Exception as e:
            failed += 1
    
    print(f'  ✅ 成功: {success}, ❌ 失败: {failed}, ⏭️  跳过: {skipped}')
    
except Exception as e:
    print(f'❌ 处理批次失败: {e}')
    sys.exit(1)
" || {
        echo "❌ Python处理失败"
        break
    }
    
    OFFSET=$((OFFSET + BATCH_SIZE))
    sleep 0.1
done

# 清理临时文件
rm -rf "$TEMP_DIR"

# 最终统计
echo ""
echo "📊 回填完成，验证结果..."

NEW_ES_COUNT=$(curl -s http://127.0.0.1:9200/qsou_documents_v1/_count | grep -o '"count":[0-9]*' | cut -d: -f2)

echo "📈 回填后统计:"
echo "  - Qdrant向量数: $QD_COUNT"
echo "  - ES文档数: $NEW_ES_COUNT"

DIFF=$((QD_COUNT - NEW_ES_COUNT))
if [ $DIFF -eq 0 ]; then
    echo "  ✅ 数据完全一致！"
else
    echo "  ⚠️  仍有差异: $DIFF"
fi

echo "🎉 回填脚本执行完成"
