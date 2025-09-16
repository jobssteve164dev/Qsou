# 日志收集器生命周期管理指南

## 概述

日志收集器的生命周期与开发环境完全同步，确保不会出现"僵尸"收集进程。

## 自动生命周期管理

### 启动时自动启动
```bash
./dev.sh start
# 日志收集器会自动启动（如果 ENABLE_UNIFIED_LOG=true）
```

### 停止时自动停止
```bash
./dev.sh stop
# 日志收集器会自动停止，确保不会继续收集
```

### 重启时完全重置
```bash
./dev.sh restart
# 先完全停止（包括日志收集器），再重新启动
```

## 手动管理（紧急情况）

### Windows快速停止
```batch
# 使用专用脚本
stop_all.bat

# 或者使用紧急停止
emergency_stop.bat
```

### PowerShell命令
```powershell
# 停止所有Python进程
Get-Process python* | Stop-Process -Force

# 只停止日志收集器
Get-Process | Where {$_.CommandLine -like "*unified_logger*"} | Stop-Process
```

### Python服务管理器
```bash
# 查看所有服务状态
python scripts/service_manager.py list

# 停止日志收集器
python scripts/service_manager.py stop --service log-collector

# 停止所有服务
python scripts/service_manager.py stop --all

# 清理死亡服务
python scripts/service_manager.py cleanup

# 实时监控服务
python scripts/service_manager.py monitor
```

## 生命周期保证机制

### 1. PID文件管理
- 位置：`pids/log-collector.pid`
- 启动时创建，停止时删除
- 用于跟踪进程状态

### 2. 信号处理
- 支持 SIGTERM（优雅退出）
- 支持 SIGINT（Ctrl+C）
- Windows特殊处理（SIGBREAK）

### 3. 多重保障
```bash
# stop_log_collector 函数的执行流程：
1. 发送SIGTERM信号，等待5秒
2. 如果还在运行，强制终止（SIGKILL/taskkill）
3. 清理PID文件
4. 额外扫描并清理残留进程
```

### 4. 进程查找和清理
```bash
# Windows
tasklist | findstr unified_logger
taskkill /F /PID <pid>

# Linux/Mac
pgrep -f unified_logger
pkill -f unified_logger
```

## 配置选项

在 `dev.local` 中配置：

```bash
# 完全禁用日志收集（内存不足时）
ENABLE_UNIFIED_LOG=false

# 减小日志文件大小（减少内存占用）
UNIFIED_LOG_MAX_LINES=10000

# 增加检查间隔（降低CPU占用）
LOG_COLLECTOR_CHECK_INTERVAL=5
```

## 故障排除

### 问题：日志收集器未停止

**症状**：
- `dev.sh stop` 后，日志文件还在增长
- 进程管理器中还有 `python unified_logger.py`

**解决**：
```bash
# Windows
stop_all.bat

# 或手动
taskkill /F /IM python.exe /FI "COMMANDLINE eq *unified_logger*"
```

### 问题：编码错误

**症状**：
- UnicodeEncodeError
- 中文或emoji显示为乱码

**解决**：
已通过以下方式修复：
- Python脚本设置 `PYTHONIOENCODING=utf-8`
- Windows代码页设置 `chcp 65001`
- 重新配置stdout/stderr编码

### 问题：内存占用过高

**解决**：
1. 减小日志文件大小限制
2. 增加检查间隔
3. 或完全禁用日志收集

## 最佳实践

1. **正常操作**：始终使用 `dev.sh start/stop/restart`
2. **紧急停止**：使用 `stop_all.bat` 或 `emergency_stop.bat`
3. **定期检查**：使用 `service_manager.py list` 查看服务状态
4. **资源不足**：临时禁用日志收集 `ENABLE_UNIFIED_LOG=false`
5. **开发完成**：记得执行 `dev.sh stop` 释放所有资源

## 架构设计

```
dev.sh start
    ├── start_log_collector()  # 启动日志收集器
    │   └── python unified_logger.py (后台进程)
    └── start_all_services()   # 启动其他服务

dev.sh stop
    ├── stop_all_services()
    │   └── stop_log_collector()  # 优先停止日志收集器
    │       ├── 发送SIGTERM
    │       ├── 等待退出
    │       ├── 强制终止（如需要）
    │       └── 清理残留进程
    └── cleanup()
```

## 重要提示

⚠️ **日志收集器必须与开发环境同步启停**
- 不要单独启动日志收集器
- 不要忘记停止开发环境
- 定期检查是否有僵尸进程
