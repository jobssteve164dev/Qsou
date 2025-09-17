"""
数据处理服务

连接爬虫和数据处理系统
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
import requests
from celery import Celery

from app.core.config import settings
from app.services.search_service import search_service


class DataProcessingService:
	"""数据处理服务"""
	
	def __init__(self):
		self.logger = logger
		self.celery_app = None
		self._initialize_celery()
	
	def _initialize_celery(self):
		"""初始化Celery连接"""
		try:
			self.celery_app = Celery('qsou-data-processor')
			self.celery_app.config_from_object({
				'broker_url': settings.CELERY_BROKER_URL,
				'result_backend': settings.CELERY_RESULT_BACKEND,
				'task_serializer': 'json',
				'result_serializer': 'json',
				'accept_content': ['json'],
				'timezone': 'Asia/Shanghai',
				'enable_utc': True,
			})
			self.logger.info("Celery连接初始化成功")
		except Exception as e:
			self.logger.error(f"Celery连接初始化失败: {str(e)}")
			self.celery_app = None
	
	async def process_documents(
		self,
		documents: List[Dict[str, Any]],
		source: str = "crawler",
		batch_id: Optional[str] = None,
		enable_elasticsearch: bool = True,
		enable_vector_store: bool = True,
		enable_nlp_processing: bool = True
	) -> Dict[str, Any]:
		"""处理文档数据"""
		try:
			if not documents:
				return {
					"status": "success",
					"message": "没有文档需要处理",
					"processed_count": 0,
					"failed_count": 0,
					"batch_id": batch_id or "empty"
				}
			
			# 生成批次ID
			if not batch_id:
				batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			
			self.logger.info(
				f"开始处理 {len(documents)} 个文档",
				source=source,
				batch_id=batch_id
			)
			
			# 使用Celery异步处理（若可用）
			if self.celery_app:
				# 使用不含连字符的任务名以避免模块名冲突
				task_results = []
				for i, doc in enumerate(documents):
					try:
						doc_id = doc.get('id', f"{batch_id}_{i}")
						# 任务名采用通用形式：tasks.process_crawled_data
						task = self.celery_app.send_task(
							'data-processor.tasks.process_crawled_data',
							args=[doc_id, doc],
							queue='data_processing'
						)
						task_results.append({
							'doc_id': doc_id,
							'task_id': task.id,
							'status': 'submitted'
						})
					except Exception as e:
						self.logger.error(f"提交文档处理任务失败: {str(e)}")
						task_results.append({
							'doc_id': doc.get('id', f"{batch_id}_{i}"),
							'task_id': None,
							'status': 'failed',
							'error': str(e)
						})
				
				# 等待任务（带超时）
				await self._wait_for_tasks_completion(task_results)
				processed_count = len([r for r in task_results if r['status'] == 'completed'])
				failed_count = len([r for r in task_results if r['status'] in ('failed','timeout')])
				return {
					"status": "success",
					"message": f"处理完成: {processed_count} 成功, {failed_count} 失败",
					"processed_count": processed_count,
					"failed_count": failed_count,
					"batch_id": batch_id,
					"task_results": task_results
				}
			
			# Celery不可用：走直接路径，真实落地（所见即可用）
			return await self._process_documents_direct(
				documents, source, batch_id,
				enable_elasticsearch, enable_vector_store, enable_nlp_processing
			)
				
		except Exception as e:
			self.logger.error(f"处理文档失败: {str(e)}")
			return {
				"status": "error",
				"message": f"处理失败: {str(e)}",
				"processed_count": 0,
				"failed_count": len(documents),
				"batch_id": batch_id or "error"
			}
	
	async def _wait_for_tasks_completion(self, task_results: List[Dict[str, Any]], timeout: int = 300):
		"""等待Celery任务完成"""
		start_time = datetime.now()
		
		while (datetime.now() - start_time).total_seconds() < timeout:
			all_completed = True
			for result in task_results:
				if result['status'] == 'submitted' and result['task_id']:
					try:
						task_result = self.celery_app.AsyncResult(result['task_id'])
						if task_result.ready():
							if task_result.successful():
								result['status'] = 'completed'
								result['result'] = task_result.result
							else:
								result['status'] = 'failed'
								result['error'] = str(task_result.result)
						else:
							all_completed = False
					except Exception as e:
						result['status'] = 'failed'
						result['error'] = str(e)
			if all_completed:
				break
			await asyncio.sleep(1)
		
		for result in task_results:
			if result['status'] == 'submitted':
				result['status'] = 'timeout'
				result['error'] = 'Task timeout'
	
	async def _process_documents_direct(
		self,
		documents: List[Dict[str, Any]],
		source: str,
		batch_id: str,
		enable_elasticsearch: bool,
		enable_vector_store: bool,
		enable_nlp_processing: bool
	) -> Dict[str, Any]:
		"""直接处理文档（当Celery不可用时）：真实写入Elasticsearch，所见即可用"""
		try:
			processed_count = 0
			failed_count = 0
			
			# 确保索引存在
			try:
				await search_service._ensure_indices_exist()  # 使用现有服务的索引策略
			except Exception as e:
				self.logger.warning(f"确保索引存在失败，将继续尝试写入: {e}")
			
			index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
			
			for i, doc in enumerate(documents):
				try:
					# 最小规范化：映射到搜索索引字段
					body = {
						"title": doc.get("title", ""),
						"content": doc.get("content", ""),
						"summary": (doc.get("content", "") or "")[:200],
						"source": doc.get("source", source),
						"url": doc.get("url", ""),
						"published_at": doc.get("publish_time", datetime.now().isoformat()),
						"tags": doc.get("tags", []),
						"title_suggest": doc.get("title", ""),
					}
					if not body["title"] or not body["content"]:
						raise ValueError("缺少必要字段 title/content")
					
					doc_id = doc.get("id", f"{batch_id}_{i}")
					resp = await search_service.client.index(
						index=index_name,
						id=doc_id,
						body=body,
						refresh=True
					)
					if resp and resp.get("result") in ("created", "updated"):
						processed_count += 1
					else:
						failed_count += 1
				except Exception as e:
					self.logger.error(f"直接写入失败: {str(e)}")
					failed_count += 1
			
			return {
				"status": "success",
				"message": f"直接处理完成: {processed_count} 成功, {failed_count} 失败",
				"processed_count": processed_count,
				"failed_count": failed_count,
				"batch_id": batch_id
			}
			
		except Exception as e:
			self.logger.error(f"直接处理文档失败: {str(e)}")
			return {
				"status": "error",
				"message": f"直接处理失败: {str(e)}",
				"processed_count": 0,
				"failed_count": len(documents),
				"batch_id": batch_id
			}
	
	async def get_status(self) -> Dict[str, Any]:
		"""获取处理服务状态"""
		try:
			status = {
				"service": "data_processing",
				"status": "running",
				"timestamp": datetime.now().isoformat(),
				"celery_connected": self.celery_app is not None
			}
			if self.celery_app:
				try:
					inspect = self.celery_app.control.inspect()
					stats = inspect.stats()
					if stats:
						status["celery_workers"] = len(stats)
						status["celery_stats"] = stats
					else:
						status["celery_workers"] = 0
						status["celery_stats"] = {}
				except Exception as e:
					status["celery_error"] = str(e)
			return status
		except Exception as e:
			self.logger.error(f"获取状态失败: {str(e)}")
			return {
				"service": "data_processing",
				"status": "error",
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			}
	
	async def health_check(self) -> Dict[str, Any]:
		"""健康检查"""
		try:
			health = {
				"service": "data_processing",
				"healthy": True,
				"timestamp": datetime.now().isoformat(),
				"checks": {}
			}
			if self.celery_app:
				try:
					inspect = self.celery_app.control.inspect()
					stats = inspect.stats()
					health["checks"]["celery"] = {
						"status": "healthy" if stats else "no_workers",
						"workers": len(stats) if stats else 0
					}
				except Exception as e:
					health["checks"]["celery"] = {"status": "unhealthy", "error": str(e)}
					health["healthy"] = False
			else:
				health["checks"]["celery"] = {"status": "not_configured"}
			return health
		except Exception as e:
			self.logger.error(f"健康检查失败: {str(e)}")
			return {
				"service": "data_processing",
				"healthy": False,
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			}


# 创建全局实例
data_processing_service = DataProcessingService()
