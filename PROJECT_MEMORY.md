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
*   **[2025-01-27]**: 实现统一日志收集系统。**原因**: 集中管理所有服务日志，便于调试和监控；实现智能日志轮转（5万行限制）；提供强大的搜索和统计功能。**实现**: `dev.sh`集成日志收集器，自动收集API、前端、Celery、ES、Qdrant等所有组件日志到`logs/unified.log`。

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

### 基础开发命令
*   **快速启动**: `./dev.sh start` (推荐) 或 `python scripts/quick_start.py`
*   **停止所有服务**: `./dev.sh stop`
*   **重启环境**: `./dev.sh restart`
*   **检查服务状态**: `./dev.sh status`
*   **健康检查**: `./dev.sh health`

### 自动启动的数据服务 [2025-01-27 更新]
开发环境会自动安装并启动以下服务（如果未运行）：
*   **Redis**: 消息队列和缓存服务（端口 6379）
    - Windows: 自动下载Redis for Windows到`vendor/redis`并启动
    - Linux/Mac: 需要预先安装redis-server
    - 安装位置：`vendor/redis/` (与Elasticsearch、Qdrant一致)
*   **Elasticsearch**: 全文搜索引擎（端口 9200）
    - 安装位置：`vendor/elasticsearch/`
*   **Qdrant**: 向量数据库（端口 6333）
    - 安装位置：`vendor/qdrant/`

### 统一日志管理系统 (Unified Logging System) [2025-01-27 新增]
*   **实时查看统一日志**: `./dev.sh unified-log`
*   **日志统计信息**: `./dev.sh log-stats`
*   **搜索日志**: `./dev.sh log-search <pattern> [service]`
*   **按级别查看**: `./dev.sh log-level <ERROR|WARN|INFO|DEBUG>`
*   **单服务日志**: `./dev.sh logs <service>`

### Makefile命令（备选）
*   **开发环境搭建**: `make dev-setup`
*   **验证环境**: `make verify`
*   **初始化数据存储**: `make init`
*   **启动API服务**: `make dev-api`
*   **启动前端服务**: `make dev-frontend`
*   **启动任务队列**: `make dev-celery`
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

---

## 7. 技术问题与解决方案 (Technical Issues & Solutions)

### 日志收集系统内存溢出问题 [2025-01-27]
**问题**: 使用`tail -F`的Shell版本日志收集器在Windows Git Bash环境下导致内存溢出
- 症状：fork进程失败，报错"Resource temporarily unavailable"
- 原因：多个tail进程累积，Git Bash的Cygwin层性能差

**解决方案**: 改用Python实现的日志收集器
- 文件：`scripts/unified_logger.py`
- 优势：单进程、跨平台、内存占用低、支持批量处理
- 配置：`ENABLE_UNIFIED_LOG=true`，`UNIFIED_LOG_MAX_LINES=30000`

### Celery Flower监控问题 [2025-01-27]
**问题**: Celery监控服务无法启动
- 原因：flower包未安装到虚拟环境
- 解决：在requirements.txt中添加`flower==2.0.1`

### Windows开发环境优化 [2025-01-27]
- 紧急停止脚本：`emergency_stop.bat`
- Python脚本编码：设置`PYTHONIOENCODING=utf-8`避免中文乱码
- 内存管理：避免使用shell的fork密集型操作

### Celery Worker问题解决 [2025-09-16]
**问题1**: Windows权限错误 - `PermissionError: [WinError 5] 拒绝访问`
- 原因：Windows不支持prefork进程池模式
- 解决：创建`data-processor/celeryconfig.py`，Windows使用solo池

**问题2**: Elasticsearch模块冲突
- 原因：本地目录名与pip包名冲突
- 解决：重命名`data-processor/elasticsearch`为`es_indexing`

**问题3**: Qdrant版本不兼容
- 原因：客户端1.7.0与服务器1.15.4不匹配
- 解决：升级qdrant-client到1.12.1

**问题4**: 依赖包缺失
- 原因：api-gateway和data-processor依赖不一致
- 解决：添加jieba、sentence-transformers到api-gateway/requirements.txt
