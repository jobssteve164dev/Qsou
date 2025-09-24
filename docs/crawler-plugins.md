# 爬虫插件开发与安装指南

本指南说明如何为 Qsou 数据采集层编写与安装“插件化”爬虫。

## 1. 目标与能力

- 可插拔：将插件包放入 `crawler/plugins/`（或通过 Python entry point 安装）即可自动被发现。
- 无侵入：无需修改核心代码与 `settings.py` 的 `SPIDER_MODULES`。
- 可验证：`cd crawler && scrapy list` 能显示插件 Spider 名称；`run_crawler.py` 可动态列出并启动。

## 2. 插件目录结构（目录扫描方式）

```
crawler/
  plugins/
    your_plugin_pkg/
      __init__.py
      spiders/
        __init__.py
        your_spider.py
```

- `your_spider.py` 中定义标准 Scrapy Spider 类，并设置唯一的 `name`。
- 插件 Spider 输出的 `Item` 字段应与 `qsou_crawler.items` 中定义的结构对齐，例如 `NewsArticleItem`。

最小示例：

```python
# crawler/plugins/example_news_plugin/spiders/example_yicai_spider.py
import scrapy
from qsou_crawler.items import NewsArticleItem

class ExampleYicaiSpider(scrapy.Spider):
    name = "example_yicai"
    allowed_domains = ["yicai.com"]
    start_urls = ["https://www.yicai.com/news/"]

    def parse(self, response):
        for href in response.css(".m-title a::attr(href)").getall():
            yield response.follow(href, callback=self.parse_article)

    def parse_article(self, response):
        item = NewsArticleItem()
        item["title"] = response.css("title::text").get() or ""
        content_parts = response.css("article p::text, .article p::text").getall()
        item["content"] = "\n".join([p.strip() for p in content_parts if p and p.strip()])
        item["summary"] = (item["content"] or "")[:160]
        item["source"] = "yicai.com"
        item["url"] = response.url
        yield item
```

## 3. 通过 Entry Point 的方式分发（可选）

若希望以 `pip install` 分发插件，可在你的独立 Python 包内声明 entry point：

- entry point group 固定为：`qsou_crawler.plugins`
- entry point value 指向你的包的 `spiders` 模块，例如：`your_pkg.spiders`

`pyproject.toml` 示例：

```toml
[project.entry-points."qsou_crawler.plugins"]
news_plugin = "your_pkg.spiders"
```

安装后运行 `scrapy list` 即可被发现。

## 4. 运行与验证

- 列出所有 Spider（含插件）：
  - `cd crawler && scrapy list`
- 启动交互式运行器：
  - `python crawler/run_crawler.py`
  - 直接输入爬虫名或选择序号均可

## 5. 配置与行为说明

- 自定义加载器：`qsou_crawler.plugin_loader.PluginSpiderLoader`
- 目录扫描基准：`CRAWLER_PLUGIN_DIRS = ["plugins"]`（相对 `crawler/` 根目录）
- Entry point 组名：`CRAWLER_PLUGIN_ENTRYPOINT_GROUP = 'qsou_crawler.plugins'`
- 插件内部可通过 `custom_settings` 微调参数（建议小范围覆盖，避免与全局冲突）。

## 6. 最佳实践

- 与核心 Item 对齐，确保数据在 `pipelines` 中能被验证、去重并提交到处理系统。
- 合理控制抓取速率，遵守 `robots.txt` 与站点条款。
- 对接新增站点时，优先以插件形式扩展，避免修改核心仓库。

## 7. 故障排查

- 插件未被发现：
  - 目录结构是否正确？`spiders/__init__.py` 是否存在？
  - `scrapy list` 是否在 `crawler/` 目录执行？
- 导入错误：
  - 插件 Spider 内是否引用了不存在的依赖？
  - `from qsou_crawler.items import NewsArticleItem` 是否可导入？

```bash
# 快速验证
cd crawler
scrapy list | cat
scrapy crawl example_yicai -L INFO -s LOG_FILE=logs/scrapy.log
```

