"""
数据项定义 - 定义爬取数据的结构和验证规则
"""

import scrapy
from itemloaders.processors import TakeFirst, MapCompose, Join, Identity
from datetime import datetime
from typing import Optional, List, Dict


def clean_text(value: str) -> str:
    """清理文本内容"""
    if not value:
        return ""
    
    import re
    # 移除多余的空白字符
    value = re.sub(r'\s+', ' ', value.strip())
    # 移除HTML实体
    value = value.replace('&nbsp;', ' ').replace('&amp;', '&')
    # 移除特殊字符
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    
    return value.strip()


def parse_datetime(value: str) -> Optional[str]:
    """解析日期时间"""
    if not value:
        return None
    
    import re
    from dateutil import parser
    
    try:
        # 中文日期格式处理
        chinese_date_patterns = [
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1-\2-\3'),
            (r'(\d{1,2})月(\d{1,2})日', f'{datetime.now().year}-\\1-\\2'),
            (r'今天', datetime.now().strftime('%Y-%m-%d')),
            (r'昨天', (datetime.now().date() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')),
        ]
        
        for pattern, replacement in chinese_date_patterns:
            if isinstance(replacement, str) and '\\' in replacement:
                value = re.sub(pattern, replacement, value)
            else:
                value = re.sub(pattern, replacement, value)
        
        # 解析日期
        parsed_date = parser.parse(value)
        return parsed_date.isoformat()
        
    except (ValueError, TypeError):
        return None


def extract_tags(value: str) -> List[str]:
    """提取标签"""
    if not value:
        return []
    
    # 按逗号、分号或空格分割
    import re
    tags = re.split(r'[,;，；\s]+', value.strip())
    
    # 清理和过滤标签
    cleaned_tags = []
    for tag in tags:
        tag = tag.strip()
        if tag and len(tag) > 1 and len(tag) <= 20:  # 合理的标签长度
            cleaned_tags.append(tag)
    
    return cleaned_tags[:10]  # 最多保留10个标签


class NewsArticleItem(scrapy.Item):
    """新闻文章数据项"""
    
    # 基础信息
    title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    summary = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # 来源信息
    source = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    author = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    original_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 时间信息
    published_at = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    crawled_at = scrapy.Field(
        output_processor=TakeFirst(),
        default=datetime.now().isoformat()
    )
    
    # 分类和标签
    category = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    tags = scrapy.Field(
        input_processor=MapCompose(extract_tags),
        output_processor=Identity()  # 保留列表格式
    )
    keywords = scrapy.Field(
        input_processor=MapCompose(extract_tags),
        output_processor=Identity()
    )
    
    # 媒体内容
    images = scrapy.Field(
        output_processor=Identity()  # 图片URL列表
    )
    videos = scrapy.Field(
        output_processor=Identity()  # 视频URL列表
    )
    
    # 元数据
    metadata = scrapy.Field(
        output_processor=TakeFirst(),
        default={}  # 字典格式的额外元数据
    )
    
    # 质量指标
    content_length = scrapy.Field(
        output_processor=TakeFirst()
    )
    readability_score = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 股票相关
    related_stocks = scrapy.Field(
        output_processor=Identity()  # 相关股票代码列表
    )
    stock_mentions = scrapy.Field(
        output_processor=Identity()  # 股票提及次数
    )


class CompanyAnnouncementItem(scrapy.Item):
    """上市公司公告数据项"""
    
    # 基础信息
    title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    announcement_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # 公司信息
    company_name = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    company_code = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst()
    )
    stock_code = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst()
    )
    exchange = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst()  # SSE, SZSE
    )
    
    # 时间信息
    announcement_date = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    published_at = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    effective_date = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    crawled_at = scrapy.Field(
        output_processor=TakeFirst(),
        default=datetime.now().isoformat()
    )
    
    # 文件信息
    pdf_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    attachments = scrapy.Field(
        output_processor=Identity()  # 附件列表
    )
    
    # 来源信息
    source = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    original_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 分类信息
    industry = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    sector = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # 重要性标识
    is_major = scrapy.Field(
        output_processor=TakeFirst(),
        default=False
    )
    impact_level = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()  # high, medium, low
    )
    
    # 元数据
    metadata = scrapy.Field(
        output_processor=TakeFirst(),
        default={}
    )


class ResearchReportItem(scrapy.Item):
    """研究报告数据项"""
    
    # 基础信息
    title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    abstract = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # 研究信息
    research_institution = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    analysts = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=Identity()  # 分析师列表
    )
    report_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()  # 行业报告、个股研究、策略报告等
    )
    
    # 标的信息
    target_stocks = scrapy.Field(
        output_processor=Identity()  # 目标股票代码
    )
    target_industry = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # 投资建议
    investment_rating = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()  # 买入、持有、卖出
    )
    target_price = scrapy.Field(
        output_processor=TakeFirst()  # 目标价格
    )
    
    # 时间信息
    published_at = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    report_period = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    crawled_at = scrapy.Field(
        output_processor=TakeFirst(),
        default=datetime.now().isoformat()
    )
    
    # 文件信息
    pdf_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    file_size = scrapy.Field(
        output_processor=TakeFirst()
    )
    page_count = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 来源信息
    source = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 元数据
    metadata = scrapy.Field(
        output_processor=TakeFirst(),
        default={}
    )


class MarketDataItem(scrapy.Item):
    """市场数据项"""
    
    # 基础信息
    symbol = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst()
    )
    name = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    exchange = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst()
    )
    
    # 价格信息
    current_price = scrapy.Field(
        output_processor=TakeFirst()
    )
    open_price = scrapy.Field(
        output_processor=TakeFirst()
    )
    high_price = scrapy.Field(
        output_processor=TakeFirst()
    )
    low_price = scrapy.Field(
        output_processor=TakeFirst()
    )
    close_price = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 交易信息
    volume = scrapy.Field(
        output_processor=TakeFirst()
    )
    turnover = scrapy.Field(
        output_processor=TakeFirst()
    )
    market_cap = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 变化信息
    price_change = scrapy.Field(
        output_processor=TakeFirst()
    )
    price_change_percent = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 时间信息
    trading_date = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    timestamp = scrapy.Field(
        input_processor=MapCompose(parse_datetime),
        output_processor=TakeFirst()
    )
    crawled_at = scrapy.Field(
        output_processor=TakeFirst(),
        default=datetime.now().isoformat()
    )
    
    # 来源信息
    source = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # 元数据
    metadata = scrapy.Field(
        output_processor=TakeFirst(),
        default={}
    )
