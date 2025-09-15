# 本地开发环境搭建指南

## 系统要求

- **操作系统**: Windows 10/11, macOS 10.15+, 或 Linux (Ubuntu 18.04+)
- **内存**: 8GB+ RAM 推荐
- **存储**: 20GB+ 可用空间
- **Python**: 3.8+ 
- **Node.js**: 16.x+
- **Java**: 11+ (Elasticsearch需要)

## 1. 安装 Java JDK

### Windows
```bash
# 使用 Chocolatey
choco install openjdk11

# 或者手动下载安装 OpenJDK 11
# https://adoptopenjdk.net/
```

### macOS
```bash
# 使用 Homebrew
brew install openjdk@11

# 添加到 PATH
echo 'export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"' >> ~/.zshrc
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install openjdk-11-jdk
```

## 2. 安装 Elasticsearch

### Windows
```bash
# 下载 Elasticsearch 8.11.0
curl -L -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.0-windows-x86_64.zip
unzip elasticsearch-8.11.0-windows-x86_64.zip
cd elasticsearch-8.11.0

# 安装 IK 中文分词器
bin/elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.11.0/elasticsearch-analysis-ik-8.11.0.zip
```

### macOS
```bash
# 使用 Homebrew
brew tap elastic/tap
brew install elastic/tap/elasticsearch-full

# 或者手动安装
curl -L -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.0-darwin-x86_64.tar.gz
tar -xvf elasticsearch-8.11.0-darwin-x86_64.tar.gz
cd elasticsearch-8.11.0

# 安装 IK 分词器
bin/elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.11.0/elasticsearch-analysis-ik-8.11.0.zip
```

### Linux
```bash
# 下载并安装
curl -L -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.0-linux-x86_64.tar.gz
tar -xvf elasticsearch-8.11.0-linux-x86_64.tar.gz
cd elasticsearch-8.11.0

# 安装 IK 分词器
bin/elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.11.0/elasticsearch-analysis-ik-8.11.0.zip
```

### 配置 Elasticsearch
将以下配置添加到 `config/elasticsearch.yml`:
```yaml
# 基本配置
cluster.name: qsou-investment-intelligence
node.name: node-1
network.host: localhost
http.port: 9200
discovery.type: single-node

# 安全配置 (开发环境可以禁用)
xpack.security.enabled: false
xpack.security.enrollment.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false

# 性能配置
bootstrap.memory_lock: true
```

### 启动 Elasticsearch
```bash
# Windows
bin/elasticsearch.bat

# macOS/Linux
bin/elasticsearch
```

验证安装：访问 http://localhost:9200

## 3. 安装 PostgreSQL

### Windows
```bash
# 使用 Chocolatey
choco install postgresql

# 或下载安装包
# https://www.postgresql.org/download/windows/
```

### macOS
```bash
# 使用 Homebrew
brew install postgresql
brew services start postgresql

# 创建数据库用户
createuser --superuser qsou
createdb -O qsou qsou_investment_intel
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建用户和数据库
sudo -u postgres createuser --superuser qsou
sudo -u postgres createdb -O qsou qsou_investment_intel
```

## 4. 安装 Redis

### Windows
```bash
# 使用 Chocolatey
choco install redis-64

# 或下载 Windows 版本
# https://github.com/microsoftarchive/redis/releases
```

### macOS
```bash
# 使用 Homebrew
brew install redis
brew services start redis
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install redis-server

# 启动服务
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

验证安装：
```bash
redis-cli ping
# 应该返回 PONG
```

## 5. 安装 Qdrant 向量数据库

### 使用预编译二进制文件 (推荐)

#### Windows
```bash
# 下载 Qdrant
curl -L https://github.com/qdrant/qdrant/releases/download/v1.7.3/qdrant-x86_64-pc-windows-gnu.zip -o qdrant.zip
unzip qdrant.zip
```

#### macOS
```bash
# 使用 Homebrew
brew install qdrant/tap/qdrant

# 或手动下载
curl -L https://github.com/qdrant/qdrant/releases/download/v1.7.3/qdrant-x86_64-apple-darwin.tar.gz -o qdrant.tar.gz
tar -xzf qdrant.tar.gz
```

#### Linux
```bash
curl -L https://github.com/qdrant/qdrant/releases/download/v1.7.3/qdrant-x86_64-unknown-linux-gnu.tar.gz -o qdrant.tar.gz
tar -xzf qdrant.tar.gz
```

### 配置 Qdrant
创建配置文件 `config/qdrant/config.yaml`:
```yaml
storage:
  storage_path: ./qdrant_storage
service:
  host: "0.0.0.0"
  http_port: 6333
  grpc_port: 6334
telemetry_disabled: true
```

### 启动 Qdrant
```bash
./qdrant --config-path config/qdrant/config.yaml
```

验证安装：访问 http://localhost:6333

## 6. 配置 Python 开发环境

### 创建虚拟环境
```bash
# 在项目根目录
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 安装基础依赖
```bash
# 升级 pip
python -m pip install --upgrade pip

# 安装基础包
pip install fastapi uvicorn scrapy scrapy-redis celery redis psycopg2-binary elasticsearch qdrant-client transformers torch pandas numpy requests python-dotenv pydantic
```

## 7. 配置 Node.js 环境 (前端)

```bash
# 在 web-frontend 目录
cd web-frontend

# 初始化 Next.js 项目
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

# 安装额外依赖
npm install antd @ant-design/icons axios swr
```

## 8. 环境变量配置

创建 `.env` 文件：
```bash
# 数据库配置
DATABASE_URL=postgresql://qsou:password@localhost:5432/qsou_investment_intel
REDIS_URL=redis://localhost:6379/0

# Elasticsearch 配置
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200

# Qdrant 配置
QDRANT_HOST=localhost
QDRANT_PORT=6333

# API 配置
API_HOST=localhost
API_PORT=8000

# 开发模式
DEBUG=True
ENVIRONMENT=development
```

## 9. 验证安装

运行验证脚本：
```bash
python scripts/verify_setup.py
```

## 常见问题解决

### Elasticsearch 内存不足
在 `config/jvm.options` 中调整内存设置：
```
-Xms1g
-Xmx1g
```

### PostgreSQL 连接问题
检查 `pg_hba.conf` 配置，确保本地连接被允许。

### Redis 权限问题
在 Linux 上，可能需要调整 Redis 配置文件的权限设置。

### Python 包安装失败
如果某些包安装失败，尝试：
```bash
pip install --upgrade setuptools wheel
pip install package-name --no-cache-dir
```

## 下一步

安装完成后，可以运行：
1. `python scripts/init_database.py` - 初始化数据库表
2. `python scripts/init_elasticsearch.py` - 创建 Elasticsearch 索引
3. `python scripts/test_connections.py` - 测试所有服务连接

完成后，您的本地开发环境就已经准备就绪！
