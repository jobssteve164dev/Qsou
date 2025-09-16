# 数据处理模块 (Data Processor)

投资情报搜索引擎的核心数据处理模块，负责数据清洗、NLP处理、向量化、索引和增量更新。

## 📋 功能概述

### 核心功能
- **数据清洗管道**: 去重、格式化、内容提取、质量评估
- **中文NLP处理**: 分词、实体识别、情感分析、文本分类
- **文本向量化**: 使用中文金融BERT模型生成文档向量
- **Elasticsearch索引**: 建立搜索索引和映射策略
- **向量存储**: Qdrant向量数据库集成
- **增量更新**: 智能数据同步和更新机制
- **搜索引擎**: 多种搜索类型支持（文本、语义、混合）

### 技术栈
- **Python 3.8+**
- **Elasticsearch 8.11+**: 全文搜索引擎
- **Qdrant**: 向量数据库
- **Transformers**: 中文NLP模型
- **Jieba**: 中文分词
- **Celery**: 异步任务队列
- **Redis**: 缓存和消息队列
- **Pandas/NumPy**: 数据处理

## 🏗️ 模块结构

```
data-processor/
├── __init__.py                 # 包初始化
├── config.py                   # 配置管理
├── main.py                     # 主管理器
├── pipeline.py                 # 数据处理管道
├── demo.py                     # 功能演示脚本
├── test_pipeline.py           # 管道测试验证
├── requirements.txt           # 依赖包列表
├── README.md                  # 本文档
│
├── processors/                # 数据处理器
│   ├── __init__.py
│   ├── cleaner.py            # 数据清洗
│   ├── extractor.py          # 内容提取
│   ├── deduplicator.py       # 去重处理
│   └── quality_assessor.py   # 质量评估
│
├── nlp/                      # NLP处理模块
│   ├── __init__.py
│   ├── nlp_processor.py      # NLP统一接口
│   ├── segmentation.py       # 中文分词
│   ├── entity_recognition.py # 实体识别
│   ├── sentiment_analysis.py # 情感分析
│   └── text_classifier.py    # 文本分类
│
├── vector/                   # 向量处理模块
│   ├── __init__.py
│   ├── vector_manager.py     # 向量管理器
│   ├── embeddings.py         # 文本向量化
│   ├── vector_store.py       # 向量存储
│   └── similarity_search.py  # 相似度搜索
│
├── elasticsearch/            # Elasticsearch模块
│   ├── __init__.py
│   ├── index_manager.py      # 索引管理
│   ├── document_indexer.py   # 文档索引
│   └── search_engine.py      # 搜索引擎
│
└── incremental/             # 增量更新模块
    ├── __init__.py
    ├── sync_manager.py       # 同步管理器
    ├── change_detector.py    # 变更检测
    └── incremental_processor.py # 增量处理
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd data-processor
pip install -r requirements.txt
```

### 2. 配置环境

确保以下服务正在运行：
- Elasticsearch (端口: 9200)
- Qdrant (端口: 6333)
- Redis (端口: 6379)

### 3. 运行演示

```bash
python demo.py
```

演示脚本将展示：
- 系统初始化
- 数据处理管道
- 搜索功能
- 系统统计

### 4. 运行完整测试

```bash
python test_pipeline.py
```

测试脚本将验证：
- 系统初始化
- 完整数据处理管道
- 搜索功能
- 组件健康状态

## 💻 使用示例

### 基本使用

```python
import asyncio
from main import data_processor_manager

async def process_documents():
    # 1. 初始化系统
    init_result = await data_processor_manager.initialize()
    if not init_result['success']:
        print("初始化失败")
        return
    
    # 2. 准备文档数据
    documents = [
        {
            'title': '新闻标题',
            'content': '新闻内容...',
            'url': 'https://example.com/news/1',
            'source': '新闻来源',
            'publish_time': '2024-10-30T09:30:00Z'
        }
    ]
    
    # 3. 处理文档
    result = await data_processor_manager.process_documents_full_pipeline(
        documents=documents,
        enable_elasticsearch=True,
        enable_vector_store=True
    )
    
    if result['success']:
        print(f"处理成功: {result['processed_documents']} 个文档")
    
    # 4. 搜索文档
    search_result = await data_processor_manager.search_documents(
        query="搜索关键词",
        search_type="hybrid",
        limit=10
    )
    
    if search_result['success']:
        documents = search_result['result']['documents']
        print(f"找到 {len(documents)} 个相关文档")

# 运行
asyncio.run(process_documents())
```

### 高级配置

```python
from config import config

# 自定义配置
config.update({
    'elasticsearch': {
        'host': 'localhost',
        'port': 9200,
        'index_prefix': 'investment_'
    },
    'qdrant': {
        'host': 'localhost',
        'port': 6333,
        'collection_name': 'investment_documents'
    },
    'nlp': {
        'model_name': 'bert-base-chinese',
        'max_length': 512,
        'batch_size': 32
    }
})
```

## 🔧 核心组件详解

### 1. 数据处理管道 (Pipeline)

负责数据的清洗、提取、去重和质量评估：

```python
from pipeline import DataProcessingPipeline

pipeline = DataProcessingPipeline()
result = pipeline.process_documents(
    documents,
    enable_deduplication=True,
    enable_quality_filter=True
)
```

**功能特性**:
- HTML标签清理
- 文本格式化
- 内容去重（基于内容哈希）
- 数据质量评分
- 元数据提取

### 2. NLP处理器 (NLP Processor)

提供中文文本的深度语言处理：

