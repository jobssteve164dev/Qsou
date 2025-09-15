#!/bin/bash

# Qsou 投资情报搜索引擎 - 开发环境启动脚本
# 支持自动依赖检测、端口清理、进程管理和自动清理

set -euo pipefail  # 严格模式

# ============================================
# 脚本配置
# ============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/dev.local"
PID_DIR="${SCRIPT_DIR}/pids"
LOG_DIR="${SCRIPT_DIR}/logs"

# 颜色定义
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[0;37m'
readonly NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# ============================================
# 配置加载
# ============================================
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        log_info "加载配置文件: $CONFIG_FILE"
        # 安全地加载配置文件，只加载有效的变量定义，忽略注释和空行
        while IFS= read -r line || [[ -n "$line" ]]; do
            # 跳过注释行和空行
            if [[ $line =~ ^[[:space:]]*# ]] || [[ $line =~ ^[[:space:]]*$ ]]; then
                continue
            fi
            # 处理变量定义行
            if [[ $line =~ ^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*= ]]; then
                # 清理行，移除可能的注释
                line=$(echo "$line" | cut -d'#' -f1 | xargs)
                export "$line"
                log_debug "已加载配置: $line"
            fi
        done < "$CONFIG_FILE"
        log_info "配置文件加载完成"
    else
        log_error "配置文件不存在: $CONFIG_FILE"
        log_info "请先创建配置文件或运行: cp env.example .env"
        exit 1
    fi
}

# ============================================
# 系统检查
# ============================================
check_system() {
    log_step "检查系统环境..."
    
    # 检查操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
    else
        log_error "不支持的操作系统: $OSTYPE"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS"
    
    # 检查必要的命令
    local required_commands=("python" "node" "npm" "java" "curl" "wget")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_warn "命令 '$cmd' 未找到，请确保已安装"
        else
            log_debug "✓ $cmd: $(command -v "$cmd")"
        fi
    done
}

# ============================================
# 依赖检查和安装
# ============================================
check_python_deps() {
    log_step "检查Python依赖..."
    
    # 优先使用用户指定
    if [[ -n "${PYTHON_EXECUTABLE:-}" ]]; then
        PYTHON_CMD="$PYTHON_EXECUTABLE"
    else
        # 按平台选择Python命令
        if [[ "$OS" == "windows" ]]; then
            if command -v py &> /dev/null; then
                PYTHON_CMD="py -3"
            elif command -v python &> /dev/null; then
                PYTHON_CMD="python"
            elif command -v python3 &> /dev/null; then
                PYTHON_CMD="python3"
            else
                log_error "Python未安装或不在PATH中"
                exit 1
            fi
        else
            if command -v python3 &> /dev/null; then
                PYTHON_CMD="python3"
            elif command -v python &> /dev/null; then
                PYTHON_CMD="python"
            else
                log_error "Python未安装或不在PATH中"
                exit 1
            fi
        fi
    fi
    
    log_info "使用Python: $PYTHON_CMD"
    local python_version
    python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Python版本: $python_version"
    
    # Windows环境特殊处理
    if [[ "$OS" == "windows" ]]; then
        # 检查是否是WindowsApps版本的Python（可能有权限问题）
        if [[ "$PYTHON_CMD" =~ WindowsApps ]]; then
            log_warn "检测到WindowsApps版本的Python，可能存在权限问题"
            log_info "建议安装标准版本的Python 3.8+"
        fi
        
        # 设置Windows下的Python可执行文件路径
        PYTHON_EXE="python.exe"
        if [[ -f "venv/Scripts/python.exe" ]]; then
            PYTHON_EXE="venv/Scripts/python.exe"
        fi
    fi
    
    # 在 api-gateway 创建并使用专属虚拟环境（避免全局环境差异）
    if [[ -d "api-gateway" ]]; then
        if [[ "$OS" == "windows" ]]; then
            if [[ ! -f "api-gateway/.venv/Scripts/python.exe" ]]; then
                log_info "为API创建虚拟环境 (Windows)..."
                (cd api-gateway && eval "$PYTHON_CMD -m venv .venv")
            fi
        else
            if [[ ! -f "api-gateway/.venv/bin/python" ]]; then
                log_info "为API创建虚拟环境 (Unix)..."
                (cd api-gateway && eval "$PYTHON_CMD -m venv .venv")
            fi
        fi
        # 检查并安装API依赖（已安装则跳过）
        if [[ -f "api-gateway/requirements.txt" ]]; then
            if [[ "$OS" == "windows" && -f "api-gateway/.venv/Scripts/python.exe" ]]; then
                API_PY="api-gateway/.venv/Scripts/python.exe"
            else
                API_PY="api-gateway/.venv/bin/python"
            fi
            if [[ -f "$API_PY" ]]; then
                # 通过导入核心包判断是否已满足依赖
                if [[ "${FORCE_REINSTALL:-false}" == "true" ]]; then
                    need_install=true
                    log_info "FORCE_REINSTALL=true，强制重新安装API依赖"
                else
                    if eval "$API_PY -c 'import fastapi, uvicorn, sqlalchemy, redis, elasticsearch, qdrant_client'" >/dev/null 2>&1; then
                        need_install=false
                        log_info "API依赖已满足，跳过安装（设置 FORCE_REINSTALL=true 可强制重装）"
                    else
                        need_install=true
                        log_info "检测到API依赖未完整，开始安装..."
                    fi
                fi

                if [[ "$need_install" == true ]]; then
                    if [[ "${UPGRADE_PIP:-false}" == "true" ]]; then
                        log_info "升级pip..."
                        eval "$API_PY -m pip install --upgrade pip" || true
                    fi
                    log_info "安装API依赖包（api-gateway/requirements.txt）..."
                    eval "$API_PY -m pip install -r api-gateway/requirements.txt" || {
                        log_warn "安装API依赖部分失败，后续可能影响启动"
                    }
                fi
            else
                log_warn "未找到API虚拟环境Python，可重试运行脚本以重新创建"
            fi
        fi
    fi
    
    # 根目录requirements可选安装提示
    if [[ -f "requirements.txt" ]]; then
        log_info "检测到根目录requirements.txt（可选），优先已为API安装专属依赖"
    fi
    
    # 检查基础依赖是否已安装
    log_info "检查基础Python包..."
    if $PYTHON_CMD -c "import sys; print(f'Python路径: {sys.executable}')" 2>/dev/null; then
        log_info "✓ Python环境正常"
    else
        log_warn "Python环境可能有问题"
    fi
    
    log_info "Python依赖检查完成"
}

check_node_deps() {
    log_step "检查Node.js依赖..."
    
    # 检查Node.js版本
    if ! command -v node &> /dev/null; then
        log_warn "Node.js未安装，跳过前端依赖检查"
        return
    fi
    
    local node_version
    node_version=$(node --version)
    log_info "Node.js版本: $node_version"
    
    # 检查前端依赖
    if [[ -d "web-frontend" && -f "web-frontend/package.json" ]]; then
        cd web-frontend
        if [[ ! -d "node_modules" ]]; then
            log_info "安装前端依赖..."
            npm install
        else
            log_info "前端依赖已存在，检查更新..."
            npm ci
        fi
        cd ..
    fi
}

# ============================================
# 端口管理
# ============================================
check_port() {
    local port=$1
    local service_name=$2
    
    if command -v lsof &> /dev/null; then
        # macOS/Linux with lsof
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            return 0  # 端口被占用
        fi
    elif [[ "$OS" == "windows" ]]; then
        # Windows with netstat
        if netstat -an | findstr ":$port " | findstr LISTENING >/dev/null 2>&1; then
            return 0  # 端口被占用
        fi
    elif command -v netstat &> /dev/null; then
        # Linux/Unix with netstat
        if netstat -tln 2>/dev/null | grep ":$port " >/dev/null; then
            return 0  # 端口被占用
        fi
    elif command -v ss &> /dev/null; then
        # Modern Linux with ss
        if ss -tln 2>/dev/null | grep ":$port " >/dev/null; then
            return 0  # 端口被占用
        fi
    fi
    return 1  # 端口空闲
}

kill_port() {
    local port=$1
    local service_name=$2
    
    log_warn "端口 $port 被占用 ($service_name)，尝试释放..."
    
    if command -v lsof &> /dev/null; then
        # macOS/Linux with lsof
        local pids
        pids=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill -TERM 2>/dev/null || true
            sleep 2
            # 如果还存在，强制杀死
            pids=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
            if [[ -n "$pids" ]]; then
                echo "$pids" | xargs kill -KILL 2>/dev/null || true
            fi
        fi
    elif [[ "$OS" == "windows" ]]; then
        # Windows with netstat and taskkill
        local pids
        pids=$(netstat -ano | findstr ":$port " | findstr LISTENING | awk '{print $5}' | sort -u)
        if [[ -n "$pids" ]]; then
            for pid in $pids; do
                taskkill /PID $pid /F 2>/dev/null || true
            done
        fi
    elif command -v fuser &> /dev/null; then
        # Linux with fuser
        fuser -k ${port}/tcp 2>/dev/null || true
    fi
    
    sleep 1
    if check_port $port "$service_name"; then
        log_error "无法释放端口 $port"
        return 1
    else
        log_info "端口 $port 已释放"
        return 0
    fi
}

clean_ports() {
    log_step "检查并清理端口..."
    
    local ports_to_check=(
        "${API_PORT:-8000}:API服务"
        "${FRONTEND_PORT:-3000}:前端服务"
        "${CELERY_FLOWER_PORT:-5555}:Celery监控"
        "${ELASTICSEARCH_PORT:-9200}:Elasticsearch"
        "${QDRANT_PORT:-6333}:Qdrant"
        "${POSTGRESQL_PORT:-5432}:PostgreSQL"
        "${REDIS_PORT:-6379}:Redis"
    )
    
    for port_info in "${ports_to_check[@]}"; do
        IFS=':' read -r port service_name <<< "$port_info"
        if check_port "$port" "$service_name"; then
            # 对于系统服务，只警告不杀死
            if [[ "$service_name" == "PostgreSQL" || "$service_name" == "Redis" || "$service_name" == "Elasticsearch" || "$service_name" == "Qdrant" ]]; then
                log_info "✓ $service_name 正在运行 (端口 $port)"
            else
                if [[ "${AUTO_KILL_PORTS:-true}" == "true" ]]; then
                    kill_port "$port" "$service_name"
                else
                    log_warn "端口 $port 被占用 ($service_name)，请手动处理或设置 AUTO_KILL_PORTS=true"
                fi
            fi
        else
            log_debug "✓ 端口 $port 空闲 ($service_name)"
        fi
    done
}

# ============================================
# 服务检查
# ============================================
check_services() {
    log_step "检查外部服务状态..."
    
    # 检查PostgreSQL
    if command -v pg_isready &> /dev/null; then
        if pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" >/dev/null 2>&1; then
            log_info "✓ PostgreSQL 运行中"
        else
            log_warn "PostgreSQL 未运行，请启动PostgreSQL服务"
        fi
    fi
    
    # 检查Redis
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping >/dev/null 2>&1; then
            log_info "✓ Redis 运行中"
        else
            log_warn "Redis 未运行，请启动Redis服务"
        fi
    fi
    
    # 检查Elasticsearch
    if curl -s "http://${ELASTICSEARCH_HOST:-localhost}:${ELASTICSEARCH_PORT:-9200}" >/dev/null 2>&1; then
        log_info "✓ Elasticsearch 运行中"
    else
        log_warn "Elasticsearch 未运行，请启动Elasticsearch服务"
    fi
    
    # 检查Qdrant
    if curl -s "http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections" >/dev/null 2>&1; then
        log_info "✓ Qdrant 运行中"
    else
        log_warn "Qdrant 未运行，请启动Qdrant服务"
    fi
}

# ============================================
# 外部服务自动安装与启动（本地原生，无Docker）
# ============================================

# 目录与版本
VENDOR_DIR="vendor"
ELASTIC_DIR="$VENDOR_DIR/elasticsearch"
QDRANT_DIR="$VENDOR_DIR/qdrant"
ELASTIC_VERSION_DEFAULT="8.11.0"
QDRANT_VERSION_DEFAULT="1.6.9"

ensure_vendor_dirs() {
    mkdir -p "$VENDOR_DIR" "$ELASTIC_DIR" "$QDRANT_DIR" 2>/dev/null || true
}

install_elasticsearch_windows() {
    ensure_vendor_dirs
    local version="${ELASTICSEARCH_VERSION:-$ELASTIC_VERSION_DEFAULT}"
    local zip_name="elasticsearch-${version}-windows-x86_64.zip"
    local url="https://artifacts.elastic.co/downloads/elasticsearch/${zip_name}"
    local dest_zip="$ELASTIC_DIR/$zip_name"
    local extract_dir="$ELASTIC_DIR/elasticsearch-${version}"

    if [[ -d "$extract_dir" ]]; then
        log_info "Elasticsearch 已安装: $extract_dir"
        echo "$extract_dir" > "$ELASTIC_DIR/current.path"
        return 0
    fi

    log_step "下载并安装Elasticsearch $version (Windows) ..."
    log_info "下载: $url"
    curl -L -o "$dest_zip" "$url" || {
        log_error "Elasticsearch 下载失败"
        return 1
    }
    log_info "解压: $dest_zip → $ELASTIC_DIR"
    powershell -NoProfile -Command "Expand-Archive -Path '$dest_zip' -DestinationPath '$ELASTIC_DIR' -Force" || {
        log_error "Elasticsearch 解压失败"
        return 1
    }
    echo "$extract_dir" > "$ELASTIC_DIR/current.path"
    log_info "Elasticsearch 安装完成: $extract_dir"
}

install_qdrant_windows() {
    ensure_vendor_dirs
    local version="${QDRANT_VERSION:-$QDRANT_VERSION_DEFAULT}"

    # 已安装则跳过
    if [[ -f "$QDRANT_DIR/qdrant.exe" ]]; then
        log_info "Qdrant 已安装"
        return 0
    fi

    log_step "下载并安装Qdrant $version (Windows) ..."
    # 兼容不同资产命名
    local candidates=(
        "qdrant_windows_x86_64.zip"
        "qdrant-x86_64-pc-windows-msvc.zip"
    )
    local downloaded=""
    for name in "${candidates[@]}"; do
        local url="https://github.com/qdrant/qdrant/releases/download/v${version}/${name}"
        local dest_zip="$QDRANT_DIR/$name"
        log_info "尝试下载: $url"
        if curl -fL -o "$dest_zip" "$url"; then
            local sz
            sz=$(wc -c <"$dest_zip" 2>/dev/null || echo 0)
            if [[ "$sz" -gt 1000000 ]]; then
                downloaded="$dest_zip"
                break
            else
                log_warn "下载文件过小(大小=$sz)，可能无效，继续尝试其他资产名"
            fi
        fi
    done

    if [[ -z "$downloaded" ]]; then
        log_error "Qdrant 下载失败（未找到有效资产）"
        return 1
    fi

    log_info "解压: $downloaded → $QDRANT_DIR"
    powershell -NoProfile -Command "Expand-Archive -Path '$downloaded' -DestinationPath '$QDRANT_DIR' -Force" || {
        log_error "Qdrant 解压失败"
        return 1
    }
    # 定位 qdrant.exe
    if [[ -f "$QDRANT_DIR/qdrant.exe" ]]; then
        :
    else
        local found
        found=$(powershell -NoProfile -Command "Get-ChildItem -Recurse -Path '$QDRANT_DIR' -Filter 'qdrant.exe' | Select -First 1 -ExpandProperty FullName" 2>/dev/null)
        if [[ -n "$found" ]]; then
            cp "$found" "$QDRANT_DIR/qdrant.exe" 2>/dev/null || true
        fi
    fi
    if [[ -f "$QDRANT_DIR/qdrant.exe" ]]; then
        log_info "Qdrant 安装完成"
    else
        log_error "未找到Qdrant可执行文件"
        return 1
    fi
}

start_elasticsearch_local() {
    # 已运行则跳过（优先以端口监听为准，避免HTTPS导致的curl误判）
    if check_port "${ELASTICSEARCH_PORT:-9200}" "Elasticsearch"; then
        log_info "✓ Elasticsearch 端口已监听，视为运行中"
        return 0
    fi

    if [[ "$OS" == "windows" ]]; then
        install_elasticsearch_windows || return 1
        local base_dir
        base_dir=$(cat "$ELASTIC_DIR/current.path" 2>/dev/null)
        if [[ -z "$base_dir" ]]; then
            log_error "未找到Elasticsearch安装路径"
            return 1
        fi
        local es_bat="$base_dir/bin/elasticsearch.bat"
        local pid_file="$PID_DIR/elasticsearch.pid"
        local heap="${ELASTICSEARCH_HEAP_SIZE:-1g}"
        local data_dir="$base_dir/data-dev"
        mkdir -p "$data_dir" 2>/dev/null || true
        # 清理僵尸锁：仅当端口未监听且存在node.lock时
        if ! netstat -an | grep -E ":${ELASTICSEARCH_PORT:-9200} .*LISTEN" >/dev/null 2>&1; then
            if [[ -f "$data_dir/node.lock" ]]; then
                log_warn "检测到旧的Elasticsearch node.lock，端口未监听，清理锁文件"
                rm -f "$data_dir/node.lock" 2>/dev/null || true
            fi
        fi

        log_info "启动Elasticsearch...（日志见 $base_dir/logs/elasticsearch.log）"
        # 通过PowerShell启动并获取PID（不做文件重定向，避免权限/编码问题）
        local ps_cmd
        # 开发模式禁用安全与HTTPS，单机引导
        ps_cmd="Start-Process -FilePath '$es_bat' -ArgumentList '-Epath.data=$data_dir','-Ehttp.port=${ELASTICSEARCH_PORT:-9200}','-Enetwork.host=127.0.0.1','-Expack.security.enabled=false','-Expack.security.http.ssl.enabled=false','-Expack.security.transport.ssl.enabled=false','-Ediscovery.type=single-node','-Ecluster.initial_master_nodes=','-Expack.ml.enabled=false','-Ecluster.routing.allocation.disk.threshold_enabled=false' -WindowStyle Hidden -PassThru | Select -Expand Id"
        local pid
        pid=$(powershell -NoProfile -Command "$ps_cmd")
        if [[ -n "$pid" ]]; then
            echo "$pid" > "$pid_file"
            log_info "Elasticsearch 启动中 (PID: $pid)，等待就绪..."
            # 等待健康
            for i in {1..30}; do
                if curl -s "http://127.0.0.1:${ELASTICSEARCH_PORT:-9200}" >/dev/null 2>&1; then
                    log_info "✓ Elasticsearch 就绪"
                    return 0
                fi
                sleep 1
            done
            log_warn "Elasticsearch 启动超时，请查看 $base_dir/logs/elasticsearch.log"
            return 1
        else
            log_error "Elasticsearch 启动失败"
            return 1
        fi
    else
        log_warn "当前仅实现Windows下的本地Elasticsearch自动安装/启动"
        return 1
    fi
}

start_qdrant_local() {
    # 已运行则跳过
    if curl -s "http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections" >/dev/null 2>&1; then
        log_info "✓ Qdrant 已在运行"
        return 0
    fi

    if [[ "$OS" == "windows" ]]; then
        install_qdrant_windows || return 1
        local exe="$QDRANT_DIR/qdrant.exe"
        if [[ ! -f "$exe" ]]; then
            log_error "未找到Qdrant可执行文件"
            return 1
        fi
        local log_file="$LOG_DIR/qdrant.log"
        local pid_file="$PID_DIR/qdrant.pid"
        local config_file="config/qdrant/config.yaml"
        local data_dir="${QDRANT_STORAGE_PATH:-./qdrant_storage}"
        
        # 确保配置目录和数据目录存在
        mkdir -p "$data_dir" 2>/dev/null || true
        mkdir -p "config/qdrant" 2>/dev/null || true
        
        # 检查配置文件是否存在
        if [[ ! -f "$config_file" ]]; then
            log_error "Qdrant配置文件不存在: $config_file"
            return 1
        fi

        log_info "启动Qdrant...（日志: $log_file）"
        log_info "使用配置文件: $config_file"
        log_info "数据存储路径: $data_dir"
        
        # 先清理端口占用的僵尸进程
        if netstat -an | grep -E ":${QDRANT_PORT:-6333} .*LISTEN" >/dev/null 2>&1; then
            log_warn "检测到Qdrant端口已被占用，可能已有实例在运行"
        fi
        
        # 使用配置文件启动Qdrant，禁用遥测
        local start_cmd="\"$exe\" --config-path \"$config_file\" --disable-telemetry"
        log_debug "启动命令: $start_cmd"
        
        # 使用PowerShell启动并获取PID
        local ps_cmd="Start-Process -FilePath '$exe' -ArgumentList '--config-path','$config_file','--disable-telemetry' -WindowStyle Hidden -PassThru | Select -Expand Id"
        local pid
        pid=$(powershell -NoProfile -Command "$ps_cmd")
        
        if [[ -n "$pid" ]]; then
            echo "$pid" > "$pid_file"
            log_info "Qdrant 启动中 (PID: $pid)，等待就绪..."
            
            # 等待服务就绪
            for i in {1..30}; do
                if curl -s "http://127.0.0.1:${QDRANT_PORT:-6333}/collections" >/dev/null 2>&1; then
                    log_info "✓ Qdrant 就绪"
                    return 0
                fi
                sleep 1
            done
            log_warn "Qdrant 启动超时，请查看日志或手动检查进程状态"
            return 1
        else
            log_error "Qdrant 启动失败"
            return 1
        fi
    else
        log_warn "当前仅实现Windows下的本地Qdrant自动安装/启动"
        return 1
    fi
}

# ============================================
# 目录和文件初始化
# ============================================
init_directories() {
    log_step "初始化目录结构..."
    
    local dirs=(
        "$PID_DIR"
        "$LOG_DIR"
        "data"
        "backups"
        "${QDRANT_STORAGE_PATH:-./qdrant_storage}"
    )
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_debug "创建目录: $dir"
        fi
    done
    
    # 创建环境文件（如果不存在）
    if [[ ! -f ".env" && -f "env.example" ]]; then
        cp env.example .env
        log_info "已创建 .env 文件，请根据需要修改配置"
    fi
}

# ============================================
# 进程管理
# ============================================
start_service() {
    local service_name=$1
    local command=$2
    local pid_file="$PID_DIR/${service_name}.pid"
    local log_file="$LOG_DIR/${service_name}.log"
    
    # 检查是否已经在运行
    if [[ -f "$pid_file" ]]; then
        local existing_pid
        existing_pid=$(cat "$pid_file")
        if kill -0 "$existing_pid" 2>/dev/null; then
            log_warn "$service_name 已经在运行 (PID: $existing_pid)"
            return 0
        else
            log_debug "清理无效的PID文件: $pid_file"
            rm -f "$pid_file"
        fi
    fi
    
    log_info "启动 $service_name..."
    
    # 启动服务并获取PID
    if [[ "$service_name" == "frontend" ]]; then
        # 前端服务需要在特定目录下启动
        (cd web-frontend && eval "$command") > "$log_file" 2>&1 &
    else
        eval "$command" > "$log_file" 2>&1 &
    fi
    
    local pid=$!
    echo $pid > "$pid_file"
    
    # 等待服务启动
    sleep "${SERVICE_START_WAIT:-3}"
    
    # 验证服务是否成功启动
    if kill -0 "$pid" 2>/dev/null; then
        log_info "✓ $service_name 启动成功 (PID: $pid)"
        return 0
    else
        log_error "$service_name 启动失败，查看日志: $log_file"
        rm -f "$pid_file"
        return 1
    fi
}

stop_service() {
    local service_name=$1
    local pid_file="$PID_DIR/${service_name}.pid"
    
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止 $service_name (PID: $pid)..."
            
            # 优雅停止
            kill -TERM "$pid" 2>/dev/null || true
            
            # 等待进程结束
            local wait_count=0
            while kill -0 "$pid" 2>/dev/null && [[ $wait_count -lt ${SERVICE_STOP_WAIT:-10} ]]; do
                sleep 1
                ((wait_count++))
            done
            
            # 如果还在运行，强制杀死
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "强制停止 $service_name..."
                kill -KILL "$pid" 2>/dev/null || true
                sleep "${SERVICE_KILL_WAIT:-2}"
            fi
            
            if ! kill -0 "$pid" 2>/dev/null; then
                log_info "✓ $service_name 已停止"
            else
                log_error "$service_name 停止失败"
            fi
        else
            log_debug "$service_name 进程不存在"
        fi
        
        rm -f "$pid_file"
    else
        log_debug "$service_name 没有PID文件"
    fi
}

# ============================================
# 健康检查
# ============================================
health_check() {
    local service_name=$1
    local url=$2
    local retries=${HEALTH_CHECK_RETRIES:-3}
    local delay=${HEALTH_CHECK_DELAY:-2}
    
    log_debug "健康检查: $service_name"
    
    for ((i=1; i<=retries; i++)); do
        if curl -s --max-time 5 "$url" >/dev/null 2>&1; then
            log_info "✓ $service_name 健康检查通过"
            return 0
        else
            if [[ $i -lt $retries ]]; then
                log_debug "$service_name 健康检查失败，重试 ($i/$retries)..."
                sleep $delay
            fi
        fi
    done
    
    log_warn "$service_name 健康检查失败"
    return 1
}

# ============================================
# 主要启动流程
# ============================================
start_all_services() {
    log_step "启动所有开发服务..."
    
    # 选择Python可执行文件（Windows优先避免WindowsApps桥接器）
    PY_CMD="${PYTHON_EXECUTABLE:-}"
    if [[ -z "$PY_CMD" ]]; then
        if [[ "$OS" == "windows" ]]; then
            # 优先使用 py 启动器
            if command -v py &> /dev/null; then
                PY_CMD="py -3"
            elif command -v python &> /dev/null; then
                PY_CMD="python"
            else
                PY_CMD="python3"
            fi
        else
            if command -v python3 &> /dev/null; then
                PY_CMD="python3"
            else
                PY_CMD="python"
            fi
        fi
    fi

    # API专用虚拟环境路径
    API_VENV_PY_ABS="api-gateway/.venv/bin/python"
    API_VENV_WIN_PY_ABS="api-gateway/.venv/Scripts/python.exe"
    API_PY_LOCAL=""  # 进入 api-gateway 目录后可用的本地路径
    if [[ -f "$API_VENV_WIN_PY_ABS" ]]; then
        API_PY_LOCAL=".venv/Scripts/python.exe"
    elif [[ -f "$API_VENV_PY_ABS" ]]; then
        API_PY_LOCAL=".venv/bin/python"
    fi

    # 若存在API虚拟环境，优先使用本地路径调用
    if [[ -n "$API_PY_LOCAL" ]]; then
        UVICORN_CMD="cd api-gateway && \"$API_PY_LOCAL\" -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
    else
        UVICORN_CMD="cd api-gateway && $PY_CMD -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
    fi

    # 启动API服务
    start_service "api" "$UVICORN_CMD"
    
    # 启动前端服务
    if [[ -d "web-frontend" ]]; then
        start_service "frontend" "npm run dev -- --port ${FRONTEND_PORT:-3000}"
    fi
    
    # 启动Celery工作进程
    start_service "celery-worker" "celery -A data-processor.tasks worker --loglevel=${CELERY_LOGLEVEL:-info} --concurrency=${CELERY_WORKERS:-4}"
    
    # 启动Celery监控
    start_service "celery-flower" "celery -A data-processor.tasks flower --port=${CELERY_FLOWER_PORT:-5555}"
    
    # 等待服务完全启动
    log_info "等待服务完全启动..."
    sleep 5
    
    # 健康检查
    health_check "API服务" "http://localhost:${API_PORT:-8000}/health"
    if [[ -d "web-frontend" ]]; then
        health_check "前端服务" "http://localhost:${FRONTEND_PORT:-3000}"
    fi
    health_check "Celery监控" "http://localhost:${CELERY_FLOWER_PORT:-5555}"
}

stop_all_services() {
    log_step "停止所有开发服务..."
    
    local services=("celery-flower" "celery-worker" "frontend" "api")
    
    for service in "${services[@]}"; do
        stop_service "$service"
    done
}

# ============================================
# 清理功能
# ============================================
cleanup() {
    log_step "执行清理操作..."
    
    # 停止所有服务
    stop_all_services
    
    # 清理PID文件
    if [[ -d "$PID_DIR" ]]; then
        rm -f "$PID_DIR"/*.pid
        log_debug "清理PID文件"
    fi
    
    # 清理临时文件（如果启用）
    if [[ "${AUTO_CLEAN_TEMP:-true}" == "true" ]]; then
        find . -name "*.pyc" -delete 2>/dev/null || true
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
        log_debug "清理临时文件"
    fi
    
    # 清理旧日志（如果启用）
    if [[ "${AUTO_CLEAN_LOGS:-false}" == "true" && -n "${LOG_RETENTION_DAYS:-}" ]]; then
        find "$LOG_DIR" -name "*.log" -mtime +${LOG_RETENTION_DAYS} -delete 2>/dev/null || true
        log_debug "清理旧日志文件"
    fi
    
    log_info "清理完成"
}

# ============================================
# 信号处理
# ============================================
trap_exit() {
    log_warn "收到退出信号，正在清理..."
    cleanup
    log_info "开发环境已安全关闭"
    exit 0
}

# 设置信号陷阱
trap trap_exit SIGINT SIGTERM

# ============================================
# 帮助信息
# ============================================
show_help() {
    cat << EOF
Qsou 投资情报搜索引擎 - 开发环境启动脚本

用法: $0 [选项]

选项:
    start           启动所有开发服务
    stop            停止所有开发服务
    restart         重启所有开发服务
    status          显示服务状态
    logs [service]  查看服务日志
    clean           清理临时文件和日志
    health          执行健康检查
    help            显示此帮助信息

环境变量:
    DEBUG=true      启用调试模式
    AUTO_KILL_PORTS=true    自动杀死占用端口的进程

示例:
    $0 start        # 启动开发环境
    $0 stop         # 停止开发环境
    $0 logs api     # 查看API服务日志
    DEBUG=true $0 start  # 以调试模式启动

配置文件: dev.local
日志目录: $LOG_DIR
PID目录: $PID_DIR
EOF
}

show_status() {
    log_step "服务状态检查..."
    
    local services=("api" "frontend" "celery-worker" "celery-flower")
    
    for service in "${services[@]}"; do
        local pid_file="$PID_DIR/${service}.pid"
        if [[ -f "$pid_file" ]]; then
            local pid
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log_info "✓ $service 运行中 (PID: $pid)"
            else
                log_warn "✗ $service 已停止 (PID文件存在但进程不存在)"
            fi
        else
            log_warn "✗ $service 未运行"
        fi
    done
    
    # 检查端口使用情况
    echo
    log_step "端口使用情况:"
    local ports=(
        "${API_PORT:-8000}:API服务"
        "${FRONTEND_PORT:-3000}:前端服务"
        "${CELERY_FLOWER_PORT:-5555}:Celery监控"
    )
    
    for port_info in "${ports[@]}"; do
        IFS=':' read -r port service_name <<< "$port_info"
        if check_port "$port" "$service_name"; then
            log_info "✓ 端口 $port 正在使用 ($service_name)"
        else
            log_warn "✗ 端口 $port 空闲 ($service_name)"
        fi
    done
}

show_logs() {
    local service_name=${1:-}
    
    if [[ -z "$service_name" ]]; then
        log_info "可用的服务日志:"
        for log_file in "$LOG_DIR"/*.log; do
            if [[ -f "$log_file" ]]; then
                local service
                service=$(basename "$log_file" .log)
                echo "  - $service"
            fi
        done
        echo
        echo "用法: $0 logs <service_name>"
        return
    fi
    
    local log_file="$LOG_DIR/${service_name}.log"
    if [[ -f "$log_file" ]]; then
        log_info "显示 $service_name 的日志 (按 Ctrl+C 退出):"
        tail -f "$log_file"
    else
        log_error "日志文件不存在: $log_file"
        exit 1
    fi
}

# ============================================
# 主函数
# ============================================
main() {
    local command=${1:-start}
    
    echo "🚀 Qsou 投资情报搜索引擎 - 开发环境管理"
    echo "命令: $command"
    echo ""
    
    # 加载配置
    load_config
    
    case "$command" in
        start)
            echo "============================================================"
            log_info "🚀 启动 ${PROJECT_NAME:-Qsou Investment Intelligence Engine} 开发环境"
            echo "============================================================"
            echo ""
            
            check_system
            init_directories
            
            # 询问是否跳过依赖检查（加速启动）
            if [[ "${SKIP_DEPS:-false}" != "true" ]]; then
                check_python_deps
                check_node_deps
            else
                log_info "跳过依赖检查 (SKIP_DEPS=true)"
            fi
            
            clean_ports
            # 在启动任何服务之前，确保数据服务先安装并启动
            if [[ "${AUTO_START_DATA_SERVICES:-true}" == "true" ]]; then
                start_elasticsearch_local || log_warn "Elasticsearch 自动启动未成功"
                start_qdrant_local || log_warn "Qdrant 自动启动未成功"
            else
                log_info "已禁用数据服务自动启动 (AUTO_START_DATA_SERVICES=false)"
            fi

            # 再检查一次服务状态
            check_services
            start_all_services
            
            log_info ""
            log_info "🎉 开发环境启动完成！"
            log_info ""
            log_info "服务地址:"
            log_info "  - API服务: http://localhost:${API_PORT:-8000}"
            log_info "  - API文档: http://localhost:${API_PORT:-8000}/docs"
            if [[ -d "web-frontend" ]]; then
                log_info "  - 前端服务: http://localhost:${FRONTEND_PORT:-3000}"
            fi
            log_info "  - Celery监控: http://localhost:${CELERY_FLOWER_PORT:-5555}"
            log_info ""
            log_info "使用 '$0 stop' 停止所有服务"
            log_info "使用 '$0 status' 查看服务状态"
            log_info "使用 '$0 logs <service>' 查看服务日志"
            log_info ""
            log_info "按 Ctrl+C 退出并清理所有服务"
            
            # 保持脚本运行，等待用户中断
            while true; do
                sleep 10
                # 可以在这里添加定期健康检查
            done
            ;;
        stop)
            log_info "🛑 停止开发环境"
            cleanup
            ;;
        restart)
            log_info "🔄 重启开发环境"
            cleanup
            sleep 2
            main start
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        clean)
            log_info "🧹 清理临时文件"
            cleanup
            ;;
        health)
            log_info "🏥 健康检查"
            check_services
            ;;
        verify|test)
            log_info "运行环境验证..."
            python scripts/verify_env.py
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# ============================================
# 脚本入口
# ============================================
# 检查脚本是否在项目根目录运行
if [[ ! -f "PROJECT_MEMORY.md" ]]; then
    log_error "请在项目根目录运行此脚本"
    exit 1
fi

# 执行主函数
main "$@"
