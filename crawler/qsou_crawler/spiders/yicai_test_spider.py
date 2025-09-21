"""
第一财经测试爬虫 - 专门用于调试第一财经网站
"""

import scrapy
import logging
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Any
import re

from qsou_crawler.items import NewsArticleItem


class YicaiTestSpider(scrapy.Spider):
    """第一财经测试爬虫"""
    
    name = 'yicai_test'
    allowed_domains = ['yicai.com']
    start_urls = [
        'https://www.yicai.com/news/'
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'ROBOTSTXT_OBEY': True,
        'LOG_LEVEL': 'INFO',
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_urls = set()
        self.max_news_pages = 3  # 限制爬取页面数量，用于测试
        
    def start_requests(self):
        """生成初始请求"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'domain': urlparse(url).netloc,
                    'page': 1,
                    'start_url': url
                },
                dont_filter=True
            )
    
    def parse(self, response):
        """解析新闻列表页面"""
        domain = response.meta['domain']
        page = response.meta['page']
        start_url = response.meta['start_url']
        
        self.logger.info(f"解析 {domain} 第 {page} 页: {response.url}")
        
        # 解析第一财经新闻链接
        yield from self.parse_yicai(response)
        
        # 继续爬取下一页（限制数量）
        if page < self.max_news_pages:
            next_page_url = self.get_next_page_url(response, start_url, page + 1)
            if next_page_url:
                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse,
                    meta={
                        'domain': domain,
                        'page': page + 1,
                        'start_url': start_url
                    },
                    dont_filter=True
                )
    
    def parse_yicai(self, response):
        """解析第一财经新闻"""
        self.logger.info(f"开始解析第一财经页面: {response.url}")
        
        # 使用爬虫的选择器
        news_links = response.css('a[href*="/news/"]::attr(href)').getall()
        self.logger.info(f"找到 {len(news_links)} 个新闻链接")
        
        for i, link in enumerate(news_links):
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    self.logger.info(f"处理新闻链接 {i+1}: {full_url}")
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'yicai.com'}
                    )
                else:
                    self.logger.debug(f"跳过无效链接: {full_url}")
    
    def parse_news_detail(self, response):
        """解析新闻详情页面"""
        try:
            self.logger.info(f"解析新闻详情: {response.url}")
            
            # 提取标题
            title = self.extract_title(response)
            if not title or len(title.strip()) < 5:
                self.logger.warning(f"标题过短或为空: {response.url}")
                return
            
            # 提取内容
            content = self.extract_content(response)
            if not content or len(content.strip()) < 50:
                self.logger.warning(f"内容过短或为空: {response.url}")
                return
            
            # 提取其他信息
            publish_time = self.extract_publish_time(response)
            author = self.extract_author(response)
            tags = self.extract_tags(response)
            
            # 创建新闻项目
            item = NewsArticleItem()
            item['title'] = title.strip()
            item['content'] = content.strip()
            item['url'] = response.url
            item['source'] = response.meta.get('source', 'yicai.com')
            item['published_at'] = publish_time
            item['author'] = author
            item['tags'] = tags
            item['crawled_at'] = datetime.now().isoformat()
            item['content_length'] = len(content)
            item['category'] = self.classify_news_category(title, content)
            
            # 数据质量检查
            if self.validate_news_item(item):
                self.logger.info(f"成功提取新闻: {title[:50]}...")
                yield item
            else:
                self.logger.warning(f"数据质量检查失败: {response.url}")
                
        except Exception as e:
            self.logger.error(f"解析新闻详情失败 {response.url}: {str(e)}")
    
    def extract_title(self, response) -> str:
        """提取新闻标题"""
        title_selectors = [
            'h1::text',
            'h1.title::text',
            '.title h1::text',
            '.article-title::text',
            '.news-title::text',
            'title::text'
        ]
        
        for selector in title_selectors:
            title = response.css(selector).get()
            if title:
                return title.strip()
        
        return ""
    
    def extract_content(self, response) -> str:
        """提取新闻内容"""
        content_selectors = [
            '.article-content p::text',
            '.news-content p::text',
            '.content p::text',
            '.article-body p::text',
            '.post-content p::text',
            'article p::text',
            '.main-content p::text',
            'p::text',  # 通用段落选择器
            '.text p::text',
            '.article p::text',
            '.news p::text'
        ]
        
        content_parts = []
        for selector in content_selectors:
            parts = response.css(selector).getall()
            if parts:
                content_parts.extend(parts)
                break
        
        if not content_parts:
            # 备用方案：提取所有段落文本
            content_parts = response.css('p::text').getall()
        
        # 清理和合并内容
        content = ' '.join([part.strip() for part in content_parts if part.strip()])
        
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        
        return content
    
    def extract_publish_time(self, response) -> str:
        """提取发布时间"""
        time_selectors = [
            '.publish-time::text',
            '.article-time::text',
            '.news-time::text',
            '.time::text',
            'time::text',
            '[datetime]::attr(datetime)'
        ]
        
        for selector in time_selectors:
            time_text = response.css(selector).get()
            if time_text:
                return time_text.strip()
        
        # 从URL中提取时间（如果包含日期）
        url_time = self.extract_time_from_url(response.url)
        if url_time:
            return url_time
        
        # 默认返回当前时间
        return datetime.now().isoformat()
    
    def extract_author(self, response) -> str:
        """提取作者"""
        author_selectors = [
            '.author::text',
            '.article-author::text',
            '.news-author::text',
            '.byline::text',
            '.writer::text'
        ]
        
        for selector in author_selectors:
            author = response.css(selector).get()
            if author:
                return author.strip()
        
        return "未知"
    
    def extract_tags(self, response) -> List[str]:
        """提取标签"""
        tag_selectors = [
            '.tags a::text',
            '.tag::text',
            '.keywords::text',
            '.category::text'
        ]
        
        tags = []
        for selector in tag_selectors:
            tag_list = response.css(selector).getall()
            tags.extend([tag.strip() for tag in tag_list if tag.strip()])
        
        return list(set(tags))[:10]  # 最多10个标签
    
    def extract_time_from_url(self, url: str) -> str:
        """从URL中提取时间"""
        date_patterns = [
            r'(\d{4})/(\d{2})/(\d{2})',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})(\d{2})(\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                year, month, day = match.groups()
                try:
                    if len(year) == 4 and len(month) == 2 and len(day) == 2:
                        if 2000 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                            return f"{year}-{month}-{day}T00:00:00"
                except ValueError:
                    continue
        
        return ""
    
    def classify_news_category(self, title: str, content: str) -> str:
        """根据标题和内容分类新闻"""
        text = (title + " " + content).lower()
        
        # 股票相关关键词
        stock_keywords = ['股票', '股价', '涨停', '跌停', 'a股', '港股', '美股', '上市', 'ipo']
        if any(keyword in text for keyword in stock_keywords):
            return '股票'
        
        # 基金相关关键词
        fund_keywords = ['基金', 'etf', '公募', '私募', '净值', '申购', '赎回']
        if any(keyword in text for keyword in fund_keywords):
            return '基金'
        
        # 债券相关关键词
        bond_keywords = ['债券', '国债', '企业债', '可转债', '收益率']
        if any(keyword in text for keyword in bond_keywords):
            return '债券'
        
        # 宏观经济关键词
        macro_keywords = ['gdp', '通胀', '利率', '汇率', '央行', '货币政策', '经济数据']
        if any(keyword in text for keyword in macro_keywords):
            return '宏观经济'
        
        # 行业分析关键词
        industry_keywords = ['行业', '板块', '龙头', '产业链', '供需']
        if any(keyword in text for keyword in industry_keywords):
            return '行业分析'
        
        return '综合财经'
    
    def is_valid_news_url(self, url: str) -> bool:
        """检查URL是否为有效的新闻链接"""
        if not url:
            return False
        
        # 排除非新闻链接
        exclude_patterns = [
            r'/video/', r'/photo/', r'/gallery/', r'/live/',
            r'/comment/', r'/user/', r'/login', r'/register',
            r'\.(jpg|jpeg|png|gif|pdf|doc|docx|xls|xlsx)$'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # 必须包含新闻相关路径
        news_patterns = [
            r'/news/', r'/finance/', r'/stock/', r'/money/', r'/business/'
        ]
        
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in news_patterns)
    
    def validate_news_item(self, item: NewsArticleItem) -> bool:
        """验证新闻项目的数据质量"""
        # 检查必要字段
        if not item.get('title') or not item.get('content'):
            return False
        
        # 检查内容长度
        if len(item.get('content', '')) < 100:
            return False
        
        # 检查标题长度
        if len(item.get('title', '')) < 10:
            return False
        
        return True
    
    def get_next_page_url(self, response, start_url: str, page: int) -> str:
        """获取下一页URL"""
        if 'yicai.com' in urlparse(start_url).netloc:
            return f"{start_url}?page={page}"
        
        return None
