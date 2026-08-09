# Qsou 自主数据基线部署

本文用于部署已经落地的单用户生产基线：Web、API、持续采集器、索引器与 Elasticsearch 组成一个闭环。PostgreSQL 是唯一目录库，Elasticsearch 是可重建但生产常驻的全文检索层。

## 1. 本基线交付什么

- 版本化来源登记：`config/sources.json`。
- 原始响应正文与安全响应头的不可变文件归档。
- PostgreSQL 目录库：保存来源、文档身份、内容版本和可靠待处理状态。
- 自有数据关键词搜索、来源状态、证据查看、JSONL 导出和标准文档回放。
- 面向用户的“搜索”和“我的数据”页面。
- 持续采集器、常驻全文索引器及可观察运行状态；向量索引与 AI 处理默认关闭。
- 私人登录会话。浏览器只访问 Web，同域服务端代理使用 HttpOnly Cookie 持有会话，API 不直接暴露到公网。

当前回放会把已经生成的标准文档重新放入派生处理队列，不访问外部来源。它还不是“仅凭原始响应重新执行解析器”的完整灾难恢复演练；这一边界必须保留，不能把当前能力表述成全链重建已经完成。

## 2. 数据目录

运行时数据根目录由 `QSOU_DATA_ROOT` 指定，结构如下：

```text
data/qsou/
├── objects/             # 文件后端下按内容标识保存的原始正文
└── indexer-status.json  # Elasticsearch 投影器的运行就绪状态
```

PostgreSQL 与原始对象必须按同一恢复点验收。Elasticsearch、Qdrant 和模型输出不属于事实权威，可从标准文档重建。

旧 SQLite 目录只允许由一次性只读迁移脚本导入；运行服务不再支持 SQLite。对象存储升级、校验和回滚步骤见 [PostgreSQL 目录库与对象存储升级手册](storage-upgrade-runbook.md)。

## 3. 通过远程 GitOps 发布

容器镜像应在专用部署主机或 CI 构建，不要在资源敏感的共享开发机直接构建。先创建一份只属于部署环境的配置：

生产镜像必须由各自 Dockerfile 的显式 `COPY` 白名单组成，不能把仓库、构建缓存或开发依赖整体复制进运行镜像。Python 运行镜像安装依赖时禁用字节码预编译；运行期也禁止写入 `.pyc`，避免同时携带源码和可再生字节码。发布包只允许包含目标服务镜像、Compose 文件和发布清单。

```bash
cp deploy/baseline.env.example deploy/baseline.env
```

部署前至少修改：

- `QSOU_WEB_PORT`：唯一宿主机入口端口，默认 `3000`。
- `QSOU_ADMIN_USERNAME`、`QSOU_ADMIN_PASSWORD`与 `QSOU_SECRET_KEY`：登录账号、强密码与随机签名密钥，必须只保存在部署环境中。
- `QSOU_ACCESS_TOKEN_EXPIRE_MINUTES`：服务端会话有效期，默认与 Cookie 一致为 24 小时。
- `QSOU_SOURCE_IDS`：可选的来源子集；留空时运行登记中的全部启用来源。
- `QSOU_CRAWL_POLL_SECONDS`：调度器检查到期来源的频率，默认 60 秒。
- `QSOU_ADAPTER_MAX_DETAILS`：单来源单轮最多获取的详情数，默认 12；它限制批量规模，不改变来源健康判定。

Compose 只把 Web 的 `3000` 发布到宿主机。API 的 `8000` 仅通过项目内部网络提供给 Web 服务端代理；完整项目重新发布后，端口自动发现也只能选择 Web，不会把公网域名切到 API。

生产发布只走受治理的远程 GitOps；本机不启动 Docker。根 Compose 或服务拓扑变化使用项目级发布，单个既有服务的代码更新使用单服务发布。所有服务继承项目的 2C/4G/512 资源上限。

采集器启动后立即执行尚未运行的来源，随后按每个来源在 `sources.json` 中的 `schedule` 独立判断是否到期。每轮先保存入口和详情原始响应，再由对应版本适配器生成标准文档。入口页和通用页面快照不会进入正式搜索。运行终态、阶段指标和游标写入 PostgreSQL，汇总状态同时写入 `collector-status.json`。

数据资产页的“立即采集”会写入同一个 PostgreSQL 调度队列。重复点击不会制造并行任务；采集器异常重启后，已认领但未闭合的请求会自动重新排队。`enabled=false` 或 `authorization_required` 的来源不能从前台强行触发。

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
DATABASE_URL=postgresql://... ELASTICSEARCH_HOST=... ENABLE_ELASTICSEARCH=true \
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
- SEC EDGAR 的 `automated_access_allowed` 仅覆盖按官方开发者规则进行的程序化访问；运行时必须保留声明 User-Agent、低于每秒 10 次并遵守 robots。
- 来源状态区分入口成功、详情发现、详情获取与文档产出；仍没有外部独立对账源来证明历史窗口绝对完整，也没有条款变更自动检查。
- 备份必须覆盖 PostgreSQL、原始对象、来源登记和部署配置，并通过隔离恢复演练验证，不能只备份 Elasticsearch。
