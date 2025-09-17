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
                    if eval "$API_PY -c 'import fastapi, uvicorn, sqlalchemy, redis, elasticsearch, qdrant_client, flower'" >/dev/null 2>&1; then
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
    
    # 复用同一虚拟环境为 data-processor 安装依赖，确保 Celery 与 API 在同一环境
    if [[ -f "data-processor/requirements.txt" ]]; then
        if [[ -n "$API_PY" ]]; then
            if eval "$API_PY -c 'import elasticsearch, qdrant_client, redis, celery, flower'" >/dev/null 2>&1; then
                log_info "data-processor 核心依赖已满足（复用 API 虚拟环境）"
            else
                log_info "为 data-processor 安装依赖到 API 虚拟环境..."
                eval "$API_PY -m pip install -r data-processor/requirements.txt" || {
                    log_warn "安装 data-processor 依赖失败，后续可能影响 Celery/向量/ES 功能"
                }
            fi
        else
            log_warn "未找到 API 虚拟环境 Python，跳过 data-processor 依赖安装"
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
        # 计算依赖哈希（package.json + package-lock.json），用于判断是否需要安装
        local deps_hash
        deps_hash=$(node -e "const fs=require('fs');const crypto=require('crypto');const files=['package-lock.json','package.json'];let s='';for(const f of files){if(fs.existsSync(f)){s+=crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex')}};process.stdout.write(s)")
        local hash_file=".deps_hash"

        if [[ -d "node_modules" && -f "$hash_file" ]]; then
            local last_hash
            last_hash=$(cat "$hash_file" 2>/dev/null || echo "")
            if [[ -n "$deps_hash" && "$deps_hash" == "$last_hash" ]]; then
                log_info "前端依赖未变化，跳过安装"
                cd ..
                return
            fi
        fi

        if [[ ! -d "node_modules" ]]; then
            log_info "首次安装前端依赖 (npm ci)..."
            npm ci || {
                log_warn "npm ci 失败，尝试使用 npm install 作为回退...";
                npm install || log_warn "npm install 也失败，请关闭占用 node_modules 的进程/杀软或以管理员权限重试";
            }
        else
            log_info "依赖定义有变化，增量安装更新 (npm install)..."
            npm install || log_warn "npm install 失败，请关闭占用 node_modules 的进程/杀软或以管理员权限重试"
        fi

        # 安装成功后记录当前哈希
        if [[ -n "$deps_hash" ]]; then
            echo "$deps_hash" > "$hash_file" 2>/dev/null || true
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
        # Windows: 使用 PowerShell 更可靠（避免本地化/解析问题）
        local ps_cmd="Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1"
        if powershell -NoProfile -Command "$ps_cmd" | grep -qi "LocalPort" >/dev/null 2>&1; then
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
        # Windows: 使用 PowerShell 获取占用PID并强制结束进程树
        local pids
        pids=$(powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -Expand OwningProcess) | Sort-Object -Unique" 2>/dev/null | tr -d '\r')
        if [[ -n "$pids" ]]; then
            for pid in $pids; do
                taskkill /T /F /PID $pid 2>/dev/null || true
            done
        fi
        # 回退方案：再尝试通过 netstat 抓取PID
        if check_port $port "$service_name"; then
            local npids
            npids=$(netstat -ano | tr -s ' ' | grep ":$port " | awk '{print $5}' | sort -u 2>/dev/null)
            if [[ -n "$npids" ]]; then
                for pid in $npids; do
                    taskkill /T /F /PID $pid 2>/dev/null || true
                done
            fi
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

