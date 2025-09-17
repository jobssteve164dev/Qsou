"""
Pipelines 占位转发
settings.py 可能引用了 qsou_crawler.pipelines.*
这里转发到 data_processing_pipeline 中的具体实现，避免导入错误。
"""

from .pipelines.data_processing_pipeline import (
	DataProcessingPipeline,
	ValidationPipeline,
	DuplicationPipeline,
	StatisticsPipeline,
)
