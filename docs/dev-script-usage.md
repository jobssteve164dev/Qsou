# dev.sh 开发环境启动脚本使用指南

## 概述

`dev.sh` 是 Qsou 投资情报搜索引擎的一键式开发环境管理脚本，提供完整的开发环境生命周期管理功能。

## 核心功能

### 🚀 自动化环境搭建
- **依赖检测**: 自动检测并安装 Python、Node.js 依赖
- **虚拟环境**: 自动创建和激活 Python 虚拟环境
- **目录初始化**: 自动创建必要的日志、PID 目录

### 🔌 智能端口管理
- **端口检测**: 自动检测端口占用情况
- **冲突解决**: 可选择自动清理占用端口的进程
- **跨平台支持**: 兼容 Windows、macOS、Linux

### 📊 服务监控
- **健康检查**: 实时监控所有服务状态
- **进程管理**: 完整的进程生命周期管理
- **日志管理**: 集中式日志收集和查看

### 🧹 智能清理
- **自动清理**: 脚本退出时自动清理所有进程
- **信号处理**: 优雅处理 Ctrl+C 等退出信号
- **临时文件清理**: 自动清理 Python 缓存等临时文件

## 基本用法

### 启动开发环境
```bash
# 启动完整开发环境
./dev.sh start

# 或使用 Make 命令
make dev-start
```

### 停止开发环境
```bash
# 停止所有服务
./dev.sh stop

# 或使用 Make 命令
make dev-stop
```

### 查看服务状态
```bash
# 查看所有服务状态
./dev.sh status

# 或使用 Make 命令
make dev-status
```

### 查看服务日志
```bash
# 查看可用的服务日志
./dev.sh logs

# 查看特定服务日志
./dev.sh logs api
./dev.sh logs frontend
./dev.sh logs celery-worker

# 使用 Make 命令查看日志
make dev-logs SERVICE=api
```

## 高级功能

### 环境变量配置

#### 调试模式
```bash
# 启用调试模式，显示详细信息
DEBUG=true ./dev.sh start
```

#### 自动端口清理
```bash
# 自动杀死占用端口的进程
AUTO_KILL_PORTS=true ./dev.sh start
```

### 完整命令列表

| 命令 | 功能 | 描述 |
|------|------|------|
| `start` | 启动开发环境 | 启动所有开发服务 |
| `stop` | 停止开发环境 | 停止所有服务并清理 |
| `restart` | 重启环境 | 停止后重新启动所有服务 |
| `status` | 查看状态 | 显示所有服务的运行状态 |
| `logs [service]` | 查看日志 | 查看指定服务的日志 |
| `clean` | 清理环境 | 清理临时文件和日志 |
| `health` | 健康检查 | 检查外部服务连接状态 |
| `help` | 帮助信息 | 显示完整的帮助信息 |

## 配置文件 (dev.local)

### 基础配置
```bash
# 项目基本信息
PROJECT_NAME="Qsou Investment Intelligence Engine"
PROJECT_VERSION="1.0.0"
ENVIRONMENT="development"
DEBUG=true
```

### 服务端口配置
```bash
# 服务端口配置
API_PORT=8000
FRONTEND_PORT=3000
CELERY_FLOWER_PORT=5555
ELASTICSEARCH_PORT=9200
QDRANT_PORT=6333
POSTGRESQL_PORT=5432
REDIS_PORT=6379
```

### 数据库配置
```bash
# PostgreSQL 配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qsou_investment_intel
DB_USER=qsou
DB_PASSWORD=your_password

# Redis 配置
REDIS_HOST=localhost
REDIS_DB_CACHE=0
REDIS_DB_CELERY_BROKER=1
REDIS_DB_CELERY_RESULT=2
```

### 应用服务配置
```bash
# API 服务配置
API_HOST=0.0.0.0
API_WORKERS=1
API_RELOAD=true

# Celery 配置
CELERY_WORKERS=4
CELERY_LOGLEVEL=info
```

