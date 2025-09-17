"""
Scrapy 中间件最小可用实现
- RotateUserAgentMiddleware: 轮换UA（优先使用user_agents/fake_useragent，失败则回退固定UA）
- ProxyMiddleware: 预留代理（当前透传）
- RetryMiddleware: 透传，保留Scrapy默认重试
- AntiDetectionMiddleware: 添加少量常见头部
- DuplicateFilterMiddleware: 简单去重（基于URL）
- StatisticsMiddleware: 基本统计
"""

import random
from typing import Optional, Set

from scrapy import signals
from scrapy.http import Request

try:
	from fake_useragent import UserAgent  # type: ignore
	_FAKE_UA_AVAILABLE = True
except Exception:
	_FAKE_UA_AVAILABLE = False

# 一组常见浏览器UA，作为兜底
_FALLBACK_UAS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]


class RotateUserAgentMiddleware:
	"""下载器中间件：轮换UA"""

	def __init__(self) -> None:
		self.ua: Optional[UserAgent] = None
		if _FAKE_UA_AVAILABLE:
			try:
				self.ua = UserAgent()
			except Exception:
				self.ua = None

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_request(self, request: Request, spider):  # noqa: D401
		ua_value = None
		if self.ua is not None:
			try:
				ua_value = self.ua.random
			except Exception:
				ua_value = None
		if not ua_value:
			ua_value = random.choice(_FALLBACK_UAS)
		request.headers.setdefault(b"User-Agent", ua_value.encode("utf-8"))
		return None


class ProxyMiddleware:
	"""下载器中间件：代理（当前不启用，预留钩子）"""

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_request(self, request: Request, spider):
		# 若后续需要，可从crawler settings或ENV读取代理并设置：
		# request.meta['proxy'] = 'http://user:pass@host:port'
		return None


class RetryMiddleware:
	"""占位：保留Scrapy默认重试逻辑，故不拦截。"""

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_response(self, request, response, spider):
		return response

	def process_exception(self, request, exception, spider):
		return None


class AntiDetectionMiddleware:
	"""下载器中间件：添加常见头部，降低指纹一致性"""

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_request(self, request: Request, spider):
		request.headers.setdefault(b"Accept", b"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
		request.headers.setdefault(b"Accept-Language", b"zh-CN,zh;q=0.9,en;q=0.8")
		request.headers.setdefault(b"Accept-Encoding", b"gzip, deflate, br")
		request.headers.setdefault(b"Connection", b"keep-alive")
		request.headers.setdefault(b"Upgrade-Insecure-Requests", b"1")
		return None


class DuplicateFilterMiddleware:
	"""爬虫中间件：基于URL的简单去重（进程内）"""

	def __init__(self) -> None:
		self._seen: Set[str] = set()

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_spider_output(self, response, result, spider):
		for r in result:
			if isinstance(r, Request):
				url = r.url
				if url in self._seen:
					continue
				self._seen.add(url)
			yield r


class StatisticsMiddleware:
	"""爬虫中间件：简单统计请求/响应数量"""

	def __init__(self) -> None:
		self._requests = 0
		self._responses = 0

	@classmethod
	def from_crawler(cls, crawler):
		mw = cls()
		crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
		crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
		crawler.signals.connect(mw.response_received, signal=signals.response_received)
		return mw

	def spider_opened(self, spider):
		self._requests = 0
		self._responses = 0

	def response_received(self, response, request, spider):
		self._responses += 1

	def process_request(self, request: Request, spider):
		self._requests += 1
		return None

	def spider_closed(self, spider):
		spider.logger.info(f"[Statistics] requests={self._requests}, responses={self._responses}")
