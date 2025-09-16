#!/bin/bash
# 轻量级日志收集器 - 低内存占用版本

LOG_DIR="logs"
UNIFIED_LOG="$LOG_DIR/unified_light.log"
MAX_SIZE=5000  # 最大5000行

# 创建日志目录
mkdir -p "$LOG_DIR"

# 初始化日志文件
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SYSTEM] 轻量级日志收集器启动" > "$UNIFIED_LOG"

echo "轻量级日志收集器已启动"
echo "- 日志文件: $UNIFIED_LOG"
echo "- 最大行数: $MAX_SIZE"
echo "- 按 Ctrl+C 停止"
echo ""

# 简单的日志收集循环
while true; do
    # 收集各服务最新日志（只读取最后10行）
    for log_file in "$LOG_DIR"/*.log; do
        if [[ -f "$log_file" && "$log_file" != "$UNIFIED_LOG" ]]; then
            service=$(basename "$log_file" .log)
            # 只读取新增的行
            tail -n 10 "$log_file" 2>/dev/null | while IFS= read -r line; do
                if [[ -n "$line" ]]; then
                    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$service] $line" >> "$UNIFIED_LOG"
                fi
            done
        fi
    done
    
    # 检查文件大小并轮转
    if [[ -f "$UNIFIED_LOG" ]]; then
        line_count=$(wc -l < "$UNIFIED_LOG" 2>/dev/null || echo 0)
        if [[ $line_count -gt $MAX_SIZE ]]; then
            # 保留最后80%
            keep_lines=$((MAX_SIZE * 8 / 10))
            temp_file="${UNIFIED_LOG}.tmp"
            tail -n "$keep_lines" "$UNIFIED_LOG" > "$temp_file"
            mv "$temp_file" "$UNIFIED_LOG"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SYSTEM] 日志轮转完成" >> "$UNIFIED_LOG"
        fi
    fi
    
    # 较长的等待时间，减少CPU占用
    sleep 10
done