## 启动的服务

### 后端服务
- **API 服务**: FastAPI (默认端口: 8000)
  - 地址: http://localhost:8000
  - API 文档: http://localhost:8000/docs

### 前端服务
- **Next.js 前端**: (默认端口: 3000)
  - 地址: http://localhost:3000

### 任务队列
- **Celery Worker**: 异步任务处理
- **Flower 监控**: Celery 监控面板 (默认端口: 5555)
  - 地址: http://localhost:5555

## 日志管理

### 日志文件位置
```bash
logs/
├── api.log          # API 服务日志
├── frontend.log     # 前端服务日志
├── celery-worker.log # Celery 工作进程日志
└── celery-flower.log # Celery 监控日志
```

### 查看日志
```bash
# 实时查看 API 日志
./dev.sh logs api

# 查看所有可用日志
./dev.sh logs
```

## 进程管理

### PID 文件
脚本会在 `pids/` 目录下创建 PID 文件：
```bash
pids/
├── api.pid
├── frontend.pid
├── celery-worker.pid
└── celery-flower.pid
```

### 进程控制
- **优雅停止**: 先发送 TERM 信号
- **强制停止**: 等待超时后发送 KILL 信号
- **自动清理**: 退出时自动清理所有进程

## 故障排除

### 常见问题

#### 1. 端口被占用
```bash
# 问题：端口 8000 被占用
# 解决方案：使用自动端口清理
AUTO_KILL_PORTS=true ./dev.sh start
```

#### 2. Python 虚拟环境问题
```bash
# 问题：虚拟环境未激活
# 解决方案：删除并重新创建
rm -rf venv
./dev.sh start
```

#### 3. 依赖安装失败
```bash
# 问题：pip 安装失败
# 解决方案：手动更新 pip
python -m pip install --upgrade pip
./dev.sh start
```

#### 4. 服务启动失败
```bash
# 查看具体服务日志
./dev.sh logs api

# 检查外部服务状态
./dev.sh health
```

### 调试技巧

#### 启用调试模式
```bash
DEBUG=true ./dev.sh start
```

#### 查看详细日志
```bash
# 查看脚本运行日志
tail -f logs/dev.log

# 查看特定服务日志
tail -f logs/api.log
```

#### 手动检查端口
```bash
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000
```

## 与 Makefile 集成

脚本已完全集成到 Makefile 中：

```bash
# 使用 dev.sh 的 Make 命令
make dev-start     # ./dev.sh start
make dev-stop      # ./dev.sh stop
make dev-restart   # ./dev.sh restart
make dev-status    # ./dev.sh status
make dev-logs      # ./dev.sh logs

# 传统的单独启动命令仍然可用
make dev-api       # 只启动 API 服务
make dev-frontend  # 只启动前端服务
make dev-celery    # 只启动 Celery 服务
```

## 最佳实践

### 开发工作流
1. **启动环境**: `./dev.sh start`
2. **开发代码**: 服务会自动重载
3. **查看日志**: `./dev.sh logs [service]`
4. **测试功能**: 访问相应的服务端口
5. **停止环境**: `Ctrl+C` 或 `./dev.sh stop`

### 配置建议
- **端口配置**: 确保端口不与其他应用冲突
- **资源配置**: 根据机器性能调整 Worker 数量
- **日志配置**: 定期清理日志文件避免磁盘满载

### 团队协作
- **配置文件**: 不要提交包含敏感信息的 `dev.local`
- **环境一致**: 使用相同的配置模板
- **文档更新**: 配置变更及时更新文档

## 安全注意事项

- **端口暴露**: 开发环境仅监听必要端口
- **密码安全**: 不要在配置文件中使用生产密码
- **网络访问**: 开发环境应在安全的网络环境中运行
- **进程权限**: 脚本以当前用户权限运行，避免使用 root

通过 `dev.sh` 脚本，您可以获得一个完全自动化、高度可配置的开发环境，大大提升开发效率和体验！
