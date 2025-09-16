# 统一日志收集机制使用指南

## 概述

本项目的开发环境脚本（`dev.sh`）现已集成了一个强大的统一日志收集机制，能够自动收集并管理整个项目所有组件的运行日志。

## 功能特性

### 核心功能
- **自动日志收集**：随开发环境启动，自动收集所有服务的日志
- **智能日志轮转**：限制5万行，超出自动覆盖（保留80%最近内容）
- **实时日志监控**：实时跟踪所有服务的日志输出
- **统一时间戳**：为所有日志添加统一的时间戳和服务标识
- **启动时清理**：每次启动开发环境时自动清理旧日志

### 收集的日志源
- API服务（FastAPI/Uvicorn）
- 前端服务（Next.js）
- Celery工作进程
- Celery监控（Flower）
- Elasticsearch
- Qdrant向量数据库
- 系统级日志

## 配置选项

在 `dev.local` 配置文件中可以自定义以下选项：

```bash
# 启用统一日志收集（默认: true）
ENABLE_UNIFIED_LOG=true

# 统一日志文件最大行数（默认: 50000）
UNIFIED_LOG_MAX_LINES=50000

# 日志收集刷新间隔（秒）
LOG_COLLECTOR_REFRESH_INTERVAL=30
```

## 使用方法

### 基本命令

```bash
# 启动开发环境（自动启动日志收集）
./dev.sh start

# 实时查看统一日志
./dev.sh unified-log

# 查看日志统计信息
./dev.sh log-stats

# 搜索特定模式的日志
./dev.sh log-search "error" api

# 显示特定级别的日志
./dev.sh log-level ERROR
```

### 高级功能

#### 1. 日志搜索
搜索包含特定模式的日志：
```bash
# 搜索所有包含 "error" 的日志
./dev.sh log-search error

# 搜索 API 服务中的错误日志
./dev.sh log-search error api

# 搜索数据库连接问题
./dev.sh log-search "connection.*failed"
```

#### 2. 日志级别过滤
按日志级别查看：
```bash
# 查看所有错误
./dev.sh log-level ERROR

# 查看警告信息
./dev.sh log-level WARN

# 查看调试信息
./dev.sh log-level DEBUG
```

#### 3. 日志统计
获取详细的日志统计信息：
```bash
./dev.sh log-stats
```

输出示例：
```
日志统计信息:
  - 总行数: 12345 / 50000
  - 文件大小: 2.3M
  - 各服务日志分布:
    * api: 3456 行
    * frontend: 2345 行
    * celery-worker: 1234 行
  - 错误数量: 23
  - 警告数量: 45
最近的错误（最多显示5条）:
    [2025-01-27 14:30:15] [api] ERROR: Database connection failed
    ...
```

## 日志文件位置

- **统一日志文件**: `logs/unified.log`
- **各服务独立日志**: `logs/[service-name].log`
- **PID文件**: `pids/log-collector.pid`

## 日志格式

每行日志的格式为：
```
[时间戳] [服务名] 原始日志内容
```

示例：
```
[2025-01-27 14:30:15] [api] INFO: Server started on port 8000
[2025-01-27 14:30:16] [frontend] INFO: Next.js server ready
[2025-01-27 14:30:17] [celery-worker] INFO: Connected to Redis
```

## 故障排除

### 日志收集器未启动
如果日志收集器未自动启动，可以：
1. 检查配置 `ENABLE_UNIFIED_LOG=true`
2. 手动查看状态 `./dev.sh status`
3. 查看错误日志 `cat logs/unified.log`

### 日志文件过大
如果日志文件增长过快：
1. 调整最大行数 `UNIFIED_LOG_MAX_LINES=30000`
2. 增加轮转频率
3. 使用日志级别过滤减少噪音

### 性能问题
如果日志收集影响性能：
1. 增加刷新间隔 `LOG_COLLECTOR_REFRESH_INTERVAL=60`
2. 减少监控的日志源
3. 禁用统一日志 `ENABLE_UNIFIED_LOG=false`

## 最佳实践

1. **定期检查日志统计**：使用 `log-stats` 命令定期检查错误和警告
2. **使用日志搜索调试**：出现问题时，使用 `log-search` 快速定位
3. **监控日志大小**：注意日志文件大小，必要时调整配置
4. **保存重要日志**：在重要操作前后，可以手动备份统一日志文件
5. **合理设置日志级别**：在生产环境中避免过多的 DEBUG 日志

## 与其他工具集成

### 与监控系统集成
统一日志文件可以被其他监控工具（如 Prometheus、Grafana）读取和分析。

### 与日志分析工具集成
可以使用工具如 `grep`、`awk`、`sed` 等对统一日志进行高级分析：

```bash
# 统计每小时的错误数
grep ERROR logs/unified.log | awk '{print $1}' | cut -d: -f1 | sort | uniq -c

# 找出最频繁的错误类型
grep ERROR logs/unified.log | awk -F'ERROR:' '{print $2}' | sort | uniq -c | sort -rn
```

## 扩展和自定义

如需添加更多日志源或自定义日志格式，可以修改 `dev.sh` 中的 `start_log_collector` 函数。

## 注意事项

1. 日志收集器会在后台持续运行，直到开发环境停止
2. 每次启动时会清理旧的统一日志
3. 日志轮转是自动的，无需手动干预
4. 统一日志包含所有服务的输出，可能包含敏感信息，请妥善保管
