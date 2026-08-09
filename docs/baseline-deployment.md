# Qsou 自主数据基线部署

本文用于部署已经落地的单用户生产基线：Web、API 与持续采集器组成一个闭环，不依赖 Elasticsearch、Qdrant、Redis 或传统搜索引擎即可运行。采集器与 API 共享原始证据和标准文档存储。

## 1. 本基线交付什么

- 版本化来源登记：`config/sources.json`。
- 原始响应正文与安全响应头的不可变文件归档。
- SQLite 数据目录：保存来源、文档身份、内容版本和可靠待处理状态。
- 自有数据关键词搜索、来源状态、证据查看、JSONL 导出和标准文档回放。
- 面向用户的“搜索”和“我的数据”页面。
- 持续采集器及可观察运行状态；派生全文索引、向量索引与 AI 处理默认关闭，不影响基线使用。
- 私人登录会话。浏览器只访问 Web，同域服务端代理使用 HttpOnly Cookie 持有会话，API 不直接暴露到公网。

当前回放会把已经生成的标准文档重新放入派生处理队列，不访问外部来源。它还不是“仅凭原始响应重新执行解析器”的完整灾难恢复演练；这一边界必须保留，不能把当前能力表述成全链重建已经完成。

## 2. 数据目录

运行时数据根目录由 `QSOU_DATA_ROOT` 指定，结构如下：

```text
data/qsou/
├── catalog.sqlite3      # 身份、版本与处理状态目录
└── objects/             # 按内容标识保存的原始正文与元数据
```

这两个部分必须作为同一个备份单元。Elasticsearch、Qdrant 和模型输出不属于基线事实权威。

## 3. 在部署主机运行容器版本

容器镜像应在专用部署主机或 CI 构建，不要在资源敏感的共享开发机直接构建。先创建一份只属于部署环境的配置：

```bash
cp deploy/baseline.env.example deploy/baseline.env
```

部署前至少修改：

- `QSOU_WEB_PORT`：唯一宿主机入口端口，默认 `3000`。
- `QSOU_ADMIN_USERNAME`、`QSOU_ADMIN_PASSWORD`与 `QSOU_SECRET_KEY`：登录账号、强密码与随机签名密钥，必须只保存在部署环境中。
- `QSOU_ACCESS_TOKEN_EXPIRE_MINUTES`：服务端会话有效期，默认与 Cookie 一致为 24 小时。
- `QSOU_CRAWLER_SPIDERS` 与 `QSOU_CRAWL_INTERVAL_SECONDS`：持续运行的采集器列表和轮询间隔。

Compose 只把 Web 的 `3000` 发布到宿主机。API 的 `8000` 仅通过项目内部网络提供给 Web 服务端代理；完整项目重新发布后，端口自动发现也只能选择 Web，不会把公网域名切到 API。

在部署主机启动 API 和前端：

```bash
docker compose --env-file deploy/baseline.env up -d --build
```

采集器启动后立即执行首轮采集，随后按 `QSOU_CRAWL_INTERVAL_SECONDS` 周期运行。每轮先保存原始响应和 Spider 结构化条目，再把未被专用解析覆盖的有效 HTML 生成可搜索页面快照。状态写入共享数据目录的 `collector-status.json`，前台“数据资产”页面直接显示正在运行、等待下一轮或部分失败，不用“暂无新数据”掩盖故障。

## 4. 验证部署

以下检查都成功，才算基线部署完成：

宿主机只应看到 Web 的 `3000`，不应存在 API 的 `8000` 发布端口。容器健康检查直接访问 API 的 `/health`；公网验收从 Web 域名开始。

浏览器验证：

1. 在无旧 Cookie 的浏览器上下文打开域名，必须进入登录页，不能直接出现应用或“退出登录”。
2. 登录后搜索已采集关键词。
3. 打开“数据资产”，确认采集状态、来源、原始证据和可搜索文档数量来自真实接口。
4. 打开一条证据正文。
5. 导出 JSONL，确认每条记录包含 `source_id`、`raw_object_id`、时间和版本标识。
6. 重新发布完整项目后再次访问域名，页面必须仍由 Web 提供，不能返回 API 根路径 JSON。

首轮采集尚未完成时数量为 0 是正常空库状态，不应填充演示数据、虚构热门搜索或成功率；但采集器状态必须可见。

## 5. 不使用容器的宿主机验证

后端：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r deploy/requirements-api.txt
ENABLE_DERIVED_SEARCH=false ENABLE_DERIVED_PROCESSING=false \
  .venv/bin/python -m uvicorn --app-dir api-gateway app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd web-frontend
npm ci
API_INTERNAL_URL=http://localhost:8000 npm run build
npm run start -- -p 3000
```

## 6. 上线前边界

- `config/sources.json` 中的 `rights_status=review_required` 是待复核状态，不是数据保存或再分发许可结论。
- 来源覆盖状态目前只表示“已登记、是否采到数据”，还没有分页完整性、时间缺口和条款变更自动检查。
- SQLite 加共享文件卷适合单实例基线；多 API 实例、跨节点采集或大规模数据前，需要迁移到支持并发与对象存储的实现，但不能改变原始证据的权威地位。
- 备份必须覆盖来源登记、整个数据根目录及部署配置，并通过恢复演练验证，不能只备份搜索索引。