find_free_port() {
    local start_port=$1
    local range=${2:-100}
    local end_port=$((start_port + range))
    local p
    for ((p=start_port; p<end_port; p++)); do
        if ! check_port "$p" "probe"; then
            echo "$p"
            return 0
        fi
    done
    return 1
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
                    kill_port "$port" "$service_name" || true
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
REDIS_DIR="$VENDOR_DIR/redis"
ELASTIC_DIR="$VENDOR_DIR/elasticsearch"
QDRANT_DIR="$VENDOR_DIR/qdrant"
REDIS_VERSION_DEFAULT="5.0.14.1"
ELASTIC_VERSION_DEFAULT="8.11.0"
QDRANT_VERSION_DEFAULT="1.6.9"

ensure_vendor_dirs() {
    mkdir -p "$VENDOR_DIR" "$REDIS_DIR" "$ELASTIC_DIR" "$QDRANT_DIR" 2>/dev/null || true
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
        # 清理僵尸锁和PID文件：仅当端口未监听且存在lock时
        if ! netstat -an | grep -E ":${ELASTICSEARCH_PORT:-9200} .*LISTEN" >/dev/null 2>&1; then
            if [[ -f "$data_dir/node.lock" ]]; then
                log_warn "检测到旧的Elasticsearch node.lock，端口未监听，清理锁文件"
                rm -f "$data_dir/node.lock" 2>/dev/null || true
            fi
            # 同时清理可能的僵尸PID文件
            if [[ -f "$pid_file" ]]; then
                local old_pid
                old_pid=$(cat "$pid_file" 2>/dev/null)
                if [[ -n "$old_pid" ]] && ! tasklist //FI "PID eq $old_pid" 2>/dev/null | grep -q "elasticsearch"; then
                    log_warn "清理无效的Elasticsearch PID文件"
                    rm -f "$pid_file" 2>/dev/null || true
                fi
            fi
        fi

        local log_file="$LOG_DIR/elasticsearch.log"
        log_info "启动Elasticsearch...（日志见 $log_file）"
        # 通过PowerShell启动并获取PID，同时重定向日志到项目logs目录
        local ps_cmd
        # 开发模式禁用安全与HTTPS，单机引导，指定日志文件路径
        ps_cmd="Start-Process -FilePath '$es_bat' -ArgumentList '-Epath.data=$data_dir','-Ehttp.port=${ELASTICSEARCH_PORT:-9200}','-Enetwork.host=127.0.0.1','-Expack.security.enabled=false','-Expack.security.http.ssl.enabled=false','-Expack.security.transport.ssl.enabled=false','-Ediscovery.type=single-node','-Expack.ml.enabled=false','-Ecluster.routing.allocation.disk.threshold_enabled=false','-Epath.logs=$LOG_DIR' -RedirectStandardOutput '$log_file' -RedirectStandardError '$log_file' -WindowStyle Hidden -PassThru | Select -Expand Id"
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
            log_warn "Elasticsearch 启动超时，请查看 $log_file"
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
        
        # 使用PowerShell启动并获取PID，同时重定向日志到项目logs目录
        local ps_cmd="Start-Process -FilePath '$exe' -ArgumentList '--config-path','$config_file','--disable-telemetry' -RedirectStandardOutput '$log_file' -RedirectStandardError '$log_file' -WindowStyle Hidden -PassThru | Select -Expand Id"
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
            log_warn "Qdrant 启动超时，请查看日志: $log_file"
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
# Redis服务管理
# ============================================
install_redis_windows() {
    ensure_vendor_dirs
    local redis_version="${REDIS_VERSION:-$REDIS_VERSION_DEFAULT}"
    local redis_url="https://github.com/tporadowski/redis/releases/download/v${redis_version}/Redis-x64-${redis_version}.zip"
    local redis_zip="$REDIS_DIR/redis-${redis_version}.zip"
    
    # 如果已安装则跳过
    if [[ -f "$REDIS_DIR/redis-server.exe" ]]; then
        log_debug "Redis 已安装在 $REDIS_DIR"
        return 0
    fi
    
    log_info "下载 Redis for Windows v${redis_version}..."
    mkdir -p "$REDIS_DIR"
    
    # 下载Redis（显示进度）
    log_info "下载地址: $redis_url"
    if ! curl -L -o "$redis_zip" --progress-bar "$redis_url"; then
        log_error "下载 Redis 失败，请检查网络连接"
        rm -f "$redis_zip"
        return 1
    fi
    
    # 检查文件大小
    local file_size=$(stat -c%s "$redis_zip" 2>/dev/null || stat -f%z "$redis_zip" 2>/dev/null || echo "0")
    if [[ "$file_size" -lt 1000000 ]]; then
        log_error "下载的文件太小（${file_size}字节），可能下载失败"
        rm -f "$redis_zip"
        return 1
    fi
    log_debug "下载完成，文件大小: ${file_size} 字节"
    
    log_info "解压 Redis..."
    
    # 尝试多种解压方式
    local extract_success=false
    
    # 方法1：使用unzip（如果可用）
    if command -v unzip &> /dev/null; then
        log_debug "尝试使用 unzip 解压..."
        if unzip -q -o "$redis_zip" -d "$REDIS_DIR" 2>/dev/null; then
            extract_success=true
            log_debug "unzip 解压成功"
        fi
    fi
    
    # 方法2：使用PowerShell（Windows环境）
    if [[ "$extract_success" == "false" ]]; then
        log_debug "尝试使用 PowerShell 解压..."
        # 将路径转换为Windows格式
        local win_zip=$(cygpath -w "$redis_zip" 2>/dev/null || echo "$redis_zip")
        local win_dir=$(cygpath -w "$REDIS_DIR" 2>/dev/null || echo "$REDIS_DIR")
        
        if powershell -NoProfile -Command "
            try {
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                [System.IO.Compression.ZipFile]::ExtractToDirectory('$win_zip', '$win_dir')
                exit 0
            } catch {
                Write-Host \"PowerShell解压失败: \$_\"
                exit 1
            }
        "; then
            extract_success=true
            log_debug "PowerShell 解压成功"
        fi
    fi
    
    # 方法3：使用7z（如果可用）
    if [[ "$extract_success" == "false" ]] && command -v 7z &> /dev/null; then
        log_debug "尝试使用 7z 解压..."
        if 7z x "$redis_zip" -o"$REDIS_DIR" -y > /dev/null 2>&1; then
            extract_success=true
            log_debug "7z 解压成功"
        fi
    fi
    
    if [[ "$extract_success" == "false" ]]; then
        log_error "解压失败，请手动安装Redis或安装unzip工具"
        rm -f "$redis_zip"
        return 1
    fi
    
    # 清理zip文件
    rm -f "$redis_zip"
    
    # 检查安装是否成功
    if [[ -f "$REDIS_DIR/redis-server.exe" ]]; then
        log_info "✓ Redis 安装成功"
        # 设置执行权限（Git Bash环境）
        chmod +x "$REDIS_DIR"/*.exe 2>/dev/null || true
        return 0
    else
        log_error "Redis 安装失败，未找到redis-server.exe"
        log_debug "目录内容："
        ls -la "$REDIS_DIR" 2>/dev/null || true
        return 1
    fi
}

start_redis_local() {
    # 检查redis-cli是否可用，如果可用则测试连接
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping >/dev/null 2>&1; then
            log_info "✓ Redis 已在运行"
            return 0
        fi
    fi
    
    # 检查端口是否被占用
    if check_port "${REDIS_PORT:-6379}" "Redis"; then
        log_info "✓ Redis 端口已监听，视为运行中"
        return 0
    fi
    
    if [[ "$OS" == "windows" ]]; then
        # Windows环境
        install_redis_windows || return 1
        
        local redis_exe="$REDIS_DIR/redis-server.exe"
        local redis_conf="$REDIS_DIR/redis.conf"
        local pid_file="$PID_DIR/redis.pid"
        local data_dir="$REDIS_DIR/data"
        local log_file="$LOG_DIR/redis.log"  # 改为logs目录，让统一日志收集器能收集
        
        if [[ ! -f "$redis_exe" ]]; then
            log_error "未找到Redis可执行文件"
            return 1
        fi
        
        # 创建必要的目录
        mkdir -p "$data_dir"
        mkdir -p "$LOG_DIR"
        
        # 将路径转换为Windows格式（避免路径问题）
        local win_data_dir=$(cygpath -w "$data_dir" 2>/dev/null || echo "$data_dir")
        
        # 创建简单的配置文件
        cat > "$redis_conf" << EOF
# Redis开发环境配置
bind 127.0.0.1
port ${REDIS_PORT:-6379}
dir ./data
dbfilename dump.rdb
appendonly no
save ""
maxmemory 256mb
maxmemory-policy allkeys-lru
logfile ""
EOF
        
        log_info "启动 Redis..."
        
        # 确保目录存在
        mkdir -p "$LOG_DIR"
        mkdir -p "$PID_DIR"
        
        # 在子shell中切换目录并启动Redis
        (
            cd "$REDIS_DIR" 2>/dev/null || {
                log_error "无法进入Redis目录: $REDIS_DIR"
                return 1
            }
            
            # 在Redis目录下启动，使用相对路径
            ./redis-server.exe redis.conf > "../../logs/redis.log" 2>&1 &
            echo $!
        ) > "$PID_DIR/redis.pid"
        
        local pid=$(cat "$PID_DIR/redis.pid" 2>/dev/null)
        
        if [[ -n "$pid" ]] && [[ "$pid" -gt 0 ]]; then
            log_info "Redis 启动中 (PID: $pid)，等待就绪..."
            
            # 等待Redis就绪（使用安装目录中的redis-cli）
            local redis_cli="$REDIS_DIR/redis-cli.exe"
            for i in {1..10}; do
                if [[ -f "$redis_cli" ]]; then
                    if "$redis_cli" -h 127.0.0.1 -p "${REDIS_PORT:-6379}" ping >/dev/null 2>&1; then
                        log_info "✓ Redis 就绪"
                        return 0
                    fi
                elif check_port "${REDIS_PORT:-6379}" "Redis"; then
                    log_info "✓ Redis 端口已监听，视为就绪"
                    return 0
                fi
                sleep 1
            done
            
            log_warn "Redis 启动超时"
            return 1
        else
            log_error "Redis 启动失败"
            return 1
        fi
        
    elif [[ "$OS" == "linux" ]] || [[ "$OS" == "darwin" ]]; then
        # Linux/Mac环境
        if ! command -v redis-server &> /dev/null; then
            log_error "Redis未安装，请先安装Redis："
            if [[ "$OS" == "linux" ]]; then
                log_info "  Ubuntu/Debian: sudo apt-get install redis-server"
                log_info "  CentOS/RHEL: sudo yum install redis"
            else
                log_info "  macOS: brew install redis"
            fi
            return 1
        fi
        
        local pid_file="$PID_DIR/redis.pid"
        local data_dir="$HOME/.local/redis/data"
        mkdir -p "$data_dir"
        
        log_info "启动 Redis..."
        redis-server --bind 127.0.0.1 --port "${REDIS_PORT:-6379}" --dir "$data_dir" --daemonize yes --pidfile "$pid_file"
        
        # 等待Redis就绪
        for i in {1..10}; do
            if redis-cli -h 127.0.0.1 -p "${REDIS_PORT:-6379}" ping >/dev/null 2>&1; then
                log_info "✓ Redis 就绪"
                return 0
            fi
            sleep 1
        done
        
        log_warn "Redis 启动超时"
        return 1
    else
        log_warn "不支持的操作系统: $OS"
        return 1
    fi
}

stop_redis_local() {
    local pid_file="$PID_DIR/redis.pid"
    
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        
        if [[ "$OS" == "windows" ]]; then
            # 尝试优雅关闭
            local redis_cli="$REDIS_DIR/redis-cli.exe"
            if [[ -f "$redis_cli" ]]; then
                "$redis_cli" -h 127.0.0.1 -p "${REDIS_PORT:-6379}" shutdown 2>/dev/null || true
                sleep 1
            fi
            # 强制终止
            taskkill /F /PID "$pid" 2>/dev/null || true
        else
            # 先尝试优雅关闭
            if command -v redis-cli &> /dev/null; then
                redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" shutdown 2>/dev/null || true
                sleep 1
            fi
            # 发送终止信号
            kill -TERM "$pid" 2>/dev/null || true
        fi
        
        rm -f "$pid_file"
        log_info "✓ Redis已停止"
    else
        # 尝试通过redis-cli关闭
        if [[ "$OS" == "windows" ]]; then
            local redis_cli="$REDIS_DIR/redis-cli.exe"
            if [[ -f "$redis_cli" ]]; then
                "$redis_cli" -h 127.0.0.1 -p "${REDIS_PORT:-6379}" shutdown 2>/dev/null || true
            fi
        elif command -v redis-cli &> /dev/null; then
            redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" shutdown 2>/dev/null || true
        fi
    fi
}

# ============================================
# 统一日志收集机制
# ============================================
UNIFIED_LOG_FILE="${LOG_DIR}/unified.log"
UNIFIED_LOG_MAX_LINES="${UNIFIED_LOG_MAX_LINES:-50000}"
LOG_COLLECTOR_PID_FILE="${PID_DIR}/log-collector.pid"

# 日志收集器主进程
start_log_collector() {
    local pid_file="$LOG_COLLECTOR_PID_FILE"
    
    # 检查是否已经在运行
    if [[ -f "$pid_file" ]]; then
        local existing_pid
        existing_pid=$(cat "$pid_file")
        if kill -0 "$existing_pid" 2>/dev/null; then
            log_info "日志收集器已在运行 (PID: $existing_pid)"
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    
    log_info "启动统一日志收集器 (Python版本)..."
    
    # 使用Python日志收集器（更高效、跨平台）
    local python_cmd=""
    if [[ -f "api-gateway/.venv/Scripts/python.exe" ]]; then
        python_cmd="api-gateway/.venv/Scripts/python.exe"
    elif [[ -f "api-gateway/.venv/bin/python" ]]; then
        python_cmd="api-gateway/.venv/bin/python"
    else
        python_cmd="${PYTHON_CMD:-python}"
    fi
    
    # 检查Python脚本是否存在
    if [[ ! -f "scripts/unified_logger.py" ]]; then
        log_warn "Python日志收集器脚本不存在，跳过日志收集"
        return 1
    fi
    
    # 启动Python日志收集器
    $python_cmd scripts/unified_logger.py \
        --output "$UNIFIED_LOG_FILE" \
        --max-lines "${UNIFIED_LOG_MAX_LINES:-50000}" \
        --interval "${LOG_COLLECTOR_CHECK_INTERVAL:-2}" \
        > "$LOG_DIR/collector.log" 2>&1 &
    
    local collector_pid=$!
    echo "$collector_pid" > "$pid_file"
    
    # 等待一下确认启动成功
    sleep 2
    
    if kill -0 "$collector_pid" 2>/dev/null; then
        log_info "✓ 日志收集器已启动 (PID: $collector_pid)"
        log_info "  - 统一日志文件: $UNIFIED_LOG_FILE"
        log_info "  - 最大行数限制: $UNIFIED_LOG_MAX_LINES"
        log_info "  - 使用Python实现，内存占用更低"
        return 0
    else
        log_error "日志收集器启动失败"
        rm -f "$pid_file"
        return 1
    fi
}

stop_log_collector() {
    local pid_file="$LOG_COLLECTOR_PID_FILE"
    
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止日志收集器 (PID: $pid)..."
            
            # 发送SIGTERM信号，让Python程序优雅退出
            kill -TERM "$pid" 2>/dev/null || true
            
            # 等待进程退出
            local wait_count=0
            while kill -0 "$pid" 2>/dev/null && [[ $wait_count -lt 5 ]]; do
                sleep 1
                ((wait_count++))
            done
            
            # 如果还在运行，强制终止
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "日志收集器未响应，强制终止..."
                if [[ "$OS" == "windows" ]]; then
                    # Windows: 强制杀死进程树
                    taskkill /T /F /PID "$pid" 2>/dev/null || true
                else
                    # Unix: 强制杀死
                    kill -KILL "$pid" 2>/dev/null || true
                fi
            fi
            
            log_info "✓ 日志收集器已停止"
        else
            log_debug "日志收集器进程不存在"
        fi
        
        rm -f "$pid_file"
    else
        log_debug "日志收集器PID文件不存在"
    fi
    
    # 额外检查：清理可能残留的Python日志收集进程
    if [[ "$OS" == "windows" ]]; then
        # Windows: 查找并终止unified_logger.py进程
        tasklist 2>/dev/null | grep -i "unified_logger" | awk '{print $2}' | while read -r pid; do
            if [[ -n "$pid" ]]; then
                log_debug "清理残留日志收集进程: $pid"
                taskkill /F /PID "$pid" 2>/dev/null || true
            fi
        done
    else
        # Unix: 查找并终止unified_logger.py进程（使用ps代替pgrep）
        ps aux | grep -v grep | grep "unified_logger.py" | awk '{print $2}' | while read -r pid; do
            if [[ -n "$pid" ]]; then
                log_debug "清理残留日志收集进程: $pid"
                kill -TERM "$pid" 2>/dev/null || true
            fi
        done
    fi
}

# 清理统一日志文件
clean_unified_log() {
    if [[ -f "$UNIFIED_LOG_FILE" ]]; then
        log_info "清理统一日志文件: $UNIFIED_LOG_FILE"
        > "$UNIFIED_LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SYSTEM] ========== 开发环境启动 - 日志已清理 ==========" >> "$UNIFIED_LOG_FILE"
    fi
}

# 实时查看统一日志
show_unified_log() {
    if [[ -f "$UNIFIED_LOG_FILE" ]]; then
        log_info "显示统一日志 (按 Ctrl+C 退出):"
        echo ""
        tail -f "$UNIFIED_LOG_FILE"
    else
        log_error "统一日志文件不存在: $UNIFIED_LOG_FILE"
        return 1
    fi
}

# 获取日志统计信息
log_statistics() {
    if [[ -f "$UNIFIED_LOG_FILE" ]]; then
        local total_lines
        total_lines=$(wc -l < "$UNIFIED_LOG_FILE" 2>/dev/null || echo 0)
        local file_size
        file_size=$(du -h "$UNIFIED_LOG_FILE" 2>/dev/null | cut -f1)
        
        log_info "日志统计信息:"
        log_info "  - 总行数: $total_lines / $UNIFIED_LOG_MAX_LINES"
        log_info "  - 文件大小: $file_size"
        
        # 统计各服务日志行数
        log_info "  - 各服务日志分布:"
        for service in api frontend celery-worker celery-flower elasticsearch qdrant ES-NATIVE LOG-COLLECTOR SYSTEM; do
            local count
            count=$(grep -c "\[$service\]" "$UNIFIED_LOG_FILE" 2>/dev/null || echo 0)
            if [[ $count -gt 0 ]]; then
                log_info "    * $service: $count 行"
            fi
        done
        
        # 统计错误和警告
        local error_count
        error_count=$(grep -iE "(error|exception|failed|fatal)" "$UNIFIED_LOG_FILE" 2>/dev/null | wc -l || echo 0)
        local warn_count
        warn_count=$(grep -iE "(warn|warning)" "$UNIFIED_LOG_FILE" 2>/dev/null | wc -l || echo 0)
        
        log_info "  - 错误数量: $error_count"
        log_info "  - 警告数量: $warn_count"
        
        # 显示最近的错误
        if [[ $error_count -gt 0 ]]; then
            log_info ""
            log_info "最近的错误（最多显示5条）:"
            grep -iE "(error|exception|failed|fatal)" "$UNIFIED_LOG_FILE" | tail -n 5 | while IFS= read -r line; do
                echo "    $line"
            done
        fi
    else
        log_warn "统一日志文件不存在"
    fi
}

# 搜索统一日志
search_unified_log() {
    local pattern=${1:-}
    local service=${2:-}
    
    if [[ ! -f "$UNIFIED_LOG_FILE" ]]; then
        log_error "统一日志文件不存在"
        return 1
    fi
    
    if [[ -z "$pattern" ]]; then
        log_error "请提供搜索模式"
        log_info "用法: $0 log-search <pattern> [service]"
        log_info "示例: $0 log-search error api"
        return 1
    fi
    
    log_info "搜索日志..."
    log_info "  - 模式: $pattern"
    if [[ -n "$service" ]]; then
        log_info "  - 服务: $service"
    fi
    echo ""
    
    # 使用Python搜索（更高效）
    local python_cmd=""
    if [[ -f "api-gateway/.venv/Scripts/python.exe" ]]; then
        python_cmd="api-gateway/.venv/Scripts/python.exe"
    elif [[ -f "api-gateway/.venv/bin/python" ]]; then
        python_cmd="api-gateway/.venv/bin/python"
    else
        python_cmd="${PYTHON_CMD:-python}"
    fi
    
    if [[ -f "scripts/unified_logger.py" ]]; then
        $python_cmd scripts/unified_logger.py \
            --output "$UNIFIED_LOG_FILE" \
            --search "$pattern" \
            ${service:+--service "$service"} || log_warn "未找到匹配的日志"
    else
        # 回退到grep
        if [[ -n "$service" ]]; then
            grep "\[$service\]" "$UNIFIED_LOG_FILE" | grep -iE "$pattern" || log_warn "未找到匹配的日志"
        else
            grep -iE "$pattern" "$UNIFIED_LOG_FILE" || log_warn "未找到匹配的日志"
        fi
    fi
}

# 显示特定级别的日志
show_log_level() {
    local level=${1:-ERROR}
    
    if [[ ! -f "$UNIFIED_LOG_FILE" ]]; then
        log_error "统一日志文件不存在"
        return 1
    fi
    
    log_info "显示 $level 级别的日志..."
    echo ""
    
    # 使用Python搜索（更高效）
    local python_cmd=""
    if [[ -f "api-gateway/.venv/Scripts/python.exe" ]]; then
        python_cmd="api-gateway/.venv/Scripts/python.exe"
    elif [[ -f "api-gateway/.venv/bin/python" ]]; then
        python_cmd="api-gateway/.venv/bin/python"
    else
        python_cmd="${PYTHON_CMD:-python}"
    fi
    
    if [[ -f "scripts/unified_logger.py" ]]; then
        $python_cmd scripts/unified_logger.py \
            --output "$UNIFIED_LOG_FILE" \
            --search "" \
            --level "$level" || log_info "未找到 $level 级别的日志"
    else
        # 回退到grep
        case "$level" in
            ERROR|error)
                grep -iE "(error|exception|failed|fatal)" "$UNIFIED_LOG_FILE" || log_info "未找到错误日志"
                ;;
            WARN|warn|WARNING|warning)
                grep -iE "(warn|warning)" "$UNIFIED_LOG_FILE" || log_info "未找到警告日志"
                ;;
            INFO|info)
                grep -iE "(info|information)" "$UNIFIED_LOG_FILE" || log_info "未找到信息日志"
                ;;
            DEBUG|debug)
                grep -iE "(debug|trace)" "$UNIFIED_LOG_FILE" || log_info "未找到调试日志"
                ;;
            *)
                log_error "未知的日志级别: $level"
                log_info "支持的级别: ERROR, WARN, INFO, DEBUG"
                ;;
        esac
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
    
    # 初始化统一日志文件
    if [[ "${ENABLE_UNIFIED_LOG:-true}" == "true" ]]; then
        clean_unified_log
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
    log_debug "$service_name 健康检查URL: $url"
    
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
    
    # 启动统一日志收集器（如果启用）
    if [[ "${ENABLE_UNIFIED_LOG:-true}" == "true" ]]; then
        start_log_collector
    fi
    
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
        if [[ "$OS" == "windows" ]]; then
            # Git Bash中使用export而不是set，移除chcp命令避免错误
            UVICORN_CMD="cd api-gateway && export PYTHONIOENCODING=utf-8 && \"$API_PY_LOCAL\" -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
        else
            UVICORN_CMD="cd api-gateway && PYTHONIOENCODING=utf-8 \"$API_PY_LOCAL\" -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
        fi
    else
        if [[ "$OS" == "windows" ]]; then
            # Git Bash中使用export而不是set，移除chcp命令避免错误
            UVICORN_CMD="cd api-gateway && export PYTHONIOENCODING=utf-8 && $PY_CMD -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
        else
            UVICORN_CMD="cd api-gateway && PYTHONIOENCODING=utf-8 $PY_CMD -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload"
        fi
    fi

    # 启动API服务
    start_service "api" "$UVICORN_CMD"
    
    # 启动前端服务（注入 API 地址）
    if [[ -d "web-frontend" ]]; then
        local api_base="http://localhost:${API_PORT:-8000}/api/v1"
        start_service "frontend" "NEXT_PUBLIC_API_URL=$api_base npm run dev -- --port ${FRONTEND_PORT:-3000}"
    fi
    
    # 启动Celery工作进程（使用API虚拟环境）
    if [[ "$OS" == "windows" ]]; then
        # Windows下设置UTF-8编码，避免中文乱码（Git Bash中使用export）
        start_service "celery-worker" "cd data-processor && export PYTHONIOENCODING=utf-8 && ../api-gateway/.venv/Scripts/python.exe -m celery -A tasks worker --loglevel=${CELERY_LOGLEVEL:-info} --concurrency=${CELERY_WORKERS:-4}"
    else
        start_service "celery-worker" "cd data-processor && PYTHONIOENCODING=utf-8 ../api-gateway/.venv/bin/python -m celery -A tasks worker --loglevel=${CELERY_LOGLEVEL:-info} --concurrency=${CELERY_WORKERS:-4}"
    fi
    
    # 启动Celery监控（可选）
    if [[ "$OS" == "windows" ]]; then
        # Windows下设置UTF-8编码，避免中文乱码（Git Bash中使用export）
        start_service "celery-flower" "cd data-processor && export PYTHONIOENCODING=utf-8 && ../api-gateway/.venv/Scripts/python.exe -m celery -A tasks flower --port=${CELERY_FLOWER_PORT:-5555} --address=0.0.0.0"
    else
        start_service "celery-flower" "cd data-processor && PYTHONIOENCODING=utf-8 ../api-gateway/.venv/bin/python -m celery -A tasks flower --port=${CELERY_FLOWER_PORT:-5555} --address=0.0.0.0"
    fi
    
    # 等待服务完全启动
    log_info "等待服务完全启动..."
    sleep "${HEALTH_CHECK_INITIAL_WAIT:-10}"
    
    # 健康检查（API/前端）
    health_check "API服务" "http://localhost:${API_PORT:-8000}/health" || log_warn "API服务健康检查失败，继续运行"
    if [[ -d "web-frontend" ]]; then
        health_check "前端服务" "http://localhost:${FRONTEND_PORT:-3000}" || log_warn "前端服务健康检查失败，继续运行"
    fi

    # Celery worker 就绪检查（使用 inspect ping）
    log_info "检查 Celery worker 就绪..."
    local celery_py
    if [[ -f "api-gateway/.venv/Scripts/python.exe" ]]; then
        celery_py="api-gateway/.venv/Scripts/python.exe"
    else
        celery_py="api-gateway/.venv/bin/python"
    fi
    if [[ -f "$celery_py" ]]; then
        # 给 worker 一些时间完成加载
        sleep 2
        if (cd data-processor && "$celery_py" -m celery -A tasks inspect ping) >/dev/null 2>&1; then
            log_info "✓ Celery worker 就绪"
        else
            log_warn "Celery worker 未响应 ping，但进程已启动，可能仍在初始化（可稍后重试或查看 logs/celery-worker.log）"
        fi
    else
        log_warn "未找到 Celery Python 解释器，跳过 worker 就绪检查"
    fi

    # Flower 健康检查仅做提示
    health_check "Celery监控" "http://localhost:${CELERY_FLOWER_PORT:-5555}" || log_warn "Celery监控页面暂不可达（不影响 worker 工作），可稍后再试"
}

stop_all_services() {
    log_step "停止所有开发服务..."
    
    local services=("celery-flower" "celery-worker" "frontend" "api" "elasticsearch" "qdrant" "redis")
    
    for service in "${services[@]}"; do
        if [[ "$service" == "redis" ]]; then
            stop_redis_local
        else
            stop_service "$service"
        fi
    done
    
    # 停止日志收集器
    if [[ "${ENABLE_UNIFIED_LOG:-true}" == "true" ]]; then
        stop_log_collector
    fi
}

# ============================================
# 清理功能
# ============================================
cleanup() {
    log_step "执行清理操作..."
    
    # 停止所有服务（包括日志收集器）
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
    unified-log     实时查看统一日志
    log-stats       显示日志统计信息
    log-search <pattern> [service]  搜索日志
    log-level <level>  显示特定级别日志 (ERROR/WARN/INFO/DEBUG)
    clean           清理临时文件和日志
    health          执行健康检查
    help            显示此帮助信息

环境变量:
    DEBUG=true                  启用调试模式
    AUTO_KILL_PORTS=true        自动杀死占用端口的进程
    ENABLE_UNIFIED_LOG=true     启用统一日志收集（默认启用）
    UNIFIED_LOG_MAX_LINES=50000 统一日志最大行数（默认50000）

示例:
    $0 start        # 启动开发环境
    $0 stop         # 停止开发环境
    $0 logs api     # 查看API服务日志
    $0 unified-log  # 查看统一日志
    $0 log-stats    # 查看日志统计
    $0 log-search error api  # 搜索API错误日志
    $0 log-level ERROR  # 显示所有错误日志
    DEBUG=true $0 start  # 以调试模式启动

配置文件: dev.local
日志目录: $LOG_DIR
PID目录: $PID_DIR
统一日志: $LOG_DIR/unified.log
EOF
}

show_status() {
    log_step "服务状态检查..."
    
    local services=("api" "frontend" "celery-worker" "celery-flower" "elasticsearch" "qdrant")
    
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
    
    # 检查日志收集器状态
    if [[ "${ENABLE_UNIFIED_LOG:-true}" == "true" ]]; then
        local collector_pid_file="$LOG_COLLECTOR_PID_FILE"
        if [[ -f "$collector_pid_file" ]]; then
            local pid
            pid=$(cat "$collector_pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log_info "✓ 日志收集器 运行中 (PID: $pid)"
                if [[ -f "$UNIFIED_LOG_FILE" ]]; then
                    local line_count
                    line_count=$(wc -l < "$UNIFIED_LOG_FILE" 2>/dev/null || echo 0)
                    log_info "  统一日志: $line_count 行"
                fi
            else
                log_warn "✗ 日志收集器 已停止 (PID文件存在但进程不存在)"
            fi
        else
            log_warn "✗ 日志收集器 未运行"
        fi
    fi
    
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
                start_redis_local || log_warn "Redis 自动启动未成功"
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
            log_info "日志管理:"
            if [[ "${ENABLE_UNIFIED_LOG:-true}" == "true" ]]; then
                log_info "  - 统一日志: $UNIFIED_LOG_FILE"
                log_info "  - 查看统一日志: '$0 unified-log'"
                log_info "  - 日志统计: '$0 log-stats'"
            fi
            log_info "  - 查看单个服务日志: '$0 logs <service>'"
            log_info ""
            log_info "常用命令:"
            log_info "  - '$0 stop' 停止所有服务"
            log_info "  - '$0 status' 查看服务状态"
            log_info "  - '$0 restart' 重启所有服务"
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
        unified-log)
            log_info "📜 查看统一日志"
            show_unified_log
            ;;
        log-stats)
            log_info "📊 日志统计信息"
            log_statistics
            ;;
        log-search)
            log_info "🔍 搜索日志"
            search_unified_log "$2" "$3"
            ;;
        log-level)
            log_info "📋 显示日志级别"
            show_log_level "$2"
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
