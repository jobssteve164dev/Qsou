#!/bin/bash
# 纯bash回填脚本

echo "🔄 纯bash回填脚本"
echo "=================="

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
TEMP_DIR="/tmp/bash_backfill_$$"
mkdir -p "$TEMP_DIR"

# 分批处理
BATCH_SIZE=10
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
    
    # 提取ID列表
    grep -o '"id":"[^"]*"' "$TEMP_DIR/batch.json" | cut -d'"' -f4 | while read -r doc_id; do
        if [ -n "$doc_id" ]; then
            # 检查ES中是否已存在
            if curl -s -I "http://127.0.0.1:9200/qsou_documents_v1/_doc/$doc_id" | grep -q "200 OK"; then
                SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
                continue
            fi
            
            # 获取完整的点数据
            point_data=$(curl -s -X POST "http://127.0.0.1:6333/collections/investment_documents/points/$doc_id" \
                -H "Content-Type: application/json" \
                -d '{"with_payload": true, "with_vector": false}')
            
            if [ -n "$point_data" ]; then
                # 提取payload数据
                title=$(echo "$point_data" | grep -o '"title":"[^"]*"' | cut -d'"' -f4)
                content=$(echo "$point_data" | grep -o '"content":"[^"]*"' | cut -d'"' -f4)
                source=$(echo "$point_data" | grep -o '"source":"[^"]*"' | cut -d'"' -f4)
                url=$(echo "$point_data" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
                publish_time=$(echo "$point_data" | grep -o '"publish_time":"[^"]*"' | cut -d'"' -f4)
                
                # 创建ES文档
                es_doc='{
                    "id": "'$doc_id'",
                    "title": "'$title'",
                    "content": "'$content'",
                    "source": "'$source'",
                    "url": "'$url'",
                    "timestamp": "'$publish_time'",
                    "category": "general",
                    "tags": [],
                    "quality_score": 0.0,
                    "sentiment": {},
                    "entities": [],
                    "keywords": []
                }'
                
                # 索引到ES
                if curl -s -X PUT "http://127.0.0.1:9200/qsou_documents_v1/_doc/$doc_id" \
                    -H "Content-Type: application/json" \
                    -d "$es_doc" | grep -q '"result":"created"'; then
                    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
                    echo "  ✅ 成功索引: $doc_id"
                else
                    FAILED_COUNT=$((FAILED_COUNT + 1))
                    echo "  ❌ 失败: $doc_id"
                fi
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
            fi
        fi
    done
    
    echo "  📊 当前统计: 成功=$SUCCESS_COUNT, 失败=$FAILED_COUNT, 跳过=$SKIPPED_COUNT"
    
    OFFSET=$((OFFSET + BATCH_SIZE))
    sleep 0.2
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
