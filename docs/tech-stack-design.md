# 投资情报搜索引擎技术栈设计方案

## 1. 技术架构概览

### 1.1 整体架构原则
- **微服务架构**: 各组件松耦合，便于独立部署和扩展
- **容器化部署**: 使用Docker确保环境一致性和快速部署
- **水平扩展**: 支持根据负载动态扩展服务实例
- **高可用性**: 关键服务实现故障转移和负载均衡

### 1.2 技术选型标准
- **开源优先**: 选择成熟、活跃的开源项目
- **社区支持**: 拥有活跃社区和完善文档
- **性能优秀**: 能够处理大规模数据和高并发请求
- **易于维护**: 学习曲线合理，便于团队掌握

## 2. 核心技术栈详细设计

### 2.1 数据采集层

#### Scrapy + Scrapy-Redis
- **核心功能**: 分布式网络爬虫框架
- **优势**: 成熟稳定、支持分布式、丰富的中间件生态
- **配置要点**:
  ```python
  # settings.py关键配置
  SCHEDULER = "scrapy_redis.scheduler.Scheduler"
  DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
  ITEM_PIPELINES = {
      'scrapy_redis.pipelines.RedisPipeline': 300,
  }
  DOWNLOAD_DELAY = 1  # 合规访问频率
  ROBOTSTXT_OBEY = True  # 遵循robots.txt
  ```

#### Scrapy-Splash
- **用途**: 处理JavaScript渲染的页面
- **场景**: 现代财经网站的动态内容抓取
- **配置**: 与Scrapy无缝集成，支持Lua脚本

### 2.2 数据存储层

#### Elasticsearch 8.x
- **核心功能**: 分布式搜索引擎
- **索引策略**:
  ```json
  {
    "mappings": {
      "properties": {
        "title": {"type": "text", "analyzer": "ik_smart"},
        "content": {"type": "text", "analyzer": "ik_smart"}, 
        "publish_time": {"type": "date"},
        "source": {"type": "keyword"},
        "category": {"type": "keyword"},
        "sentiment_score": {"type": "float"}
      }
    }
  }
  ```

#### Qdrant向量数据库
- **核心功能**: 高性能向量相似度搜索
- **优势**: 开源、支持高并发、内存优化
- **配置方案**:
  ```yaml
  # qdrant配置
  storage:
    storage_path: ./storage
  service:
    http_port: 6333
    grpc_port: 6334
  ```

#### PostgreSQL
- **用途**: 存储结构化元数据
- **数据模型**:
  - 用户管理 (users)
  - 数据源管理 (data_sources)
  - 爬虫任务记录 (crawl_jobs)
  - 系统配置 (system_configs)

#### Redis
- **用途**: 缓存和任务队列
- **使用场景**:
  - Scrapy分布式队列
  - API响应缓存
  - 会话存储
  - 任务调度状态

### 2.3 数据处理层

#### Celery + Redis
- **功能**: 异步任务处理和调度
- **任务类型**:
  ```python
  # 主要任务定义
  @app.task
  def process_crawled_data(data_id):
      """处理爬取的数据"""
      pass
  
  @app.task  
  def generate_embeddings(text_id):
      """生成文本向量"""
      pass
  
  @app.task
  def update_search_index(doc_id):
      """更新搜索索引"""
      pass
  ```

#### Hugging Face Transformers
- **功能**: 自然语言处理和文本向量化
- **模型选择**:
  - **中文BERT**: `bert-base-chinese`
  - **金融专用**: `FinBERT-Chinese`
  - **多语言**: `distilbert-base-multilingual-cased`

### 2.4 API服务层

#### FastAPI
- **优势**: 高性能、类型安全、自动文档生成
- **核心API设计**:
  ```python
  from fastapi import FastAPI, HTTPException
  from pydantic import BaseModel
  
  app = FastAPI()
  
  # 搜索API
  @app.get("/api/search")
  async def search(q: str, limit: int = 10):
      """通用搜索接口"""
      pass
  
  # 语义搜索API  
  @app.post("/api/semantic-search")
  async def semantic_search(query: str):
      """向量相似度搜索"""
      pass
  
  # 主题监控API
  @app.post("/api/topics")
  async def create_topic_monitor(topic: TopicModel):
      """创建主题监控任务"""
      pass
  ```

