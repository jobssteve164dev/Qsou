# Qsou 数据流架构

> 文档定位：描述自主数据资产的目标数据流，并标明当前代码与目标之间的差距。
>
> 设计权威：[自主数据资产设计指导](./data-sovereignty-design-guidelines.md)。

## 1. 当前交付目标

当前第一优先级是先闭环一版完整、可实际使用的数据链路：一份真实来源内容完成采集后，系统自动保存原始证据、生成标准文档、执行基础处理、写入统一全文索引，并能从搜索结果回到对应证据。

首版链路固定为：

```text
来源登记
  → 采集与原始证据归档
  → 解析、身份与版本登记
  → 清洗、特征提取、去重、质量评估
  → 处理结果写回 PostgreSQL 标准文档
  → Elasticsearch 统一全文索引
  → 搜索结果与原始证据查看
```

首版不以全量消化已有存档、向量检索、LLM、跨节点对象存储或灾难恢复演练作为上线前置条件。这些能力不能阻断主链产生可搜索结果。

长期数据权威仍然是来源登记与不可变原始证据。PostgreSQL 标准文档是结构化权威；Elasticsearch、后续向量索引和模型结果均为可重建派生层。

## 2. 当前基线（Observed in code）

当前已运行的主要代码路径是：

```text
来源登记 config/sources.json
  → 持续调度器按每个来源的频率运行版本化适配器
  → Scrapy Downloader Middleware 归档原始响应
  → Spider 解析并关联 raw_object_id
  → Scrapy Item Pipeline 登记身份、时间和内容版本
  → PostgreSQL processing_outbox
  → 独立 indexer 将标准文档投影到 Elasticsearch
  → FastAPI 认证后的自有数据搜索、证据查看、导出与回放
  → Next.js 同域会话代理
  → 搜索与数据资产界面
```

- `qsou_data/registry.py` 负责版本化来源登记与 URL 归属校验。
- `qsou_data/store.py` 负责原始证据、PostgreSQL 目录、身份版本、可靠待处理状态、降级检索、导出和回放。
- `qsou_data/indexer.py` 持续把 PostgreSQL 标准文档投影到 Elasticsearch，并周期性校正历史版本的可见状态。
- `crawler/qsou_crawler/middlewares.py` 在 Spider 解析前保存响应，并把证据身份传给产出条目。
- `crawler/qsou_crawler/pipelines/data_processing_pipeline.py` 当前负责验证条目和登记标准文档；生产配置没有启用 Celery 派生处理。
- `crawler/qsou_crawler/adapters/` 为登记来源提供一对一、可版本化的入口发现和详情解析契约。
- `crawler/run_schedule.py` 按来源频率独立调度，并把入口、详情、文档、失败和游标写入运行账本。
- `adapter_run_requests` 为逐源“立即采集”提供持久队列、去重、原子认领和重启恢复，不另建第二套调度心智。
- 通用 HTML 快照仍保留原始证据，但不进入正式搜索语料；入口页不能掩盖专用适配器失败。
- `data-processor/pipeline.py` 已具备清洗、特征提取、去重和质量评估代码，但尚未接入当前生产主链。
- `data-processor/tasks.py` 是依赖 Celery、Redis 和旧索引入口的历史异步路径；处理结果没有完整写回 PostgreSQL 标准文档，不能作为首版生产主入口。
- `api-gateway/app/api/v1/endpoints/data_assets.py` 提供来源、证据、版本、导出与回放入口。
- `web-frontend/src/pages/api/` 在服务端持有 HttpOnly 会话并代理内部 API；浏览器不保存令牌，API 不发布宿主机端口。

生产基线常驻 Elasticsearch，全文搜索不可用或索引同步失联时健康检查失败；PostgreSQL 标准文档仍是可重建索引的事实来源。当前实际缺口是标准文档登记后没有经过基础处理便进入索引。

## 3. 首版闭环设计

### 3.1 最小生产技术栈

首版只使用现有技术：

| 运行角色 | 技术 | 首版职责 |
|---|---|---|
| `collector` | Python、Scrapy、现有调度器 | 发现入口、抓取详情、先归档响应、解析并登记标准文档 |
| `data-worker` | Python、现有处理器与 indexer | 从 PostgreSQL 领取任务，处理文档，持久化结果并写入全文索引 |
| 目录与处理队列 | PostgreSQL | 保存来源、证据目录、标准文档、版本关系和处理状态 |
| 原始正文 | 现有持久卷文件存储 | 保存不可变响应正文与元数据 |
| 全文检索 | Elasticsearch | 保存可重建的统一搜索投影 |
| 使用入口 | 现有 FastAPI 与 Next.js | 搜索、查看文档和追溯原始证据 |

`data-worker` 由现有 `indexer` 角色演进，不新增生产服务数量。它复用 PostgreSQL 的 `processing_outbox`，不引入新的消息基础设施。

首版明确不需要 Redis、Celery、Celery Beat、Qdrant、Kafka、Airflow、Spark、MongoDB 或独立模型服务。

### 3.2 单一处理入口

`data-worker` 按小批次循环执行：

1. 从 `processing_outbox` 原子领取 `pending` 或可重试的 `failed` 文档，并标记为 `processing`。
2. 从 `standard_documents.document_json` 读取标准文档。
3. 顺序执行清洗、特征提取、批内去重和质量评估。
4. 合格文档把完整处理结果写回同一条标准文档；被过滤文档保留原因和证据关系。
5. 由现有统一 Elasticsearch 投影代码写入 `qsou_documents`。
6. 成功后标记为 `indexed`；处理失败或索引失败标记为 `failed` 并记录阶段、次数和具体错误。

