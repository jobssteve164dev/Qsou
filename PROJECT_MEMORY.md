# 项目长期记忆 (PROJECT_MEMORY.md)

*最后更新: 2025-01-27 12:00:00*

---

## 1. 项目概述 (Project Overview)

### a. 核心目标 (High-Level Goal)
构建一个自部署的投资情报搜索引擎，为量化交易提供可靠的实时数据源。系统应具备双重能力：1)像Google一样的通用搜索功能，让用户自由搜索投资相关信息；2)像情报工作人员一样，能根据指定主题自动搜索、分析并整理信息到向量库中。

### b. 技术栈 (Tech Stack)
*   **搜索引擎核心**: Elasticsearch 8.x (开源搜索引擎)
*   **网络爬虫**: Scrapy + Scrapy-Redis (分布式爬虫框架)
*   **向量数据库**: Qdrant (开源向量数据库) 
*   **后端框架**: FastAPI (Python, 高性能API框架)
*   **前端框架**: Next.js + TypeScript (现代化前端栈)
*   **消息队列**: Redis + Celery (任务调度和异步处理)
*   **数据库**: PostgreSQL (结构化数据) + MongoDB (非结构化数据)
*   **AI/NLP**: Hugging Face Transformers (文本分析和向量化)
*   **监控**: Prometheus + Grafana (系统监控)
*   **容器化**: Docker + Docker Compose (便于部署)

---

## 2. 核心架构决策 (Key Architectural Decisions)

*   **[2025-01-27]**: 选择Elasticsearch作为搜索引擎核心。**原因**: 开源、成熟、支持全文搜索和复杂查询，有丰富的金融数据处理插件。
*   **[2025-01-27]**: 选择Qdrant作为向量数据库。**原因**: 专门为AI应用设计，支持高维向量搜索，开源且性能优秀。
*   **[2025-01-27]**: 采用微服务架构。**原因**: 各组件独立部署，便于扩展和维护，降低系统耦合度。

---

## 3. 模块职责表 (Codebase Map)

*   `crawler/`: 分布式网络爬虫模块，负责数据采集
*   `search-engine/`: Elasticsearch配置和搜索API
*   `vector-db/`: Qdrant向量数据库和相似度搜索
*   `api-gateway/`: FastAPI后端服务，统一API接口
*   `web-frontend/`: Next.js前端用户界面
*   `data-processor/`: 数据清洗、分析和向量化处理
*   `scheduler/`: Celery任务调度器
*   `monitoring/`: 系统监控和日志管理

---

## 4. 标准工作流与命令 (Standard Workflows & Commands)

*   **快速启动**: `python scripts/quick_start.py`
*   **开发环境搭建**: `make dev-setup`
*   **验证环境**: `make verify`
*   **初始化数据存储**: `make init`
*   **启动API服务**: `make dev-api`
*   **启动前端服务**: `make dev-frontend`
*   **启动任务队列**: `make dev-celery`
*   **检查服务状态**: `make status`
*   **运行爬虫任务**: `make crawl-news`

---

## 5. 用户特定偏好与规范 (User-Specific Conventions)

*   **数据来源合规**: 严格遵循robots.txt，实施合理的访问频率限制
*   **实时性要求**: 新闻数据延迟不超过5分钟，公告数据延迟不超过1分钟
*   **向量化标准**: 使用多语言BERT模型进行文本嵌入，支持中英文金融术语
*   **搜索质量**: 搜索结果相关性要求>85%，响应时间<200ms

---

## 6. 重要提醒 (Critical Reminders)

*   **法律合规**: 所有数据源必须检查使用条款，禁止抓取明确禁止的内容
*   **反爬虫应对**: 实施IP轮换、用户代理轮换、访问频率控制
*   **数据质量**: 建立数据质量评估机制，过滤垃圾信息和重复内容
*   **敏感信息**: 避免存储个人隐私信息，遵循GDPR等数据保护法规
