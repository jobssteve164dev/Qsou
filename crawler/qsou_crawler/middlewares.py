"""生产采集链只保留原始证据归档与证据身份关联。"""

from scrapy import Item

from qsou_data import DataAssetStore
from qsou_data.registry import UnknownSourceError
from qsou_data.store import utc_now


class RawEvidenceDownloaderMiddleware:
	"""在 Spider 解析前持久化来源响应。"""

	def __init__(self, store: DataAssetStore) -> None:
		self.store = store

	@classmethod
	def from_crawler(cls, crawler):
		return cls(DataAssetStore())

	def process_response(self, request, response, spider):
		try:
			source = self.store.registry.resolve_url(response.url)
			content_type_value = response.headers.get(b"Content-Type", b"application/octet-stream")
			content_type = content_type_value.decode("latin-1") if isinstance(content_type_value, bytes) else str(content_type_value)
			fetched_at = utc_now()
			evidence = self.store.archive_response(
				source_id=source["source_id"],
				url=response.url,
				status_code=response.status,
				response_headers=response.headers,
				body=response.body,
				fetched_at=fetched_at,
				content_type=content_type,
				encoding=getattr(response, "encoding", None),
				collector=f"scrapy:{spider.name}",
			)
			spider.crawler.stats.inc_value("adapter/evidence_archived")
			# Downloader middleware runs before Scrapy attaches ``request`` to the
			# response.  Persist the identity on the request that Scrapy will later
			# expose as ``response.meta`` inside the spider middleware and callback.
			request.meta["qsou_evidence"] = {
				"raw_object_id": evidence["raw_object_id"],
				"source_id": evidence["source_id"],
				"fetched_at": fetched_at,
				"final_url": evidence["url"],
				"parser_version": "qsou-crawler/1",
			}
			return response
		except UnknownSourceError:
			spider.crawler.stats.inc_value("adapter/failures")
			spider.logger.error("响应来源未登记，拒绝进入正式数据链: %s", response.url)
			raise
		except Exception:
			spider.crawler.stats.inc_value("adapter/failures")
			spider.logger.exception("原始证据归档失败，拒绝解析响应: %s", response.url)
			raise


class EvidenceLinkMiddleware:
	"""把当前响应的证据身份传递给其产出的标准文档候选。"""

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_spider_output(self, response, result, spider):
		evidence = response.meta.get("qsou_evidence")
		for output in result:
			if evidence and isinstance(output, (Item, dict)):
				metadata = dict(output.get("metadata") or {})
				metadata.update(evidence)
				output["metadata"] = metadata
			yield output
