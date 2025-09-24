import scrapy
from qsou_crawler.items import NewsArticleItem
import trafilatura


class ExampleYicaiSpider(scrapy.Spider):
    name = "example_yicai"
    allowed_domains = ["yicai.com"]
    start_urls = [
        "https://www.yicai.com/news/"
    ]

    custom_settings = {
        # 可选：插件级定制设置（示例）
        "DOWNLOAD_DELAY": 2,
    }

    def parse(self, response):
        # 抽取新闻列表链接（示例选择器，后续可按实际页面优化）
        for href in response.css(".m-title a::attr(href)").getall():
            url = response.urljoin(href)
            yield scrapy.Request(url, callback=self.parse_article, meta={"playwright": True})

    def parse_article(self, response):
        item = NewsArticleItem()
        item["title"] = response.css("title::text").get() or ""
        # 使用 trafilatura 抽取正文作为优先方案
        extracted = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        if extracted:
            item["content"] = extracted.strip()
        else:
            # 回退：CSS 选择器
            content_parts = response.css("article p::text, .article p::text").getall()
            item["content"] = "\n".join([part.strip() for part in content_parts if part and part.strip()])
        item["summary"] = (item["content"] or "")[:160]
        item["source"] = "yicai.com"
        item["url"] = response.url
        yield item



