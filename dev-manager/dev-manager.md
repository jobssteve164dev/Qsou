# 统一开发运维控制台（Dev Manager）

本模块用于在本地/开发环境下统一管理项目内的各个服务（API、前端、爬虫、Celery、ES、Qdrant、Redis 等），提供跨平台运行与 UI 控制台。

## 启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Dev Manager 后端
python dev-manager/main.py
# 健康检查
curl http://127.0.0.1:5500/health
```

设置前端环境变量以访问 Dev Manager：

```bash
# web-frontend/.env.local
NEXT_PUBLIC_DEVMAN_URL=http://localhost:5500
```

## 使用
- 访问前端控制台页面：`http://localhost:3000/monitor/dev`
- 常用 API：
  - `GET /services` - 列出服务与状态
  - `POST /services/start {"name":"api"}`
  - `POST /services/stop {"name":"api"}`
  - `POST /services/restart {"name":"api"}`
  - `GET /services/{name}/logs?lines=200`
  - `GET /services/{name}/logs/paged?offset=&limit=`
  - `GET /services/{name}/logs/download`
  - `GET /profiles`、`POST /profiles/apply {name, stop_others}`、`POST /profiles/stop {name}`
  - `GET /diagnose/ports`、`POST /diagnose/kill_port {port, token}`
  - `GET /metrics`（Prometheus）

## 配置文件
- 文件：`config/dev_services.yaml`
- 示例字段：
  - `cwd`: 进程工作目录（相对项目根）
  - `start`: 启动命令（数组）
  - `stop.port`: 监听端口（通过端口定位进程）
  - `stop.pidfile`: PID 文件路径（可选）
  - `log`: 日志文件路径，用于前端日志展示
 - `profiles`: 批量编排（如 `minimal`、`backend_only`、`fullstack`）

## 注意
- 端口管理基于 psutil 遍历连接；如需更稳健的停止方式可为服务提供 pidfile
- Windows 环境下建议避免复杂 shell 启动语句，尽量使用数组形式命令
 - 如果需要保护端口清理等敏感操作，设置环境变量 `DEVMAN_TOKEN`；前端“管理令牌”框中输入同样的 token 方可执行
