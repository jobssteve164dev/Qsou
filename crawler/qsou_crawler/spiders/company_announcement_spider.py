"""
公司公告爬虫 - 采集交易所公告数据

遵循法律合规要求，仅采集公开的交易所公告信息
"""

import scrapy
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any
import logging

from qsou_crawler.items import CompanyAnnouncementItem


class CompanyAnnouncementSpider(scrapy.Spider):
    name = 'company_announcement'
    allowed_domains = [
        'sse.com.cn',  # 上海证券交易所
        'szse.cn',     # 深圳证券交易所
        'neeq.com.cn', # 全国中小企业股份转让系统
        'cninfo.com.cn' # 巨潮资讯网
    ]
    
    # 交易所公告起始URL
    start_urls = [
        # 上交所公告
        'http://www.sse.com.cn/disclosure/announcement/company/',
        'http://www.sse.com.cn/disclosure/announcement/listed/',
        
        # 深交所公告
        'http://www.szse.cn/disclosure/listed/bulletinDetail/index.html',
        'http://www.szse.cn/disclosure/listed/notice/index.html',
        
        # 巨潮资讯网
        'http://www.cninfo.com.cn/new/disclosure/stock?plate=&stock=',
        'http://www.cninfo.com.cn/new/disclosure/stock?plate=szse&stock='
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 0.5,  # 更保守的访问频率
        'ROBOTSTXT_OBEY': True,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
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
                    'start_url': url
                },
                dont_filter=True
            )
    
    def parse(self, response):
        """解析公告列表页面"""
        domain = response.meta['domain']
        page = response.meta['page']
        start_url = response.meta['start_url']
        
        self.logger.info(f"解析 {domain} 第 {page} 页: {response.url}")
        
        # 根据域名选择不同的解析策略
        if 'sse.com.cn' in domain:
            yield from self.parse_sse(response)
        elif 'szse.cn' in domain:
            yield from self.parse_szse(response)
        elif 'cninfo.com.cn' in domain:
            yield from self.parse_cninfo(response)
        
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
    
    def parse_sse(self, response):
        """解析上交所公告"""
        # 公告链接选择器
        announcement_links = response.css('a[href*="/disclosure/announcement/"]::attr(href)').getall()
        announcement_links.extend(response.css('a[href*=".pdf"]::attr(href)').getall())
        
        for link in announcement_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_announcement_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_announcement_detail,
                        meta={'source': 'sse.com.cn', 'exchange': '上交所'}
                    )
    
    def parse_szse(self, response):
        """解析深交所公告"""
        announcement_links = response.css('a[href*="/disclosure/"]::attr(href)').getall()
        announcement_links.extend(response.css('a[href*=".pdf"]::attr(href)').getall())
        
        for link in announcement_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_announcement_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_announcement_detail,
                        meta={'source': 'szse.cn', 'exchange': '深交所'}
                    )
    
    def parse_cninfo(self, response):
        """解析巨潮资讯网公告"""
        announcement_links = response.css('a[href*="/new/disclosure/stock"]::attr(href)').getall()
        announcement_links.extend(response.css('a[href*=".pdf"]::attr(href)').getall())
        
        for link in announcement_links:
            if link and link not in self.processed_urls:
                full_url = urljoin(response.url, link)
                if self.is_valid_announcement_url(full_url):
                    self.processed_urls.add(link)
                    yield scrapy.Request(
                        url=full_url,
                        callback=self.parse_announcement_detail,
                        meta={'source': 'cninfo.com.cn', 'exchange': '巨潮资讯'}
                    )
    
    def parse_announcement_detail(self, response):
        """解析公告详情页面"""
        try:
            # 提取公告标题
            title = self.extract_title(response)
            if not title or len(title.strip()) < 5:
                self.logger.warning(f"公告标题过短或为空: {response.url}")
                return
            
            # 提取公告内容
            content = self.extract_content(response)
            if not content or len(content.strip()) < 50:
                self.logger.warning(f"公告内容过短或为空: {response.url}")
                return
            
            # 提取公司信息
            company_info = self.extract_company_info(response)
            
            # 提取公告类型
            announcement_type = self.extract_announcement_type(title, content)
            
            # 提取发布时间
            publish_time = self.extract_publish_time(response)
            
            # 提取公告编号
            announcement_id = self.extract_announcement_id(response)
            
            # 创建公告项目
            item = CompanyAnnouncementItem()
            item['title'] = title.strip()
            item['content'] = content.strip()
            item['url'] = response.url
            item['source'] = response.meta.get('source', 'unknown')
            item['exchange'] = response.meta.get('exchange', 'unknown')
            item['company_name'] = company_info.get('name', '')
            item['stock_code'] = company_info.get('code', '')
            item['announcement_type'] = announcement_type
            item['publish_time'] = publish_time
            item['announcement_id'] = announcement_id
            item['crawl_time'] = datetime.now().isoformat()
            item['content_length'] = len(content)
            item['is_important'] = self.is_important_announcement(title, content)
            
            # 数据质量检查
            if self.validate_announcement_item(item):
                yield item
            else:
                self.logger.warning(f"公告数据质量检查失败: {response.url}")
                
        except Exception as e:
            self.logger.error(f"解析公告详情失败 {response.url}: {str(e)}")
    
    def extract_title(self, response) -> str:
        """提取公告标题"""
        title_selectors = [
            'h1::text',
            '.title::text',
            '.announcement-title::text',
            '.notice-title::text',
            'title::text'
        ]
        
        for selector in title_selectors:
            title = response.css(selector).get()
            if title:
                return title.strip()
        
        return ""
    
    def extract_content(self, response) -> str:
        """提取公告内容"""
        content_selectors = [
            '.announcement-content p::text',
            '.notice-content p::text',
            '.content p::text',
            '.main-content p::text',
            'article p::text',
            '.announcement-body p::text'
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
    
    def extract_company_info(self, response) -> Dict[str, str]:
        """提取公司信息"""
        company_info = {'name': '', 'code': ''}
        
        # 提取公司名称
        company_name_selectors = [
            '.company-name::text',
            '.stock-name::text',
            '.company::text'
        ]
        
        for selector in company_name_selectors:
            name = response.css(selector).get()
            if name:
                company_info['name'] = name.strip()
                break
        
        # 提取股票代码
        stock_code_selectors = [
            '.stock-code::text',
            '.code::text',
            '.stock-symbol::text'
        ]
        
        for selector in stock_code_selectors:
            code = response.css(selector).get()
            if code:
                company_info['code'] = code.strip()
                break
        
        # 从URL中提取股票代码
        if not company_info['code']:
            code_from_url = self.extract_code_from_url(response.url)
            if code_from_url:
                company_info['code'] = code_from_url
        
        return company_info
    
    def extract_announcement_type(self, title: str, content: str) -> str:
        """根据标题和内容判断公告类型"""
        text = (title + " " + content).lower()
        
        # 财务报告相关
        if any(keyword in text for keyword in ['年报', '半年报', '季报', '财务报告', '审计报告']):
            return '财务报告'
        
        # 重大事项相关
        if any(keyword in text for keyword in ['重大事项', '重大合同', '重大投资', '重大资产']):
            return '重大事项'
        
        # 股权变动相关
        if any(keyword in text for keyword in ['股权变动', '增持', '减持', '股份变动', '股东']):
            return '股权变动'
        
        # 业绩预告相关
        if any(keyword in text for keyword in ['业绩预告', '业绩快报', '业绩修正']):
            return '业绩预告'
        
        # 停牌复牌相关
        if any(keyword in text for keyword in ['停牌', '复牌', '暂停上市', '恢复上市']):
            return '停牌复牌'
        
        # 分红送股相关
        if any(keyword in text for keyword in ['分红', '送股', '转增', '派息', '利润分配']):
            return '分红送股'
        
        # 关联交易相关
        if any(keyword in text for keyword in ['关联交易', '关联方', '关联关系']):
            return '关联交易'
        
        # 对外投资相关
        if any(keyword in text for keyword in ['对外投资', '投资', '收购', '并购']):
            return '对外投资'
        
        return '其他'
    
    def extract_publish_time(self, response) -> str:
        """提取发布时间"""
        time_selectors = [
            '.publish-time::text',
            '.announcement-time::text',
            '.notice-time::text',
            '.time::text',
            'time::text',
            '[datetime]::attr(datetime)'
        ]
        
        for selector in time_selectors:
            time_text = response.css(selector).get()
            if time_text:
                return time_text.strip()
        
        # 从URL中提取时间
        url_time = self.extract_time_from_url(response.url)
        if url_time:
            return url_time
        
        return datetime.now().isoformat()
    
    def extract_announcement_id(self, response) -> str:
        """提取公告编号"""
        id_selectors = [
            '.announcement-id::text',
            '.notice-id::text',
            '.document-id::text'
        ]
        
        for selector in id_selectors:
            announcement_id = response.css(selector).get()
            if announcement_id:
                return announcement_id.strip()
        
        # 从URL中提取ID
        url_id = self.extract_id_from_url(response.url)
        if url_id:
            return url_id
        
        return ""
    
    def extract_code_from_url(self, url: str) -> str:
        """从URL中提取股票代码"""
        # 匹配股票代码模式
        code_patterns = [
            r'stock=(\d{6})',
            r'code=(\d{6})',
            r'/(\d{6})/',
            r'(\d{6})\.'
        ]
        
        for pattern in code_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""
    
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
                return f"{year}-{month}-{day}T00:00:00"
        
        return ""
    
    def extract_id_from_url(self, url: str) -> str:
        """从URL中提取公告ID"""
        id_patterns = [
            r'id=(\d+)',
            r'/(\d+)\.',
            r'/(\d+)/'
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""
    
    def is_important_announcement(self, title: str, content: str) -> bool:
        """判断是否为重要公告"""
        text = (title + " " + content).lower()
        
        # 重要公告关键词
        important_keywords = [
            '重大事项', '重大合同', '重大投资', '重大资产',
            '业绩预告', '业绩快报', '业绩修正',
            '停牌', '复牌', '暂停上市', '恢复上市',
            '分红', '送股', '转增', '派息',
            '股权变动', '增持', '减持',
            '关联交易', '对外投资', '收购', '并购'
        ]
        
        return any(keyword in text for keyword in important_keywords)
    
    def is_valid_announcement_url(self, url: str) -> bool:
        """检查URL是否为有效的公告链接"""
        if not url:
            return False
        
        # 排除非公告链接
        exclude_patterns = [
            r'/video/',
            r'/photo/',
            r'/gallery/',
            r'/live/',
            r'/comment/',
            r'/user/',
            r'/login',
            r'/register',
            r'\.(jpg|jpeg|png|gif|doc|docx|xls|xlsx)$'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # 必须包含公告相关路径
        announcement_patterns = [
            r'/disclosure/',
            r'/announcement/',
            r'/notice/',
            r'/bulletin/',
            r'\.pdf$'
        ]
        
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in announcement_patterns)
    
    def validate_announcement_item(self, item: CompanyAnnouncementItem) -> bool:
        """验证公告项目的数据质量"""
        # 检查必要字段
        if not item.get('title') or not item.get('content'):
            return False
        
        # 检查内容长度
        if len(item.get('content', '')) < 50:
            return False
        
        # 检查标题长度
        if len(item.get('title', '')) < 5:
            return False
        
        return True
    
    def get_next_page_url(self, response, start_url: str, page: int) -> str:
        """获取下一页URL"""
        domain = urlparse(start_url).netloc
        
        if 'sse.com.cn' in domain:
            return f"{start_url}?page={page}"
        elif 'szse.cn' in domain:
            return f"{start_url}?page={page}"
        elif 'cninfo.com.cn' in domain:
            return f"{start_url}?page={page}"
        
        return None
