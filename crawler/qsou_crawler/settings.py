"""
Qsou投资情报搜索引擎 - Scrapy爬虫设置

遵循严格的网络爬取道德规范，确保合法合规的数据采集
"""

import os
from typing import Dict

# Scrapy settings for qsou_crawler project
BOT_NAME = 'qsou_crawler'

SPIDER_MODULES = ['qsou_crawler.spiders']
NEWSPIDER_MODULE = 'qsou_crawler.spiders'

# ============================================
# 机器人协议遵循 (Robots.txt Compliance)
# ============================================
ROBOTSTXT_OBEY = True  # 严格遵循robots.txt

# 用户代理设置
USER_AGENT = os.getenv(
    'SPIDER_USER_AGENT',
    'Qsou-InvestmentBot/1.0 (+http://your-domain.com/bot; contact@your-domain.com)'
)

# ============================================
# 请求频率控制 (Rate Limiting)
# ============================================
# 请求延迟设置 (秒)
DOWNLOAD_DELAY = float(os.getenv('DOWNLOAD_DELAY', 3))
# 随机延迟 (0.5 * to 1.5 * DOWNLOAD_DELAY)
RANDOMIZE_DOWNLOAD_DELAY = float(os.getenv('RANDOMIZE_DOWNLOAD_DELAY', 0.5))

# 并发请求设置
CONCURRENT_REQUESTS = int(os.getenv('SPIDER_CONCURRENCY', 16))
# 每个域名的并发请求
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv('CONCURRENT_REQUESTS_PER_DOMAIN', 1))

# ============================================
# 自动限速设置 (AutoThrottle)
# ============================================
AUTOTHROTTLE_ENABLED = os.getenv('SPIDER_AUTOTHROTTLE_ENABLED', 'true').lower() == 'true'
AUTOTHROTTLE_START_DELAY = float(os.getenv('SPIDER_AUTOTHROTTLE_START_DELAY', 1))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv('SPIDER_AUTOTHROTTLE_MAX_DELAY', 60))
# 平均请求数/秒。1.0代表每秒1个请求，2.0代表每秒2个请求
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.getenv('AUTOTHROTTLE_TARGET_CONCURRENCY', 1.0))
AUTOTHROTTLE_DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

# ============================================
# 中间件配置
# ============================================
DOWNLOADER_MIDDLEWARES = {
    # 内置中间件
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,  # 禁用默认UA中间件
    'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware': 100,  # Robots.txt中间件
    
    # 自定义中间件 
    'qsou_crawler.middlewares.RotateUserAgentMiddleware': 400,  # 用户代理轮换
    'qsou_crawler.middlewares.ProxyMiddleware': 350,  # 代理中间件
    'qsou_crawler.middlewares.RetryMiddleware': 550,  # 重试中间件
    'qsou_crawler.middlewares.AntiDetectionMiddleware': 600,  # 反检测中间件
}

SPIDER_MIDDLEWARES = {
    'qsou_crawler.middlewares.DuplicateFilterMiddleware': 543,  # 去重过滤
    'qsou_crawler.middlewares.StatisticsMiddleware': 900,  # 统计中间件
}

# ============================================
# 数据管道配置
# ============================================
ITEM_PIPELINES = {
    'qsou_crawler.pipelines.ValidationPipeline': 200,  # 数据验证
    'qsou_crawler.pipelines.CleaningPipeline': 300,  # 数据清洗
    'qsou_crawler.pipelines.DuplicationPipeline': 400,  # 去重
    'qsou_crawler.pipelines.NLPPipeline': 500,  # NLP处理
    'qsou_crawler.pipelines.DatabasePipeline': 600,  # 数据库存储
    'qsou_crawler.pipelines.SearchEnginePipeline': 700,  # 搜索引擎索引
    'qsou_crawler.pipelines.VectorStorePipeline': 800,  # 向量存储
}

# ============================================
# 分布式爬虫配置 (Scrapy-Redis)
# ============================================
# 启用分布式
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True

# Redis连接设置
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

