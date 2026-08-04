# Qsou 数据流架构

> 文档定位：描述自主数据资产的目标数据流，并标明当前代码与目标之间的差距。
>
> 设计权威：[自主数据资产设计指导](./data-sovereignty-design-guidelines.md)。

## 1. 架构结论

Qsou 的事实权威必须是来源登记与不可变原始证据，而不是 Elasticsearch 或 Qdrant。全文索引、向量索引和模型结果都应能够从已保存数据重建。

目标顺序：

```text
来源登记
  → 采集与原始证据归档
  → 规范化、身份与版本识别
  → 实体/事件等领域派生
  → Elasticsearch 全文索引、Qdrant 向量索引
  → 搜索、订阅、证据查看、分析与导出
```

## 2. 当前实现（Observed in code）

当前主要代码路径是：

```text
Scrapy Spider
  → crawler/qsou_crawler/pipelines/data_processing_pipeline.py
  → data-processor.tasks.process_crawled_data
  → data-processor.tasks.update_search_index
  → Elasticsearch
  → data-processor.tasks.generate_embeddings
  → Qdrant
```

- `crawler/qsou_crawler/` 负责 Spider、插件加载、字段验证、去重和任务提交。
- `data-processor/tasks.py` 负责数据处理、Elasticsearch 索引和向量任务。
- `api-gateway/app/services/elasticsearch_service.py` 提供全文检索。
- `api-gateway/app/services/qdrant_service.py` 提供语义检索。

这条路径已经建立了“先全文索引、后向量索引”的服务顺序，但尚不能证明自主数据资产已经闭环。

## 3. 当前差距（Inference based on code audit）

本次代码审计尚未发现以下完整能力：

- 在解析和任务确认之前持久化 HTTP 响应、附件与采集上下文的不可变原始归档。
- 统一的来源登记、覆盖契约、权利状态和来源健康模型。
- `source_published_at`、`first_seen_at`、`fetched_at`、`processed_at`、`indexed_at` 的完整时间语义。
- 逻辑文档、来源文档、内容版本和原始对象之间的稳定身份关系。
- 不访问外部来源即可按时间窗口或解析器版本重放数据。
- 从原始证据重建标准文档、Elasticsearch 与 Qdrant 的全链路恢复演练。

因此，当前 Elasticsearch 是主要在线全文存储，但不应继续被定义为长期唯一主存储。索引中的数据量也不能单独作为来源完整性的证明。

## 4. 目标组件职责

| 组件 | 主要职责 | 不应承担的职责 |
|---|---|---|
| 来源登记 | 定义来源身份、入口、覆盖、频率、权利和健康状态 | 保存正文或搜索索引 |
| 采集连接器 | 访问来源并生成采集上下文 | 决定事实真伪或覆盖失败 |
| 原始归档 | 保存响应、文件、响应头、时间、哈希和采集器版本 | 承担用户检索体验 |
| 规范化处理 | 提取字段、生成稳定身份、识别内容版本 | 覆盖或删除原始证据 |
| 实体/事件层 | 建立公司、证券、人物与事件关系 | 把模型推断伪装成来源事实 |
| Elasticsearch | 全文搜索、过滤、聚合与排序 | 作为不可替代的唯一事实源 |
| Qdrant | 语义召回和相似度检索 | 保存唯一正文或唯一版本记录 |
| 用户资产存储 | 收藏、订阅、标签、纠错和研究笔记 | 与可重建索引混存后被重建清除 |

## 5. 关键状态流

一份采集对象至少经历以下状态：

```text
discovered
  → fetched
  → archived
  → normalized
  → indexed
  → enriched
```

- `fetched` 不等于成功：只有进入 `archived`，原始证据才被系统掌握。
- `archived` 后的处理失败应从本地回放，不应立即重新抓取来源。
- `indexed` 只表示可搜索，不表示覆盖完整或模型处理完成。
- 任一失败状态必须记录输入对象、失败阶段、错误原因、尝试次数和下一次处理动作。

## 6. 一致性规则

1. 原始对象写入使用确定性标识和幂等操作。
2. 规范化文档必须引用 `raw_object_id`、来源和处理版本。
3. 内容发生变化时创建新版本，不无记录覆盖旧版本。
4. Elasticsearch 与 Qdrant 使用同一 `canonical_document_id` 和 `content_version_id` 关联。
5. 索引写入失败不能删除已归档对象；重试必须可重复执行。
6. 删除或合规限制通过受审计的生命周期事件传播到各层。
7. 用户纠错和研究数据独立保存，不能在索引重建时丢失。

## 7. 运行与验收

数据流完成不能只看任务返回成功。至少验证：

- 正式文档是否 100% 关联原始对象。
- 来源窗口是否存在分页、编号或时间缺口。
- 最新来源时间与本地首次发现时间的延迟。
- 各阶段输入数、成功数、失败数和死信数是否守恒。
- 能否选择一段原始归档，在不访问来源的情况下重新生成标准文档与两个索引。
- 重建前后文档数量、内容哈希、版本关系和关键查询是否一致。

只有原始证据、来源覆盖、处理可追溯和恢复演练同时成立，才能把该数据流称为自主可控。