#### Nginx
- **功能**: 反向代理和负载均衡
- **配置要点**:
  ```nginx
  upstream fastapi_backend {
      server api1:8000;
      server api2:8000;  
  }
  
  server {
      listen 80;
      location /api/ {
          proxy_pass http://fastapi_backend;
      }
      location / {
          proxy_pass http://frontend:3000;
      }
  }
  ```

### 2.5 前端展示层

#### Next.js + TypeScript
- **架构**: SSR + CSR混合渲染
- **关键组件**:
  ```typescript
  // 搜索组件
  interface SearchProps {
    onSearch: (query: string) => void;
    results: SearchResult[];
    loading: boolean;
  }
  
  const SearchComponent: React.FC<SearchProps> = ({ onSearch, results, loading }) => {
    // 搜索界面实现
  }
  
  // 主题监控组件
  interface TopicMonitorProps {
    topics: Topic[];
    onCreateTopic: (topic: Topic) => void;
  }
  ```

#### Ant Design
- **UI组件库**: 企业级React UI解决方案
- **主要组件**: Table、Form、DatePicker、Charts等

### 2.6 基础设施层

#### Docker + Docker Compose
- **服务编排配置**:
  ```yaml
  version: '3.8'
  services:
    elasticsearch:
      image: elasticsearch:8.11.0
      environment:
        - discovery.type=single-node
        - ES_JAVA_OPTS=-Xms1g -Xmx1g
    
    qdrant:
      image: qdrant/qdrant:latest
      ports:
        - "6333:6333"
      volumes:
        - ./qdrant_storage:/qdrant/storage
    
    redis:
      image: redis:7.2-alpine
      ports:
        - "6379:6379"
    
    postgres:
      image: postgres:15-alpine
      environment:
        POSTGRES_DB: investment_intel
        POSTGRES_USER: qsou
        POSTGRES_PASSWORD: secure_password
    
    api:
      build: ./api
      depends_on:
        - elasticsearch
        - redis
        - postgres
      environment:
        - DATABASE_URL=postgresql://qsou:password@postgres/investment_intel
    
    frontend:
      build: ./frontend
      ports:
        - "3000:3000"
      depends_on:
        - api
  ```

## 3. 性能优化策略

### 3.1 搜索性能优化
- **索引优化**: 合理分片和副本配置
- **查询优化**: 使用bool查询组合条件
- **缓存策略**: 热门查询结果缓存
- **分页优化**: 使用scroll API处理深度分页

### 3.2 数据处理性能
- **批处理**: 批量处理文档以提高效率
- **并行处理**: 利用多进程/多线程处理
- **增量更新**: 只处理变化的数据
- **资源管理**: 合理配置内存和CPU资源

### 3.3 系统监控方案
- **Prometheus**: 指标收集和存储
- **Grafana**: 监控仪表板
- **ELK Stack**: 日志聚合和分析
- **健康检查**: 各服务的健康状态监控

## 4. 开发与部署流程

### 4.1 开发环境配置
```bash
# 快速启动开发环境
git clone <repository>
cd investment-intelligence-engine
cp .env.example .env  # 配置环境变量
docker-compose -f docker-compose.dev.yml up -d
```

### 4.2 生产环境部署
```bash
# 生产环境部署
docker-compose -f docker-compose.prod.yml up -d
# 初始化搜索索引
docker-compose exec api python scripts/init_elasticsearch.py
# 启动爬虫任务
docker-compose exec api python scripts/start_crawlers.py
```

### 4.3 扩展性设计
- **水平扩展**: 通过增加容器实例扩展性能
- **垂直扩展**: 根据负载调整资源配置
- **服务拆分**: 根据业务需求拆分微服务
- **存储扩展**: 支持分布式存储集群

这个技术栈设计方案提供了完整的、基于开源技术的投资情报搜索引擎解决方案，具备高性能、高可用、易扩展的特性。