# ============================================
# 缓存设置
# ============================================
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600  # 1小时过期
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ============================================
# 日志设置
# ============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/scrapy.log')
LOG_ENABLED = True
LOG_ENCODING = 'utf-8'

# ============================================
# 请求设置
# ============================================
# 请求超时
DOWNLOAD_TIMEOUT = 30
# 重试次数
RETRY_TIMES = 3
# 重试HTTP状态码
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Cookies设置
COOKIES_ENABLED = True

# ============================================
# 文件和图片下载设置
# ============================================
# 文件存储路径
FILES_STORE = 'downloads/files'
IMAGES_STORE = 'downloads/images'

# 图片过滤设置
IMAGES_MIN_HEIGHT = 50
IMAGES_MIN_WIDTH = 50

# ============================================
# 合规性和安全设置
# ============================================
# DNS超时
DNSCACHE_ENABLED = True
DNS_TIMEOUT = 60

# 请求指纹
DUPEFILTER_DEBUG = False

# 内存使用监控
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048  # 2GB内存限制
MEMUSAGE_WARNING_MB = 1536  # 1.5GB警告

# ============================================
# 自定义设置
# ============================================

# 数据库连接设置
DATABASE_URL = os.getenv(
    'DATABASE_URL', 
    'postgresql://qsou:your_password@localhost:5432/qsou_investment_intel'
)

# Elasticsearch设置
ELASTICSEARCH_HOSTS = [
    f"http://{os.getenv('ELASTICSEARCH_HOST', 'localhost')}:{os.getenv('ELASTICSEARCH_PORT', 9200)}"
]
ELASTICSEARCH_INDEX_PREFIX = os.getenv('ELASTICSEARCH_INDEX_PREFIX', 'qsou_')

# Qdrant设置
QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))
QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'investment_documents')

# NLP模型设置
BERT_MODEL_PATH = os.getenv('BERT_MODEL_PATH', 'bert-base-chinese')
SENTENCE_TRANSFORMER_MODEL = os.getenv(
    'SENTENCE_TRANSFORMER_MODEL', 
    'shibing624/text2vec-base-chinese'
)

# 代理设置
PROXY_LIST_FILE = 'proxies.txt'  # 代理列表文件

# 数据质量设置
MIN_CONTENT_LENGTH = 100  # 最小内容长度
MAX_CONTENT_LENGTH = 1000000  # 最大内容长度 (1MB)

# 监控和统计
TELNETCONSOLE_ENABLED = False  # 禁用telnet控制台（安全考虑）
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

# ============================================
# 特定域名设置
# ============================================

# 财经网站特定设置
FINANCIAL_SITES_CONFIG: Dict[str, Dict] = {
    'eastmoney.com': {
        'download_delay': 2,
        'concurrent_requests': 1,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    },
    'sina.com.cn': {
        'download_delay': 3,
        'concurrent_requests': 1,
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
    },
    'sse.com.cn': {  # 上交所
        'download_delay': 5,
        'concurrent_requests': 1,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    'szse.cn': {  # 深交所
        'download_delay': 5,
        'concurrent_requests': 1,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

# ============================================
# 数据源白名单 (Legal Compliance)
# ============================================
# 只爬取明确允许的数据源
ALLOWED_DOMAINS_WHITELIST = [
    # 公开的财经新闻网站
    'eastmoney.com',  # 东方财富
    'sina.com.cn',    # 新浪财经 
    '163.com',        # 网易财经
    'sohu.com',       # 搜狐财经
    
    # 官方机构网站
    'sse.com.cn',     # 上海证券交易所
    'szse.cn',        # 深圳证券交易所
    'csrc.gov.cn',    # 证监会
    'pbc.gov.cn',     # 央行
    
    # 专业财经媒体
    'caijing.com.cn', # 财经网
    'yicai.com',      # 第一财经
    'cls.cn',         # 财联社
    'wallstreetcn.com' # 华尔街见闻
]

# 严格域名验证
ALLOWED_DOMAINS_ONLY = True

# Request meta settings
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',  # Do Not Track
    'Cache-Control': 'no-cache',
}
