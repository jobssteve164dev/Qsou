# Qsou 投资情报搜索引擎 - 开发环境管理
.PHONY: help install setup-env verify init-db init-es init-qdrant dev clean test

# 默认目标
help:  ## 显示帮助信息
	@echo "Qsou 投资情报搜索引擎 - 开发命令"
	@echo "=================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## 安装Python依赖包
	@echo "🔧 安装Python依赖包..."
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✅ 依赖包安装完成"

setup-env:  ## 设置开发环境
	@echo "⚙️  设置开发环境..."
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "📝 已创建 .env 文件，请根据需要修改配置"; \
	fi
	@if [ ! -d venv ]; then \
		python -m venv venv; \
		echo "🐍 已创建Python虚拟环境"; \
	fi
	@if [ ! -d logs ]; then \
		mkdir -p logs; \
		echo "📁 已创建日志目录"; \
	fi
	@echo "✅ 开发环境设置完成"

verify:  ## 验证所有服务是否正常运行
	@echo "🔍 验证开发环境..."
	python scripts/verify_setup.py

init-db:  ## 初始化PostgreSQL数据库
	@echo "🗄️  初始化数据库..."
	python scripts/init_database.py

init-es:  ## 初始化Elasticsearch索引
	@echo "🔍 初始化Elasticsearch..."
	python scripts/init_elasticsearch.py

init-qdrant:  ## 初始化Qdrant向量数据库
	@echo "🔮 初始化Qdrant..."
	python scripts/init_qdrant.py

init: init-db init-es init-qdrant  ## 初始化所有数据存储服务
	@echo "🎉 所有数据存储服务初始化完成！"

dev-setup: setup-env install verify init  ## 完整开发环境搭建
	@echo "🚀 开发环境已完全准备就绪！"
	@echo ""
	@echo "下一步操作："
	@echo "1. 启动API服务: cd api-gateway && python -m uvicorn app.main:app --reload"
	@echo "2. 启动前端: cd web-frontend && npm run dev"
	@echo "3. 启动Celery: celery -A data-processor.tasks worker --loglevel=info"

# 开发环境管理 (新增 dev.sh 集成)
dev-start:  ## 启动完整开发环境 (使用 dev.sh)
	@echo "🚀 启动完整开发环境..."
	./dev.sh start

dev-stop:  ## 停止开发环境 (使用 dev.sh)
	@echo "🛑 停止开发环境..."
	./dev.sh stop

dev-restart:  ## 重启开发环境 (使用 dev.sh)
	@echo "🔄 重启开发环境..."
	./dev.sh restart

dev-status:  ## 查看开发环境状态
	@echo "📊 检查开发环境状态..."
	./dev.sh status

dev-logs:  ## 查看开发环境日志
	@echo "📋 查看开发环境日志..."
	@echo "用法: make dev-logs SERVICE=api"
	@if [ -n "$(SERVICE)" ]; then \
		./dev.sh logs $(SERVICE); \
	else \
		./dev.sh logs; \
	fi

# 独立服务启动 (传统方式)
dev-api:  ## 启动API开发服务器
	@echo "🔥 启动API开发服务器..."
	cd api-gateway && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## 启动前端开发服务器
	@echo "🎨 启动前端开发服务器..."
	cd web-frontend && npm run dev

dev-celery:  ## 启动Celery工作进程
	@echo "⚙️  启动Celery工作进程..."
	celery -A data-processor.tasks worker --loglevel=info

dev-flower:  ## 启动Celery监控面板
	@echo "🌸 启动Celery监控面板..."
	celery -A data-processor.tasks flower --port=5555

# 爬虫相关命令
crawl-news:  ## 运行新闻爬虫
	@echo "📰 启动新闻爬虫..."
	cd crawler && scrapy crawl financial_news

crawl-announcements:  ## 运行公告爬虫
	@echo "📢 启动公告爬虫..."
	cd crawler && scrapy crawl company_announcements

crawl-all:  ## 运行所有爬虫
	@echo "🕷️  启动所有爬虫..."
	cd crawler && scrapy crawl financial_news &
	cd crawler && scrapy crawl company_announcements &
	wait

# 测试相关命令
test:  ## 运行测试
	@echo "🧪 运行测试..."
	pytest tests/ -v

test-coverage:  ## 运行测试并生成覆盖率报告
	@echo "📊 运行测试覆盖率..."
	pytest tests/ --cov=. --cov-report=html --cov-report=term

# 代码质量
lint:  ## 代码风格检查
	@echo "🔍 代码风格检查..."
	flake8 api-gateway/ data-processor/ crawler/ scripts/
	black --check api-gateway/ data-processor/ crawler/ scripts/

format:  ## 代码格式化
	@echo "✨ 代码格式化..."
	black api-gateway/ data-processor/ crawler/ scripts/
	isort api-gateway/ data-processor/ crawler/ scripts/

# 清理命令
clean:  ## 清理临时文件
	@echo "🧹 清理临时文件..."
	./dev.sh clean

clean-manual:  ## 手动清理临时文件 (传统方式)
	@echo "🧹 手动清理临时文件..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

clean-logs:  ## 清理日志文件
	@echo "📝 清理日志文件..."
	rm -rf logs/*.log

clean-data:  ## 清理测试数据 (危险操作)
	@echo "⚠️  清理测试数据..."
	@read -p "确定要清理所有测试数据吗? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		python scripts/clean_test_data.py; \
	fi

# 监控命令
status:  ## 检查所有服务状态 (使用 dev.sh)
	@echo "📊 检查服务状态..."
	./dev.sh status

status-manual:  ## 手动检查服务状态 (传统方式)
	@echo "📊 手动检查服务状态..."
	@python scripts/check_services.py

logs:  ## 查看应用日志
	@echo "📋 查看应用日志..."
	tail -f logs/app.log

# 部署相关 (后续阶段)
build:  ## 构建应用
	@echo "🔨 构建应用..."
	@echo "Docker构建将在后续阶段实现"

deploy:  ## 部署应用
	@echo "🚀 部署应用..."
	@echo "部署脚本将在阶段七实现"

# 备份和恢复
backup-db:  ## 备份数据库
	@echo "💾 备份数据库..."
	pg_dump qsou_investment_intel > backups/db_$(shell date +%Y%m%d_%H%M%S).sql

# 文档生成
docs:  ## 生成API文档
	@echo "📚 生成API文档..."
	@echo "访问 http://localhost:8000/docs 查看FastAPI自动生成的文档"
