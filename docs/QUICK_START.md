# 🚀 Qsou 投资情报搜索引擎 - 快速开始指南

## ⚡ 一键快速启动

```bash
# 1. 克隆项目并进入目录
git clone <your-repository>
cd Qsou

# 2. 启动开发环境 (推荐)
./dev.sh start

# 或者使用快速启动脚本
python scripts/quick_start.py

# 3. 按照提示完成环境配置
```

## 🎯 超快速启动 (已配置环境)

如果您已经完成过初始配置：

```bash
# 一键启动所有服务
./dev.sh start

# 或使用 Make 命令
make dev-start
```

## 📋 详细步骤

### 第一步：环境准备
确保您的系统已安装：
- **Python 3.8+**
- **Java 11+** (Elasticsearch需要)
- **PostgreSQL**
- **Redis**
- **Elasticsearch 8.x** (含IK中文分词器)
- **Qdrant** (向量数据库)

📖 **详细安装指南**: [docs/local-development-setup.md](docs/local-development-setup.md)

### 第二步：项目初始化

```bash
# 创建Python虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate
# 或 (macOS/Linux)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp env.example .env
# 编辑.env文件，配置数据库密码等参数
```

### 第三步：验证环境

```bash
# 验证所有服务连接
python scripts/verify_setup.py

# 或使用Make命令
make verify
```

### 第四步：初始化数据存储

```bash
# 初始化所有数据存储服务
make init

# 或分别初始化
make init-db        # PostgreSQL数据库
make init-es        # Elasticsearch索引
make init-qdrant    # Qdrant向量数据库
```

### 第五步：启动开发服务

```bash
# 方式一：使用Make命令 (推荐)
make dev-api        # 启动API服务 (8000端口)
make dev-frontend   # 启动前端服务 (3000端口)  
make dev-celery     # 启动任务队列

# 方式二：手动启动
cd api-gateway && uvicorn app.main:app --reload
cd web-frontend && npm run dev
celery -A data-processor.tasks worker --loglevel=info
```

## 🔍 验证安装

### 检查服务状态
```bash
make status
# 或
python scripts/check_services.py
```

### 访问服务
- **API文档**: http://localhost:8000/docs
- **前端界面**: http://localhost:3000
- **Elasticsearch**: http://localhost:9200
- **Qdrant Dashboard**: http://localhost:6333/dashboard

## 📚 开发命令参考

### dev.sh 脚本命令
| 命令 | 功能 | Make 等效命令 |
|------|------|--------------|
| `./dev.sh start` | 启动完整开发环境 | `make dev-start` |
| `./dev.sh stop` | 停止开发环境 | `make dev-stop` |
| `./dev.sh restart` | 重启开发环境 | `make dev-restart` |
| `./dev.sh status` | 查看服务状态 | `make dev-status` |
| `./dev.sh logs [service]` | 查看日志 | `make dev-logs SERVICE=api` |
| `./dev.sh clean` | 清理临时文件 | `make clean` |

### 传统 Make 命令
| 命令 | 功能 |
|------|------|
| `make help` | 显示所有可用命令 |
| `make dev-setup` | 完整开发环境搭建 |
| `make verify` | 验证服务连接 |
| `make init` | 初始化所有数据存储 |
| `make dev-api` | 单独启动API服务 |
| `make dev-frontend` | 单独启动前端服务 |
| `make dev-celery` | 单独启动任务队列 |
| `make test` | 运行测试 |

## 🛠️ 开发工具

### 项目结构
```
Qsou/
├── api-gateway/          # FastAPI后端服务
├── web-frontend/         # Next.js前端应用
├── crawler/              # Scrapy爬虫模块
├── data-processor/       # 数据处理和向量化
├── config/               # 各服务配置文件
├── scripts/              # 自动化脚本
├── docs/                 # 项目文档
├── requirements.txt      # Python依赖
├── Makefile             # 自动化命令
└── env.example          # 环境变量模板
```

### 核心脚本
- `verify_setup.py` - 验证开发环境
- `init_database.py` - 初始化数据库
- `init_elasticsearch.py` - 初始化搜索引擎
- `init_qdrant.py` - 初始化向量数据库
- `check_services.py` - 检查服务状态

## 🐛 常见问题

### Q: Elasticsearch启动失败？
A: 确保Java 11+已安装，检查内存配置（需要至少2GB可用内存）

### Q: Qdrant连接失败？
A: 确认Qdrant服务已启动，端口6333可访问

### Q: Python包安装失败？
A: 尝试升级pip：`pip install --upgrade pip setuptools wheel`

### Q: 数据库连接失败？
A: 检查PostgreSQL服务状态和.env配置中的数据库密码

## 📞 获取帮助

- 📖 **完整文档**: [docs/local-development-setup.md](docs/local-development-setup.md)
- 🏗️ **架构设计**: [tech-stack-design.md](tech-stack-design.md)
- 📋 **项目规划**: [plan report/](plan%20report/)
- ⚖️ **合规指南**: [legal-compliance-guide.md](legal-compliance-guide.md)

## ✅ 成功标志

当您看到以下信息时，说明环境搭建成功：

```
🎉 所有服务验证通过！开发环境已准备就绪。

🚀 下一步操作:
1. 运行 'python scripts/init_database.py' 初始化数据库
2. 运行 'python scripts/init_elasticsearch.py' 创建搜索索引  
3. 开始开发！
```

现在您可以开始开发投资情报搜索引擎了！🎊