```python
from nlp.nlp_processor import NLPProcessor

nlp = NLPProcessor()
result = nlp.process_text("待分析的中文文本")

# 结果包含：
# - segments: 分词结果
# - entities: 命名实体
# - sentiment: 情感分析
# - category: 文本分类
```

**支持的NLP任务**:
- **中文分词**: 使用Jieba分词器
- **命名实体识别**: 识别人名、地名、机构名等
- **情感分析**: 正面/负面/中性情感判断
- **文本分类**: 新闻、公告、研报等类别分类

### 3. 向量管理器 (Vector Manager)

处理文本向量化和相似度搜索：

```python
from vector.vector_manager import VectorManager

vector_mgr = VectorManager()

# 生成文档向量
embeddings = vector_mgr.generate_embeddings(["文本1", "文本2"])

# 存储向量
vector_mgr.store_vectors(documents, embeddings)

# 向量搜索
results = vector_mgr.search(
    query="搜索查询",
    search_type="semantic",
    limit=10
)
```

**向量化特性**:
- **中文金融BERT**: 专门针对金融领域优化
- **多维向量**: 支持768维向量表示
- **批量处理**: 高效的批量向量生成
- **相似度搜索**: 余弦相似度计算

### 4. Elasticsearch集成

提供强大的全文搜索能力：

```python
from es_indexing.search_engine import SearchEngine

search_engine = SearchEngine()

# 全文搜索
results = search_engine.search(
    query="搜索关键词",
    size=10,
    filters={'category': 'news'}
)

# 聚合查询
agg_results = search_engine.aggregate(
    field="category",
    size=10
)
```

**搜索特性**:
- **中文分析器**: IK分词器支持
- **多字段搜索**: 标题、内容、标签等
- **过滤和聚合**: 复杂查询支持
- **高亮显示**: 搜索结果高亮

### 5. 增量更新机制

智能检测和处理数据变更：

```python
from incremental.sync_manager import SyncManager

sync_mgr = SyncManager()

# 检测变更
changes = sync_mgr.detect_changes(source_data)

# 增量处理
sync_mgr.process_incremental_updates(changes)

# 同步状态
status = sync_mgr.get_sync_status()
```

**增量更新特性**:
- **变更检测**: 基于内容哈希的智能检测
- **批量更新**: 高效的批量数据同步
- **冲突解决**: 自动处理数据冲突
- **状态跟踪**: 详细的同步状态记录

## 📊 性能指标

### 处理性能
- **文档处理速度**: ~100-500 文档/秒
- **NLP处理速度**: ~50-200 文档/秒
- **向量生成速度**: ~20-100 文档/秒
- **索引写入速度**: ~200-1000 文档/秒

### 搜索性能
- **Elasticsearch查询**: <100ms (平均)
- **向量搜索**: <200ms (平均)
- **混合搜索**: <300ms (平均)

### 准确率指标
- **去重准确率**: >95%
- **情感分析准确率**: >90%
- **实体识别准确率**: >85%
- **搜索相关性**: >80%

## 🔍 监控和调试

### 日志配置

```python
from loguru import logger

# 配置日志级别
logger.add("data_processor.log", level="INFO")

# 查看处理统计
stats = data_processor_manager.get_system_statistics()
print(json.dumps(stats, indent=2, ensure_ascii=False))
```

### 健康检查

```python
# 检查组件健康状态
health = await data_processor_manager._check_components_health()

for component, status in health.items():
    print(f"{component}: {status['status']}")
```

### 性能监控

```python
# 获取处理统计
pipeline_stats = pipeline.get_processing_statistics()
nlp_stats = nlp_processor.get_processing_statistics()
vector_stats = vector_manager.get_statistics()
```

## 🛠️ 故障排除

### 常见问题

1. **Elasticsearch连接失败**
   ```bash
   # 检查Elasticsearch状态
   curl -X GET "localhost:9200/_cluster/health"
   ```

2. **Qdrant连接失败**
   ```bash
   # 检查Qdrant状态
   curl -X GET "localhost:6333/collections"
   ```

3. **内存不足**
   - 减少批处理大小
   - 增加系统内存
   - 使用流式处理

4. **处理速度慢**
   - 检查硬件资源
   - 优化批处理大小
   - 启用并行处理

### 调试模式

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 运行单步调试
result = pipeline.process_documents(
    documents,
    debug=True,
    verbose=True
)
```

## 📈 扩展和定制

### 添加自定义处理器

```python
from processors.base import BaseProcessor

class CustomProcessor(BaseProcessor):
    def process(self, document):
        # 自定义处理逻辑
        return processed_document

# 注册到管道
pipeline.add_processor(CustomProcessor())
```

### 自定义NLP模型

```python
from nlp.base import BaseNLPModel

class CustomNLPModel(BaseNLPModel):
    def analyze(self, text):
        # 自定义NLP分析
        return analysis_result

# 注册模型
nlp_processor.register_model('custom', CustomNLPModel())
```

### 扩展搜索功能

```python
from elasticsearch.base import BaseSearchEngine

class CustomSearchEngine(BaseSearchEngine):
    def custom_search(self, query, **kwargs):
        # 自定义搜索逻辑
        return search_results
```

## 📚 API参考

详细的API文档请参考各模块的docstring和类型注解。

### 主要接口

- `DataProcessorManager`: 主管理器
- `DataProcessingPipeline`: 数据处理管道
- `NLPProcessor`: NLP处理器
- `VectorManager`: 向量管理器
- `SearchEngine`: 搜索引擎
- `SyncManager`: 同步管理器

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 📞 支持

如有问题或建议，请创建Issue或联系开发团队。

---

**投资情报搜索引擎数据处理模块** - 为智能投资决策提供强大的数据处理能力。
