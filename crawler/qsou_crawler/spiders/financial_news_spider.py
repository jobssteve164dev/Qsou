"""
财经新闻爬虫 - 采集真实财经新闻数据

遵循法律合规要求，仅采集公开可访问的财经新闻
"""

import scrapy
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any
import logging

from qsou_crawler.items import NewsArticleItem


class FinancialNewsSpider(scrapy.Spider):
    name = 'financial_news'
    allowed_domains = [
        'eastmoney.com',
        'sina.com.cn', 
        '163.com',
        'sohu.com',
        'caijing.com.cn',
        'yicai.com'
    ]
    
    # 财经新闻起始URL
    start_urls = [
        # 东方财富财经新闻
        'https://finance.eastmoney.com/news/cjxw.html',
        'https://finance.eastmoney.com/news/cgsxw.html',
        'https://finance.eastmoney.com/news/cjdd.html',
        
        # 新浪财经
        'https://finance.sina.com.cn/roll/index.d.html?cid=56588&page=1',
        'https://finance.sina.com.cn/stock/',
        
        # 网易财经
        'https://money.163.com/special/002557S6/rss_newstop.xml',
        'https://money.163.com/',
        
        # 搜狐财经
        'https://business.sohu.com/',
        
        # 财经网
        'https://www.caijing.com.cn/',
        
        # 第一财经
        'https://www.yicai.com/news/'
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'ROBOTSTXT_OBEY': True,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        self.processed_urls = set()
        self.max_pages_per_domain = 5  # 每个域名最多爬取5页
        
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
        
        # 根据域名选择不同的解析策略
        if 'eastmoney.com' in domain:
            yield from self.parse_eastmoney(response)
        elif 'sina.com.cn' in domain:
            yield from self.parse_sina(response)
        elif '163.com' in domain:
            yield from self.parse_163(response)
        elif 'sohu.com' in domain:
            yield from self.parse_sohu(response)
        elif 'caijing.com.cn' in domain:
            yield from self.parse_caijing(response)
        elif 'yicai.com' in domain:
            yield from self.parse_yicai(response)
        
        # 继续爬取下一页
        if page < self.max_pages_per_domain:
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
    
    def parse_eastmoney(self, response):
        """解析东方财富新闻"""
        # 新闻链接选择器
        news_links = response.css('div.news-item a::attr(href)').getall()
        news_links.extend(response.css('a[href*="/news/"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'eastmoney.com'}
                    )
    
    def parse_sina(self, response):
        """解析新浪财经新闻"""
        news_links = response.css('a[href*="/news/"]::attr(href)').getall()
        news_links.extend(response.css('a[href*="finance.sina.com.cn"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'sina.com.cn'}
                    )
    
    def parse_163(self, response):
        """解析网易财经新闻"""
        news_links = response.css('a[href*="/money/"]::attr(href)').getall()
        news_links.extend(response.css('a[href*="money.163.com"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': '163.com'}
                    )
    
    def parse_sohu(self, response):
        """解析搜狐财经新闻"""
        news_links = response.css('a[href*="/business/"]::attr(href)').getall()
        news_links.extend(response.css('a[href*="business.sohu.com"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'sohu.com'}
                    )
    
    def parse_caijing(self, response):
        """解析财经网新闻"""
        news_links = response.css('a[href*="/news/"]::attr(href)').getall()
        news_links.extend(response.css('a[href*="caijing.com.cn"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'caijing.com.cn'}
                    )
    
    def parse_yicai(self, response):
        """解析第一财经新闻"""
        news_links = response.css('a[href*="/news/"]::attr(href)').getall()
        news_links.extend(response.css('a[href*="yicai.com"]::attr(href)').getall())
        
        for link in news_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_news_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_news_detail,
                        meta={'source': 'yicai.com'}
                    )
    
    def parse_news_detail(self, response):
        """解析新闻详情页面"""
        try:
            # 提取标题
            title = self.extract_title(response)
            if not title or len(title.strip()) < 10:
                self.logger.warning(f"标题过短或为空: {response.url}")
                return
            
            # 提取内容
            content = self.extract_content(response)
            if not content or len(content.strip()) < 100:
                self.logger.warning(f"内容过短或为空: {response.url}")
                return
            
            # 提取发布时间
            publish_time = self.extract_publish_time(response)
            
            # 提取作者
            author = self.extract_author(response)
            
            # 提取标签/分类
            tags = self.extract_tags(response)
            
            # 创建新闻项目
            item = NewsArticleItem()
            item['title'] = title.strip()
            item['content'] = content.strip()
            item['url'] = response.url
            item['source'] = response.meta.get('source', 'unknown')
            item['publish_time'] = publish_time
            item['author'] = author
            item['tags'] = tags
            item['crawl_time'] = datetime.now().isoformat()
            item['content_length'] = len(content)
            item['category'] = self.classify_news_category(title, content)
            
            # 数据质量检查
            if self.validate_news_item(item):
                yield item
            else:
                self.logger.warning(f"数据质量检查失败: {response.url}")
                
        except Exception as e:
            self.logger.error(f"解析新闻详情失败 {response.url}: {str(e)}")
    
    def extract_title(self, response) -> str:
        """提取新闻标题"""
        # 通用标题选择器
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
        # 通用内容选择器
        content_selectors = [
            '.article-content p::text',
            '.news-content p::text',
            '.content p::text',
            '.article-body p::text',
            '.post-content p::text',
            'article p::text',
            '.main-content p::text'
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
        # 通用时间选择器
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
        # 匹配常见的日期格式
        date_patterns = [
            r'(\d{4})/(\d{2})/(\d{2})',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})(\d{2})(\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                year, month, day = match.groups()
                return f"{year}-{month}-{day}T00:00:00"
        
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
            r'/video/',
            r'/photo/',
            r'/gallery/',
            r'/live/',
            r'/comment/',
            r'/user/',
            r'/login',
            r'/register',
            r'\.(jpg|jpeg|png|gif|pdf|doc|docx|xls|xlsx)$'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # 必须包含新闻相关路径
        news_patterns = [
            r'/news/',
            r'/finance/',
            r'/stock/',
            r'/money/',
            r'/business/'
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
        
        # 检查是否为重复内容
        if self.is_duplicate_content(item.get('title', ''), item.get('content', '')):
            return False
        
        return True
    
    def is_duplicate_content(self, title: str, content: str) -> bool:
        """检查是否为重复内容"""
        # 简单的重复检测逻辑
        # 在实际应用中可以使用更复杂的去重算法
        content_hash = hash(title + content[:200])  # 使用标题和前200字符的哈希
        return content_hash in getattr(self, '_content_hashes', set())
    
    def get_next_page_url(self, response, start_url: str, page: int) -> str:
        """获取下一页URL"""
        domain = urlparse(start_url).netloc
        
        if 'eastmoney.com' in domain:
            return f"{start_url}?page={page}"
        elif 'sina.com.cn' in domain:
            return f"{start_url}&page={page}"
        elif '163.com' in domain:
            return f"{start_url}?page={page}"
        elif 'sohu.com' in domain:
            return f"{start_url}?page={page}"
        elif 'caijing.com.cn' in domain:
            return f"{start_url}?page={page}"
        elif 'yicai.com' in domain:
            return f"{start_url}?page={page}"
        
        return None