处理结果至少写回 `document_json.processing`：

- `processed_at` 与 `processing_version`
- `processed_content`，保留原始标准化 `title`、`content` 和 `content_hash`
- 摘要、关键词、分类和实体
- 质量评分、质量判断与过滤原因
- 原始 `raw_object_id`、文档身份和内容版本保持不变

首版只做稳定身份、内容哈希和批内规则去重；需要模型或全库向量相似度的近似去重属于后续能力。

处理代码不得另写 `qsou_news`、`qsou_announcements` 等平行索引，也不得直接把内存中的处理结果当成已持久化结果。PostgreSQL 成功保存处理结果后，Elasticsearch 才能消费该版本。

### 3.3 新数据与已有数据使用同一路径

- 新采集文档登记后自动产生 `pending` 状态，由 `data-worker` 处理。
- 已有标准文档通过同一个重排队入口回到 `pending`，不得调用另一套历史脚本。
- 已归档但未生成标准文档的证据不直接进入处理器；它们需要对应来源解析器先生成标准文档。
- 首版先用一个真实来源、一个受控批次闭环，再按来源和时间窗口逐批处理已有数据。

首版闭环不等于已有 6.8 GB 已全部转化。系统必须分别展示原始证据数、标准文档数以及各处理状态数量，不能用存档体积代替处理进度。

## 4. 首版运行状态

标准文档的处理状态为：

```text
pending
  → processing
      ├─ processed → indexed
      ├─ filtered
      └─ failed → pending（显式重试）
```

- `pending`：标准文档已经持久化，等待基础处理。
- `processing`：worker 已经领取，尚未产生可用终态。
- `processed`：处理结果已经写回 PostgreSQL，等待或正在投影全文索引。
- `indexed`：对应版本已在统一全文索引可见。
- `filtered`：文档未进入搜索，且保存了明确过滤原因。
- `failed`：保存失败阶段、错误和尝试次数，可以从同一输入重试。

worker 重启后必须能够继续领取未完成任务。状态更新和任务领取依赖 PostgreSQL，不依赖进程内内存或外部消息队列。

## 5. 组件职责

| 组件 | 主要职责 | 不应承担的职责 |
|---|---|---|
| 来源登记 | 定义来源身份、入口、覆盖、频率、权利和健康状态 | 保存正文或搜索索引 |
| 采集连接器 | 访问来源并生成采集上下文 | 决定事实真伪或覆盖失败 |
| 原始归档 | 保存响应、文件、响应头、时间、哈希和采集器版本 | 承担用户检索体验 |
| 规范化处理 | 提取字段、生成稳定身份、识别内容版本 | 覆盖或删除原始证据 |
| 基础处理 | 清洗、特征提取、批内去重、质量评估并持久化结果 | 自建第二套目录、队列或索引真相 |
| Elasticsearch | 全文搜索、过滤、聚合与排序 | 作为不可替代的唯一事实源 |
| 用户资产存储 | 收藏、订阅、标签、纠错和研究笔记 | 与可重建索引混存后被重建清除 |

## 6. 首版完成标准

首版完成必须用真实来源内容验证以下整条路径：

1. 采集器成功保存响应正文，并登记 `raw_object_id`、来源、时间和内容哈希。
2. 解析器生成标准文档，文档能够追溯到原始证据。
3. 文档自动进入 `pending`，无需人工复制文件或调用临时脚本。
4. worker 完成清洗、特征提取、去重和质量评估，完整结果可以从 PostgreSQL 重新读取。
5. 合格文档进入唯一的 `qsou_documents` 索引；过滤和失败文档不伪装成成功。
6. 用户在现有搜索页面输入真实查询能够命中文档，并能打开对应原始证据。
7. 对同一内容重复采集和重复处理不会制造重复活动版本或重复搜索结果。
8. worker 在处理中重启后，未完成文档能够继续处理或明确进入可重试失败状态。

验收结果至少记录本批次的原始证据数、标准文档数、处理成功数、过滤数、失败数、索引数，以及一条真实搜索和证据回看结果。数量不守恒或结果只能从日志看到时，均不算闭环。

## 7. 一致性规则

1. 原始对象写入使用确定性标识和幂等操作。
2. 规范化文档必须引用 `raw_object_id`、来源和处理版本。
3. 内容发生变化时创建新版本，不无记录覆盖旧版本。
4. PostgreSQL 处理结果与 Elasticsearch 使用同一 `canonical_document_id` 和 `content_version_id` 关联。
5. 索引写入失败不能删除已归档对象；重试必须可重复执行。
6. 删除或合规限制通过受审计的生命周期事件传播到各层。
7. 用户纠错和研究数据独立保存，不能在索引重建时丢失。

## 8. 后续扩展边界

首版闭环后再根据实际使用证据决定是否扩展：

- LLM 首先消费 Elasticsearch 返回的正文和证据引用，不要求 Qdrant。
- 只有固定研究问题证明关键词召回不足时，才评估 Elasticsearch 向量字段或独立向量库。
- Qdrant、嵌入模型和混合检索是可选语义召回能力，不得成为采集和基础处理链的依赖。
- 全量原始证据回放、主备对象存储、覆盖证明和灾难恢复继续作为后续完整性能力推进。
- 实体事件层、订阅和用户知识资产在基础文档稳定可用后接入。

长期“自主可控”的验收仍遵守[自主数据资产设计指导](./data-sovereignty-design-guidelines.md)；本文件的首版完成标准只用于确认采集和数据处理主链已经真实产生可用结果。
