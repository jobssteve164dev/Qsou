"""
新浪财经爬虫

采集新浪财经网站的新闻数据，支持JS渲染和高质量正文提取
"""

import scrapy
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any

from qsou_crawler.items import NewsArticleItem
import trafilatura


class SinaFinanceSpider(scrapy.Spider):
    name = "sina_finance"
    allowed_domains = ["finance.sina.com.cn", "sina.com.cn"]
    
    # 新浪财经新闻起始URL
    start_urls = [
        # 财经新闻首页
        "https://finance.sina.com.cn/roll/index.d.html?cid=56588&page=1",
        # 股票新闻
        "https://finance.sina.com.cn/stock/",
        # 基金新闻
        "https://finance.sina.com.cn/money/fund/",
        # 债券新闻
        "https://finance.sina.com.cn/money/bond/",
        # 宏观经济
        "https://finance.sina.com.cn/china/",
    ]
    
    custom_settings = {
        # 插件级定制设置
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "ROBOTSTXT_OBEY": True,
        # 禁用Redis调度器，使用默认调度器进行测试
        "SCHEDULER": "scrapy.core.scheduler.Scheduler",
        "DUPEFILTER_CLASS": "scrapy.dupefilters.RFPDupeFilter",
        # 修复Twisted引擎问题：使用默认reactor
        "TWISTED_REACTOR": "twisted.internet.selectreactor.SelectReactor",
        # 使用默认下载处理器
        "DOWNLOAD_HANDLERS": {
            'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
            'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
        },
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_urls = set()
        self.max_pages_per_domain = 3  # 每个域名最多爬取3页
        
    def start_requests(self):
        """生成初始请求"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'domain': urlparse(url).netloc,
                    'page': 1,
                    'start_url': url,
                },
                dont_filter=True
            )
    
    def parse(self, response):
        """解析新闻列表页面"""
        domain = response.meta['domain']
        page = response.meta['page']
        start_url = response.meta['start_url']
        
        self.logger.info(f"解析 {domain} 第 {page} 页: {response.url}")
        
        # 提取新闻链接
        news_links = self.extract_news_links(response)
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
                        meta={
                            'source': 'sina.com.cn',
                            'playwright': True  # 启用JS渲染
                        }
                    )
                else:
                    self.logger.debug(f"跳过无效链接: {full_url}")
        
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
                        'start_url': start_url,
                        'playwright': True
                    },
                    dont_filter=True
                )
    
    def extract_news_links(self, response) -> List[str]:
        """提取新闻链接"""
        # 新浪财经新闻链接选择器
        news_selectors = [
            'a[href*="/news/"]::attr(href)',
            'a[href*="finance.sina.com.cn"]::attr(href)',
            '.news-item a::attr(href)',
            '.list-item a::attr(href)',
            '.item a::attr(href)',
            'h3 a::attr(href)',
            'h4 a::attr(href)',
            '.title a::attr(href)',
        ]
        
        news_links = []
        for selector in news_selectors:
            links = response.css(selector).getall()
            news_links.extend(links)
        
        # 去重并过滤
        unique_links = list(set(news_links))
        return [link for link in unique_links if link and self.is_valid_news_url(urljoin(response.url, link))]
    
    def parse_news_detail(self, response):
        """解析新闻详情页面"""
        try:
            self.logger.info(f"解析新闻详情: {response.url}")
            
            # 提取标题
            title = self.extract_title(response)
            if not title or len(title.strip()) < 5:
                self.logger.warning(f"标题过短或为空: {response.url}")
                return
            
            # 提取内容 - 优先使用trafilatura
            content = self.extract_content_with_trafilatura(response)
            if not content or len(content.strip()) < 50:
                # 回退到CSS选择器
                content = self.extract_content_with_css(response)
                if not content or len(content.strip()) < 50:
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
            item['source'] = response.meta.get('source', 'sina.com.cn')
            item['published_at'] = publish_time
            item['author'] = author
            item['tags'] = tags
            item['crawled_at'] = datetime.now().isoformat()
            item['content_length'] = len(content)
            item['category'] = self.classify_news_category(title, content)
            item['summary'] = self.generate_summary(content)
            
            # 数据质量检查
            if self.validate_news_item(item):
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
            '.main-title::text',
            'title::text'
        ]
        
        for selector in title_selectors:
            title = response.css(selector).get()
            if title:
                return title.strip()
        
        return ""
    
    def extract_content_with_trafilatura(self, response) -> str:
        """使用trafilatura提取正文"""
        try:
            extracted = trafilatura.extract(
                response.text, 
                include_comments=False, 
                include_tables=False,
                include_links=False
            )
            if extracted:
                return extracted.strip()
        except Exception as e:
            self.logger.warning(f"trafilatura提取失败: {str(e)}")
        
        return ""
    
    def extract_content_with_css(self, response) -> str:
        """使用CSS选择器提取内容"""
        content_selectors = [
            '.article-content p::text',
            '.news-content p::text',
            '.content p::text',
            '.article-body p::text',
            '.post-content p::text',
            'article p::text',
            '.main-content p::text',
            '.text p::text',
            '.article p::text',
            '.news p::text',
            'p::text'  # 通用段落选择器
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
            '[datetime]::attr(datetime)',
            '.date::text',
            '.pub-time::text'
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
            '.writer::text',
            '.reporter::text'
        ]
        
        for selector in author_selectors:
            author = response.css(selector).get()
            if author:
                return author.strip()
        
        return "新浪财经"
    
    def extract_tags(self, response) -> List[str]:
        """提取标签"""
        tag_selectors = [
            '.tags a::text',
            '.tag::text',
            '.keywords::text',
            '.category::text',
            '.label::text'
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
                    # 简单的日期验证
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
        stock_keywords = ['股票', '股价', '涨停', '跌停', 'a股', '港股', '美股', '上市', 'ipo', '交易']
        if any(keyword in text for keyword in stock_keywords):
            return '股票'
        
        # 基金相关关键词
        fund_keywords = ['基金', 'etf', '公募', '私募', '净值', '申购', '赎回', '基金经理']
        if any(keyword in text for keyword in fund_keywords):
            return '基金'
        
        # 债券相关关键词
        bond_keywords = ['债券', '国债', '企业债', '可转债', '收益率', '债券基金']
        if any(keyword in text for keyword in bond_keywords):
            return '债券'
        
        # 宏观经济关键词
        macro_keywords = ['gdp', '通胀', '利率', '汇率', '央行', '货币政策', '经济数据', 'cpi', 'ppi']
        if any(keyword in text for keyword in macro_keywords):
            return '宏观经济'
        
        # 行业分析关键词
        industry_keywords = ['行业', '板块', '龙头', '产业链', '供需', '产能', '市场']
        if any(keyword in text for keyword in industry_keywords):
            return '行业分析'
        
        return '综合财经'
    
    def generate_summary(self, content: str) -> str:
        """生成摘要"""
        if not content:
            return ""
        
        # 简单摘要：取前160个字符
        summary = content[:160]
        if len(content) > 160:
            summary += "..."
        
        return summary.strip()
    
    def is_valid_news_url(self, url: str) -> bool:
        """检查URL是否为有效的新闻链接"""
        if not url:
            return False
        
        # 排除非新闻链接 - 更严格的过滤
        exclude_patterns = [
            r'/video/', r'/photo/', r'/gallery/', r'/live/', r'/comment/',
            r'/user/', r'/login', r'/register', r'/search',
            r'\.(jpg|jpeg|png|gif|pdf|doc|docx|xls|xlsx)$',
            r'/stock/go\.php',  # 排除股票工具页面
            r'/money/globalindex',  # 排除全球指数页面
            r'/stock/message/',  # 排除股票消息页面
            r'/stock/estate/',  # 排除房地产页面
            r'/stock/ask',  # 排除问答页面
            r'/stock/map',  # 排除地图页面
            r'/stock/sl/',  # 排除股票列表页面
            r'/stock/hangqing/',  # 排除行情页面
            r'/stock/usstock/sector',  # 排除美股板块页面
            r'/stock/thirdmarket/',  # 排除三板市场页面
            r'/stock/quanshang/',  # 排除券商页面
            r'/stock/jyts/',  # 排除交易提示页面
            r'/stock/newstock/',  # 排除新股页面
            r'/fund/$',  # 排除基金首页
            r'/money/future/',  # 排除期货页面
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # 必须包含新闻相关路径 - 更精确的匹配
        news_patterns = [
            r'/stock/.*\d{4}-\d{2}-\d{2}.*\.shtml$',  # 股票新闻文章
            r'/money/fund/.*\d{4}-\d{2}-\d{2}.*\.shtml$',  # 基金新闻文章
            r'/money/bond/.*\d{4}-\d{2}-\d{2}.*\.shtml$',  # 债券新闻文章
            r'/china/.*\d{4}-\d{2}-\d{2}.*\.shtml$',  # 宏观经济新闻文章
            r'/roll/.*\d{4}-\d{2}-\d{2}.*\.shtml$',  # 滚动新闻文章
        ]
        
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in news_patterns)
    
    def validate_news_item(self, item: NewsArticleItem) -> bool:
        """验证新闻项目的数据质量"""
        # 检查必要字段
        if not item.get('title') or not item.get('content'):
            return False
        
        # 检查内容长度 - 降低要求
        content = item.get('content', '')
        if len(content) < 50:
            return False
        
        # 检查标题长度 - 降低要求
        title = item.get('title', '')
        if len(title) < 5:
            return False
        
        # 检查是否为重复内容
        if self.is_duplicate_content(title, content):
            return False
        
        # 检查是否是纯导航页面
        if content.count('|') > 20:  # 导航页面通常有很多分隔符
            return False
        
        return True
    
    def is_duplicate_content(self, title: str, content: str) -> bool:
        """检查是否为重复内容"""
        # 简单的重复检测逻辑
        content_hash = hash(title + content[:200])  # 使用标题和前200字符的哈希
        return content_hash in getattr(self, '_content_hashes', set())
    
    def get_next_page_url(self, response, start_url: str, page: int) -> str:
        """获取下一页URL"""
        domain = urlparse(start_url).netloc
        
        if 'finance.sina.com.cn' in domain:
            # 新浪财经分页URL格式
            if 'roll/index.d.html' in start_url:
                return f"{start_url}&page={page}"
            else:
                return f"{start_url}?page={page}"
        
        return None