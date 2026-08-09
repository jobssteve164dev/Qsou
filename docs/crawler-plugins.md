# 来源适配器开发与升级指南

QSou 的采集扩展点是“来源适配器”，不是任意 Spider 插件。每个启用来源必须在 `config/sources.json` 中登记，并且在 `AdapterRegistry` 中恰好对应一个有版本的实现。没有登记、实现或契约测试的代码不能进入生产调度。

完整架构、状态口径和升级流程见[来源适配器网络设计](./source-adapter-network.md)。

## 新增一个来源

1. 在 `config/sources.json` 登记来源身份、域名、入口、文档类型、频率、游标策略、权利状态、`adapter_id` 和 `adapter_version`。
2. 在 `crawler/qsou_crawler/adapters/` 新增一个 `SourceAdapter` 子类。
3. 实现入口请求、详情发现规则；只有接口形状特殊时才覆盖 `discover`。
4. 在 `crawler/qsou_crawler/adapters/registry.py` 注册适配器。
5. 在 `tests/test_source_adapters.py` 增加该来源的固定响应样本和契约测试。
6. 验证一轮真实运行至少产生入口成功数、详情发现数、详情获取数、文档产出数和证据归档数。
7. 确认前台只按真实终态显示正常、需要检查或失败。

最小 HTML 新闻适配器：

```python
from .base import NewsHTMLAdapter


class ExampleAdapter(NewsHTMLAdapter):
    source_id = "example"
    adapter_id = "example-news"
    version = "1.0.0"
    link_patterns = (r"example\.com/news/\d+\.html(?:$|\?)",)
```

如果来源使用 JSON 公告接口，应覆盖 `initial_requests` 和 `discover`，返回 `DocumentReference`。详情仍由统一 Spider 下载、归档和解析，适配器不能绕开原始证据中间件直接写标准文档。

## 升级一个适配器

适配器升级必须是一个原子变更：

- 同时修改来源登记中的 `adapter_version` 和实现类的 `version`。
- 增加能复现旧问题的响应样本，再修改解析代码。
- 保留原始证据和历史标准文档；不得用新解析结果覆盖历史内容。
- 新版本首轮仍回看最近列表窗口，由 `source_document_id` 和内容版本去重，避免升级切换造成时间缺口。
- 只有入口成功且合格详情文档已经实际登记入库，运行终态才是 `healthy`；入口可达但零入库是 `degraded`。
- 发布后核对该来源的详情发现、详情获取、文档产出和失败数，不能只看进程退出码。

## 统一管理边界

- 来源配置权威：`config/sources.json`。
- 实现注册权威：`crawler/qsou_crawler/adapters/registry.py`。
- 调度权威：`crawler/run_schedule.py`，按每个来源的 `schedule` 独立判断是否到期。
- 运行事实权威：SQLite `adapter_runs` 和 `source_cursors`。
- 用户可见状态：认证后的 `/api/v1/data/sources`、`/api/v1/data/adapter-runs` 和“数据资产”页面。
- 逐源操作入口：`POST /api/v1/data/adapter-runs/{source_id}/trigger`；持久请求由同一调度器认领，禁用或待授权来源不能触发。

旧 `crawler/plugins/` 与按 Spider 名称扫描的加载器不再属于生产路径。保留的历史代码不能被当作正式适配器，也不会被统一调度器发现。

生产 Scrapy 设置只加载统一 `source_adapter`，中间件只负责解析前原始证据归档和证据身份关联。来源级请求头应写在相应适配器的 `RequestSpec` 中；不得通过随机 UA、代理或反检测中间件改变全网行为，也不得用标题级内存去重替代来源文档身份和内容版本。
