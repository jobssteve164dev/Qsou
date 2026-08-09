# Qsou 自主数据基线部署

本文用于部署已经落地的最小生产基线：API 与前端不依赖 Elasticsearch、Qdrant、Redis 或传统搜索引擎即可运行；采集器按需启动，并与 API 共享原始证据和标准文档存储。

## 1. 本基线交付什么

- 版本化来源登记：`config/sources.json`。
- 原始响应正文与安全响应头的不可变文件归档。
- SQLite 数据目录：保存来源、文档身份、内容版本和可靠待处理状态。
- 自有数据关键词搜索、来源状态、证据查看、JSONL 导出和标准文档回放。
- 面向用户的“搜索”和“我的数据”页面。
- 可选采集器；派生全文索引、向量索引与 AI 处理默认关闭，不影响基线使用。

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

远程部署时，至少修改：

- `QSOU_PUBLIC_API_URL`：必须是最终用户浏览器能访问的 API 地址，不能保留为 `localhost`。
- `QSOU_CORS_ORIGINS`：填写前端真实来源，保持 JSON 数组格式。
- `QSOU_API_PORT`、`QSOU_WEB_PORT`：端口冲突时再修改。

只暴露前端域名时，将 `QSOU_PUBLIC_API_URL` 设为同域的 `https://<domain>/api/v1`。Next.js 会在容器网络内将该路径转发给 `api` 服务，用户无需访问第二个端口或域名。

在部署主机启动 API 和前端：

```bash
docker compose --env-file deploy/baseline.env up -d --build api web
```

按需运行一次采集任务：

```bash
docker compose --env-file deploy/baseline.env --profile collector up collector
```

将 `QSOU_SPIDER` 改为 `company_announcement` 可运行公告采集器。采集器是一次性任务，退出不代表 API 或前端故障。

## 4. 验证部署

以下检查都成功，才算基线部署完成：

```bash
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/api/v1/data/status
curl --fail http://localhost:8000/api/v1/data/sources
curl --fail http://localhost:3000/
```

浏览器验证：

1. 打开前端并搜索已采集关键词。
2. 打开“我的数据”，确认来源、原始证据和可搜索文档数量来自真实接口。
3. 打开一条证据正文。
4. 导出 JSONL，确认每条记录包含 `source_id`、`raw_object_id`、时间和版本标识。

如果尚未运行采集器，数量为 0 是正常空库状态，不应填充演示数据或虚构成功率。

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
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run build
npm run start -- -p 3000
```

## 6. 上线前边界

- `config/sources.json` 中的 `rights_status=review_required` 是待复核状态，不是数据保存或再分发许可结论。
- 来源覆盖状态目前只表示“已登记、是否采到数据”，还没有分页完整性、时间缺口和条款变更自动检查。
- SQLite 加共享文件卷适合单实例基线；多 API 实例、跨节点采集或大规模数据前，需要迁移到支持并发与对象存储的实现，但不能改变原始证据的权威地位。
- 备份必须覆盖来源登记、整个数据根目录及部署配置，并通过恢复演练验证，不能只备份搜索索引。
