#!/bin/bash
# 使用curl的简单回填脚本

echo "🔄 Qdrant到ES回填脚本 (curl版本)"
echo "=================================="

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
echo "🚀 开始同步..."

# 创建临时目录
TEMP_DIR="/tmp/backfill_$$"
mkdir -p "$TEMP_DIR"

# 分批处理
BATCH_SIZE=50
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
    
    # 使用jq处理JSON（如果可用）
    if command -v jq >/dev/null 2>&1; then
        # 使用jq处理
        jq -r '.result.points[] | @base64' "$TEMP_DIR/batch.json" | while read -r point_b64; do
            point=$(echo "$point_b64" | base64 -d)
            doc_id=$(echo "$point" | jq -r '.id')
            payload=$(echo "$point" | jq -r '.payload')
            
            if [ "$doc_id" = "null" ] || [ "$payload" = "null" ]; then
                FAILED_COUNT=$((FAILED_COUNT + 1))
                continue
            fi
            
            # 检查ES中是否已存在
            if curl -s -I "http://127.0.0.1:9200/qsou_documents_v1/_doc/$doc_id" | grep -q "200 OK"; then
                SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
                continue
            fi
            
            # 准备ES文档
            es_doc=$(echo "$payload" | jq -c '. + {"id": "'$doc_id'"}')
            
            # 索引到ES
            if curl -s -X PUT "http://127.0.0.1:9200/qsou_documents_v1/_doc/$doc_id" \
                -H "Content-Type: application/json" \
                -d "$es_doc" | grep -q '"result":"created"'; then
                SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
            fi
        done
    else
        echo "⚠️  jq不可用，跳过此批次"
        FAILED_COUNT=$((FAILED_COUNT + BATCH_SIZE))
    fi
    
    echo "  ✅ 成功: $SUCCESS_COUNT, ❌ 失败: $FAILED_COUNT, ⏭️  跳过: $SKIPPED_COUNT"
    
    OFFSET=$((OFFSET + BATCH_SIZE))
    sleep 0.1
done

# 清理临时文件
rm -rf "$TEMP_DIR"

# 最终统计
echo ""
echo "📊 同步完成，验证结果..."

NEW_ES_COUNT=$(curl -s http://127.0.0.1:9200/qsou_documents_v1/_count | grep -o '"count":[0-9]*' | cut -d: -f2)

echo "📈 同步后统计:"
echo "  - Qdrant向量数: $QD_COUNT"
echo "  - ES文档数: $NEW_ES_COUNT"

DIFF=$((QD_COUNT - NEW_ES_COUNT))
if [ $DIFF -eq 0 ]; then
    echo "  ✅ 数据完全一致！"
else
    echo "  ⚠️  仍有差异: $DIFF"
fi

echo "🎉 回填脚本执行完成"
