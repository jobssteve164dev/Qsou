"""统一来源适配器的生产采集设置。"""

import os

# Scrapy settings for qsou_crawler project
BOT_NAME = 'qsou_crawler'

# 生产面只暴露统一适配器 Spider；来源扩展点统一由 AdapterRegistry 管理。
SPIDER_MODULES = ['qsou_crawler.spiders.source_adapter_spider']
NEWSPIDER_MODULE = 'qsou_crawler.spiders'
SPIDER_LOADER_CLASS = 'scrapy.spiderloader.SpiderLoader'

# ============================================
# 机器人协议遵循 (Robots.txt Compliance)
# ============================================
ROBOTSTXT_OBEY = True  # 严格遵循robots.txt
ROBOTSTXT_ENCODING = 'utf-8'  # 设置robots.txt编码

# 用户代理设置
USER_AGENT = os.getenv(
    'SPIDER_USER_AGENT',
    'Qsou-Collector/0.2 (+https://qsou.szlk.uk; purpose=public-investment-data-archival)'
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
    'qsou_crawler.middlewares.RawEvidenceDownloaderMiddleware': 540,  # 解析前归档原始证据
}

SPIDER_MIDDLEWARES = {
    'qsou_crawler.middlewares.EvidenceLinkMiddleware': 100,  # 关联响应证据与产出文档
}

# ============================================
# 数据管道配置
# ============================================
ITEM_PIPELINES = {
    'qsou_crawler.pipelines.data_processing_pipeline.ValidationPipeline': 200,  # 数据验证
    'qsou_crawler.pipelines.data_processing_pipeline.DataProcessingPipeline': 500,  # 数据处理
}

# 自主数据资产基线
QSOU_DATA_ROOT = os.getenv('QSOU_DATA_ROOT', '')
QSOU_SOURCE_REGISTRY = os.getenv('QSOU_SOURCE_REGISTRY', '')
QSOU_OUTBOX_DISPATCH_ENABLED = os.getenv('QSOU_OUTBOX_DISPATCH_ENABLED', 'false').lower() == 'true'
QSOU_OUTBOX_BATCH_SIZE = int(os.getenv('QSOU_OUTBOX_BATCH_SIZE', 10))

# 不使用框架缓存替代原始证据归档；每次访问都进入可审计证据链。
HTTPCACHE_ENABLED = False

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
# 公告 PDF 可能达到数十 MiB；生产节点实测 35 MiB 官方公告可能需要数分钟。
# 正式采集优先完成下载，不用短超时触发重复传输并制造失败。
DOWNLOAD_TIMEOUT = int(os.getenv('QSOU_DOWNLOAD_TIMEOUT_SECONDS', '900'))
# 重试次数
RETRY_TIMES = 3
# 重试HTTP状态码
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Cookies设置
COOKIES_ENABLED = True

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
MEMUSAGE_LIMIT_MB = int(os.getenv('QSOU_COLLECTOR_MEMORY_LIMIT_MB', '3584'))
MEMUSAGE_WARNING_MB = int(os.getenv('QSOU_COLLECTOR_MEMORY_WARNING_MB', '3072'))

# 数据质量设置
MIN_CONTENT_LENGTH = 100  # 最小内容长度
MAX_CONTENT_LENGTH = 1000000  # 最大内容长度 (1MB)

# 监控和统计
TELNETCONSOLE_ENABLED = False  # 禁用telnet控制台（安全考虑）
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Request meta settings
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
}
