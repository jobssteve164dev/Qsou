import os
import sys
import yaml
import json
import time
import psutil
import subprocess
import requests
import shutil
import zipfile
import asyncio
import socket
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import platform
import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from starlette.requests import Request
from pydantic import BaseModel
from prometheus_client import CollectorRegistry, Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dev_services.yaml"
ADMIN_TOKEN = os.getenv("DEVMAN_TOKEN")
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ------------- dev.local 环境加载 -------------
def _load_dev_local(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        if not path.exists():
            return env
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            env[key] = val
    except Exception:
        pass
    return env

DEV_ENV: Dict[str, str] = _load_dev_local(ROOT / "dev.local")

def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    if v is not None and v != "":
        return v
    v = DEV_ENV.get(key)
    return v if v != "" else default


class ServiceAction(BaseModel):
    name: str

class ProfileAction(BaseModel):
    name: str
    stop_others: Optional[bool] = False
    wait_ready: Optional[bool] = True
    timeout_sec: Optional[int] = 120

class KillPortAction(BaseModel):
    port: int
    token: Optional[str] = None


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(str(CONFIG_PATH))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def service_def(name: str) -> Dict[str, Any]:
    cfg = load_config()
    svcs = cfg.get("services", {})
    if name not in svcs:
        raise KeyError(name)
    meta = dict(svcs[name] or {})
    # 覆盖端口：以 dev.local 为准（如果提供）
    port_map = {
        "api": "API_PORT",
        "frontend": "FRONTEND_PORT",
        "redis": "REDIS_PORT",
        "elasticsearch": "ELASTICSEARCH_PORT",
        "qdrant": "QDRANT_PORT",
    }
    env_key = port_map.get(name)
    if env_key and DEV_ENV.get(env_key):
        try:
            p = int(DEV_ENV.get(env_key))
            stop = dict((meta.get("stop") or {}))
            stop["port"] = p
            meta["stop"] = stop
        except Exception:
            pass
    return meta


def all_services_defs() -> Dict[str, Any]:
    cfg = load_config()
    return cfg.get("services", {}) or {}


def _popen(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None, log_path: Optional[Path] = None) -> psutil.Process:
    # 将子进程输出写入日志文件，便于排障；若未提供日志路径则丢弃输出
    stdout_target = subprocess.DEVNULL
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # 追加模式，统一编码为utf-8
            f = open(log_path, "ab", buffering=0)
            banner = (f"\n\n==== [DevManager] START {time.strftime('%Y-%m-%d %H:%M:%S')} "
                      f"cwd={cwd} cmd={' '.join(cmd)} ====\n").encode("utf-8", errors="ignore")
            f.write(banner)
            stdout_target = f
        except Exception:
            stdout_target = subprocess.DEVNULL
            f = None
    else:
        f = None
    try:
        creationflags = 0
        # 在 Windows 下使用 CREATE_NO_WINDOW，避免弹出控制台阻塞退出；并禁用交互式暂停（如某些 .bat 会询问 Y/N）
        if platform.system().lower().startswith("win"):
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=stdout_target, stderr=subprocess.STDOUT, env=env, creationflags=creationflags)
    finally:
        # 关闭父进程持有的文件句柄，子进程仍可写入
        try:
            if f is not None:
                f.flush()
                f.close()
        except Exception:
            pass
    return psutil.Process(proc.pid)


def _download_file(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def _ensure_redis_windows(version: str = "5.0.14.1") -> bool:
    base = ROOT / "vendor" / "redis"
    exe = base / "redis-server.exe"
    if exe.exists():
        return True
    # 如果用户手动解压在子目录，尝试就地发现并复制
    try:
        for p in base.rglob("redis-server.exe"):
            if p.resolve() != exe.resolve():
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                try:
                    shutil.copyfile(str(p), str(exe))
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    zip_name = f"Redis-x64-{version}.zip"
    alt = _env("REDIS_ZIP_URL") or _env("VENDOR_MIRROR_REDIS")
    url = alt or f"https://github.com/tporadowski/redis/releases/download/v{version}/{zip_name}"
    dest_zip = base / zip_name
    _op_event("redis", "prepare", f"downloading {zip_name}")
    ok = _download_file(url, dest_zip)
    if not ok:
        _op_event("redis", "prepare", "download failed", level="error")
        return False
    # 使用 Python 解压，避免 PowerShell 依赖
    try:
        with zipfile.ZipFile(dest_zip, 'r') as z:
            z.extractall(base)
    except Exception:
        _op_event("redis", "prepare", "extract failed", level="error")
        return False
    # 尝试定位并复制可执行文件到固定位置
    try:
        if not exe.exists():
            for p in base.rglob("redis-server.exe"):
                try:
                    shutil.copyfile(str(p), str(exe))
                    break
                except Exception:
                    continue
    except Exception:
        pass
    return exe.exists()


def _ensure_elasticsearch_windows(version: str = "8.11.0") -> Optional[Path]:
    base = ROOT / "vendor" / "elasticsearch"
    # 直接可用的 layout
    if (base / "bin" / "elasticsearch.bat").exists():
        return base
    # 尝试在子目录中查找解压后的目录
    for p in base.rglob("bin/elasticsearch.bat"):
        try:
            # 统一把找到的目录提升为 base（软链接/复制均可，这里仅返回路径）
            return p.parent.parent
        except Exception:
            continue
    # 需要下载
    zip_name = f"elasticsearch-{version}-windows-x86_64.zip"
    alt = _env("ES_ZIP_URL") or _env("VENDOR_MIRROR_ES")
    url = alt or f"https://artifacts.elastic.co/downloads/elasticsearch/{zip_name}"
    dest_zip = base / zip_name
    _op_event("elasticsearch", "prepare", f"downloading {zip_name}")
    if not _download_file(url, dest_zip):
        _op_event("elasticsearch", "prepare", "download failed", level="error")
        return None
    try:
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f"Expand-Archive -Path '{str(dest_zip)}' -DestinationPath '{str(base)}' -Force"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    for p in base.rglob("bin/elasticsearch.bat"):
        return p.parent.parent
    _op_event("elasticsearch", "prepare", "extract not found", level="error")
    return None


def _ensure_qdrant_windows(version: str = "1.6.9") -> bool:
    base = ROOT / "vendor" / "qdrant"
    exe = base / "qdrant.exe"
    if exe.exists():
        return True
    # 直接就地发现
    try:
        for p in base.rglob("qdrant.exe"):
            if p.resolve() != exe.resolve():
                try:
                    shutil.copyfile(str(p), str(exe))
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    candidates = [
        f"qdrant_windows_x86_64.zip",
        f"qdrant-x86_64-pc-windows-msvc.zip",
    ]
    ok = False
    for name in candidates:
        alt = _env("QDRANT_ZIP_URL") or _env("VENDOR_MIRROR_QDRANT")
        url = alt or f"https://github.com/qdrant/qdrant/releases/download/v{version}/{name}"
        dest_zip = base / name
        _op_event("qdrant", "prepare", f"downloading {name}")
        if _download_file(url, dest_zip):
            try:
                subprocess.run([
                    "powershell", "-NoProfile", "-Command",
                    f"Expand-Archive -Path '{str(dest_zip)}' -DestinationPath '{str(base)}' -Force"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ok = True
                break
            except Exception:
                continue
    if not ok:
        _op_event("qdrant", "prepare", "download failed", level="error")
        return False
    # 定位可执行文件
    if exe.exists():
        return True
    for p in base.rglob("qdrant.exe"):
        try:
            p.replace(exe)
            break
        except Exception:
            pass
    return exe.exists()


def _which_executable(name: str) -> Optional[str]:
    try:
        p = shutil.which(name)
        return p
    except Exception:
        return None


def _resolve_executable(service: str, exe_candidate: str, cwd: Path) -> Optional[str]:
    """Resolve executable path robustly across vendor layouts and PATH.

    - Prefers path relative to cwd
    - Searches vendor subdirectories
    - Falls back to system PATH
    """
    # 0) environment overrides
    try:
        env_key = None
        if service == "redis":
            env_key = "DEVMGR_REDIS_EXE"
        elif service == "qdrant":
            env_key = "DEVMGR_QDRANT_EXE"
        elif service == "elasticsearch":
            env_key = "DEVMGR_ES_EXE"
        if env_key and os.getenv(env_key):
            p = Path(os.getenv(env_key)).resolve()
            if p.exists():
                return str(p)
    except Exception:
        pass

    # 1) path relative to cwd
    try:
        cand = (cwd / exe_candidate).resolve()
        if cand.exists():
            return str(cand)
    except Exception:
        pass
    # 2) project-root relative
    try:
        cand = (ROOT / exe_candidate).resolve()
        if cand.exists():
            return str(cand)
    except Exception:
        pass
    # 3) vendor search by service
    try:
        if service == "redis":
            for p in (ROOT / "vendor" / "redis").rglob("redis-server.exe"):
                return str(p.resolve())
        if service == "qdrant":
            for p in (ROOT / "vendor" / "qdrant").rglob("qdrant.exe"):
                return str(p.resolve())
        if service == "elasticsearch":
            for p in (ROOT / "vendor" / "elasticsearch").rglob("bin/elasticsearch.bat"):
                return str(p.resolve())
            for p in (ROOT / "vendor" / "elasticsearch").rglob("bin/elasticsearch"):
                return str(p.resolve())
    except Exception:
        pass
    # 4) PATH fallback
    p = _which_executable(Path(exe_candidate).name)
    if p:
        return p
    return None


def _find_by_port(port: int) -> Optional[psutil.Process]:
    try:
        for p in psutil.process_iter(["pid", "name", "connections"]):
            for c in p.connections(kind="inet"):
                if c.laddr and c.laddr.port == port:
                    return psutil.Process(p.pid)
    except Exception:
        pass
    return None


def _kill_process_tree(pid: int):
    try:
        p = psutil.Process(pid)
    except Exception:
        return
    system = platform.system().lower()
    if "windows" in system:
        # 通过 taskkill 终止整个进程树
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        # 优雅终止所有子进程，再杀父进程
        try:
            children = p.children(recursive=True)
            for c in children:
                try:
                    c.terminate()
                except Exception:
                    pass
            _, alive = psutil.wait_procs(children, timeout=5)
            for a in alive:
                try:
                    a.kill()
                except Exception:
                    pass
            try:
                p.terminate()
            except Exception:
                pass
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        except Exception:
            pass


def _wait_port_state(port: int, expect_open: bool, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        is_open = _is_port_listening(port)
        if is_open == expect_open:
            return True
        time.sleep(0.3)
    return _is_port_listening(port) == expect_open


def _is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def _tail_file(path: Path, lines: int = 200) -> List[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()
        return data[-lines:]


def _slice_file(path: Path, offset: int, limit: int) -> Dict[str, Any]:
    if not path.exists():
        return {"total": 0, "lines": []}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()
    total = len(data)
    # 偏移从文件尾部计算：offset=0 表示最新的 limit 行
    start = max(total - offset - limit, 0)
    end = max(total - offset, 0)
    return {"total": total, "lines": data[start:end]}


app = FastAPI(title="Qsou Dev Manager", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 以中间件方式兜住 CancelledError，避免注册异常处理器引发 Starlette 断言
@app.middleware("http")
async def _cancel_guard(request: Request, call_next):
    try:
        return await call_next(request)
    except asyncio.CancelledError:
        return JSONResponse({"error": "server is shutting down"}, status_code=503)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Dev Manager UI not found. Please open /docs or /services"}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/services")
def list_services():
    cfg = load_config()
    svcs = cfg.get("services", {})
    out = []
    for key, meta in svcs.items():
        status = status_of(key)
        out.append({"id": key, "name": meta.get("name", key), **status})
    return out


def status_of(name: str) -> Dict[str, Any]:
    meta = service_def(name)
    running = False
    pid = None
    stop_cfg = meta.get("stop") or {}
    # 1) 优先通过端口监听判断
    if isinstance(stop_cfg, dict) and stop_cfg.get("port"):
        p = _find_by_port(int(stop_cfg["port"]))
        if p and p.is_running():
            running = True
            pid = p.pid
    # 2) 回退：通过 pidfile 判断
    if not running and isinstance(stop_cfg, dict) and stop_cfg.get("pidfile"):
        pidfile = ROOT / str(stop_cfg.get("pidfile"))
        if pidfile.exists():
            try:
                file_pid = int(pidfile.read_text().strip())
                pp = psutil.Process(file_pid)
                if pp.is_running():
                    running = True
                    pid = file_pid
            except Exception:
                pass
    healthy = None
    latency_ms = None
    health_cfg = meta.get("health") or {}
    url = health_cfg.get("url")
    if url and running:
        try:
            t0 = time.time()
            r = requests.get(url, timeout=1.5)
            latency_ms = int((time.time() - t0) * 1000)
            healthy = (200 <= r.status_code < 400)
        except Exception:
            healthy = False
    # 如果未配置健康检查，但存在端口定义，使用端口监听作为运行健康的近似指标
    if healthy is None:
        port = (meta.get("stop") or {}).get("port")
        if port:
            healthy = _is_port_listening(int(port))
    # 无 URL/端口时使用就绪日志作为健康近似
    if healthy is None:
        ready_cfg = meta.get("ready") or {}
        log_pattern = (ready_cfg.get("log_pattern") or "").strip()
        log_file = (ready_cfg.get("log_file") or meta.get("log"))
        if log_pattern and log_file:
            try:
                import re as _re
                lines = _tail_file(ROOT / str(log_file), lines=800)
                text = "".join(lines)
                if _re.search(log_pattern, text, flags=_re.IGNORECASE):
                    healthy = True
            except Exception:
                pass
    return {"running": running, "pid": pid, "healthy": healthy, "latency_ms": latency_ms}


def _collect_dependencies(start: str, graph: Dict[str, List[str]],
                          visiting: Set[str], visited: Set[str], order: List[str]):
    if start in visited:
        return
    if start in visiting:
        raise HTTPException(409, f"dependency cycle detected at {start}")
    visiting.add(start)
    for dep in graph.get(start, []) or []:
        _collect_dependencies(dep, graph, visiting, visited, order)
    visiting.remove(start)
    visited.add(start)
    if start not in order:
        order.append(start)


def _resolve_order_with_deps(target: List[str]) -> List[str]:
    svcs = all_services_defs()
    # 构造依赖图
    graph: Dict[str, List[str]] = {}
    for sid, meta in svcs.items():
        deps = meta.get("depends_on") or []
        # 仅保留有效服务名
        graph[sid] = [d for d in deps if d in svcs]
    # 递归收集并拓扑排序
    order: List[str] = []
    visited: Set[str] = set()
    for name in target:
        if name not in svcs:
            raise HTTPException(404, f"service not found: {name}")
        _collect_dependencies(name, graph, set(), visited, order)
    return order


def _wait_until_ready(name: str, timeout_sec: int = 120, poll_interval: float = 0.8) -> bool:
    meta = service_def(name)
    deadline = time.time() + max(timeout_sec, 1)
    # 1) 优先 ready 配置（支持日志模式）
    ready_cfg = meta.get("ready") or {}
    log_pattern = (ready_cfg.get("log_pattern") or "").strip()
    log_file = (ready_cfg.get("log_file") or meta.get("log"))
    health_cfg = meta.get("health") or {}
    url = health_cfg.get("url")
    port = (meta.get("stop") or {}).get("port")
    marker = "==== [DevManager] START"
    while time.time() < deadline:
        try:
            # a) 日志就绪模式：在最近一次 START 标记后的新日志中匹配正则
            if log_pattern and log_file:
                path = ROOT / str(log_file)
                lines = _tail_file(path, lines=1200)
                last_start = -1
                for i, ln in enumerate(lines):
                    if marker in ln:
                        last_start = i
                region = lines[last_start + 1:] if last_start >= 0 else lines
                text = "".join(region)
                try:
                    if re.search(log_pattern, text, flags=re.IGNORECASE):
                        return True
                except re.error:
                    # 正则非法则退化为子串匹配
                    if log_pattern.lower() in text.lower():
                        return True

            # b) pidfile 就绪（针对 Celery Beat 这类）
            stop_cfg = meta.get("stop") or {}
            pidfile = stop_cfg.get("pidfile")
            if pidfile:
                try:
                    p = int((ROOT / str(pidfile)).read_text().strip())
                    if p > 0 and psutil.pid_exists(p):
                        return True
                except Exception:
                    pass

            # c) 健康 URL
            if url:
                r = requests.get(url, timeout=1.2)
                if 200 <= r.status_code < 400:
                    return True

            # d) 端口监听
            if port and _is_port_listening(int(port)):
                return True

            # e) 退化：进程存在
            st = status_of(name)
            if st.get("running") and st.get("healthy") is not False:
                # 仅当显式 unhealthy 才判定为未就绪
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


# ---------------- Metrics ----------------
registry = CollectorRegistry()
metric_service_running = Gauge("devmgr_service_running", "Service running state", ["service"], registry=registry)
metric_service_starts = Counter("devmgr_service_start_total", "Service start calls", ["service"], registry=registry)
metric_service_stops = Counter("devmgr_service_stop_total", "Service stop calls", ["service"], registry=registry)
metric_requests = Counter("devmgr_requests_total", "API requests", ["path"], registry=registry)

# --------------- In-memory operation progress ---------------
_op_lock = threading.Lock()
_current_op: Dict[str, Any] = {}
PROGRESS_LOG = Path(os.getenv("DEVMGR_PROGRESS_LOG", str(ROOT / "logs" / "devmgr_progress.jsonl")))

def _append_event_to_file(record: Dict[str, Any]):
    try:
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # 文件写入失败不影响主流程
        pass

def _reset_progress_log(op_id: int):
    try:
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        if PROGRESS_LOG.exists() and PROGRESS_LOG.stat().st_size > 0:
            ts = time.strftime('%Y%m%d_%H%M%S')
            backup = PROGRESS_LOG.with_name(f"devmgr_progress_{ts}_{op_id}.jsonl")
            try:
                PROGRESS_LOG.replace(backup)
            except Exception:
                # 备份失败则尝试清空
                with open(PROGRESS_LOG, 'w', encoding='utf-8') as f:
                    f.write('')
        # 确保创建空文件
        if not PROGRESS_LOG.exists():
            with open(PROGRESS_LOG, 'w', encoding='utf-8') as f:
                f.write('')
    except Exception:
        pass

def _op_begin(profile: str, ordered: List[str]):
    with _op_lock:
        _current_op.clear()
        op_id = int(time.time()*1000)
        _reset_progress_log(op_id)
        _current_op.update({
            "id": op_id,
            "profile": profile,
            "status": "running",
            "ordered": list(ordered),
            "events": [],
            "started_at": time.time(),
            "ended_at": None,
            "error": None,
        })
        _append_event_to_file({
            "t": time.time(),
            "type": "begin",
            "op_id": op_id,
            "profile": profile,
            "ordered": list(ordered),
        })

def _op_event(service: str, action: str, message: str, level: str = "info"):
    with _op_lock:
        ev = {"ts": time.time(), "service": service, "action": action, "message": message, "level": level}
        (_current_op.get("events") or []).append(ev)
        _append_event_to_file({
            "t": ev["ts"],
            "type": "event",
            "op_id": _current_op.get("id"),
            "service": service,
            "action": action,
            "message": message,
            "level": level,
        })

def _op_end(status: str, error: Optional[str] = None):
    with _op_lock:
        _current_op["status"] = status
        _current_op["ended_at"] = time.time()
        if error:
            _current_op["error"] = error
        _append_event_to_file({
            "t": _current_op["ended_at"],
            "type": "end",
            "op_id": _current_op.get("id"),
            "status": status,
            "error": error,
        })


@app.post("/services/start")
def start_service(body: ServiceAction):
    metric_requests.labels(path="/services/start").inc()
    meta = service_def(body.name)
    if status_of(body.name)["running"]:
        return {"result": "already running"}
    cwd = ROOT / meta.get("cwd", ".")
    # 根据平台选择启动命令
    is_windows = platform.system().lower().startswith("win")
    cmd = (meta.get("start_win") if is_windows and meta.get("start_win") else meta.get("start"))
    if not isinstance(cmd, list):
        raise HTTPException(400, "start command must be list")
    try:
        # 日志文件（相对ROOT），若未配置则默认写入 logs/{service}.log
        log_rel = meta.get("log") or f"logs/{body.name}.log"
        log_path = ROOT / str(log_rel)
        # 自动准备数据服务（Windows 内置 vendor 版本）
        if platform.system().lower().startswith("win"):
            if body.name == "redis":
                _ensure_redis_windows()
            elif body.name == "elasticsearch":
                base = _ensure_elasticsearch_windows() or (ROOT / meta.get("cwd", "."))
                cwd = base
            elif body.name == "qdrant":
                _ensure_qdrant_windows()
            elif body.name == "celery_worker":
                # Windows 下使用 solo 池避免 prefork 问题
                if "-P" not in cmd and "--pool" not in cmd:
                    cmd += ["-P", "solo"]
                if "--concurrency" not in cmd:
                    cmd += ["--concurrency", "1"]
        # 在 Windows 上对可执行文件路径进行稳健解析（避免多层目录/未入 PATH）
        if platform.system().lower().startswith("win") and cmd:
            exe = _resolve_executable(body.name, cmd[0], cwd)
            if exe:
                cmd = [exe] + cmd[1:]
            else:
                raise HTTPException(500, f"start failed: executable not found for {body.name}: {cmd[0]}")
        # 统一设置 UTF-8 输出，避免中文日志乱码
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        p = _popen(cmd, cwd, env=env, log_path=log_path)
        time.sleep(0.5)
        metric_service_starts.labels(service=body.name).inc()
        return {"result": "started", "pid": p.pid}
    except Exception as e:
        raise HTTPException(500, f"start failed: {e}")


@app.post("/services/stop")
def stop_service(body: ServiceAction):
    metric_requests.labels(path="/services/stop").inc()
    meta = service_def(body.name)
    # by port
    port = (meta.get("stop") or {}).get("port")
    if port:
        p = _find_by_port(int(port))
        if p and p.is_running():
            try:
                _kill_process_tree(p.pid)
                _wait_port_state(int(port), expect_open=False, timeout=10.0)
                metric_service_stops.labels(service=body.name).inc()
                return {"result": "stopped"}
            except Exception as e:
                raise HTTPException(500, f"stop failed: {e}")
        return {"result": "not running"}
    # by pidfile
    pidfile = (meta.get("stop") or {}).get("pidfile")
    if pidfile and (ROOT / pidfile).exists():
        pid = int((ROOT / pidfile).read_text().strip())
        p = psutil.Process(pid)
        p.terminate()
        metric_service_stops.labels(service=body.name).inc()
        return {"result": "stopped"}
    return {"result": "noop"}


@app.post("/services/restart")
def restart_service(body: ServiceAction):
    metric_requests.labels(path="/services/restart").inc()
    stop_service(body)
    return start_service(body)


@app.get("/services/{name}/logs")
def service_logs(name: str, lines: int = 200):
    meta = service_def(name)
    log = meta.get("log")
    if not log:
        # 默认日志路径：logs/{service}.log
        log = f"logs/{name}.log"
    content = _tail_file(ROOT / str(log), lines)
    return {"lines": content}


@app.get("/services/{name}/logs/paged")
def service_logs_paged(name: str, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=2000)):
    meta = service_def(name)
    log = meta.get("log")
    if not log:
        log = f"logs/{name}.log"
    result = _slice_file(ROOT / str(log), offset=offset, limit=limit)
    return result


@app.get("/services/{name}/logs/download")
def service_logs_download(name: str):
    meta = service_def(name)
    log = meta.get("log")
    if not log:
        raise HTTPException(404, "no log configured")
    path = ROOT / log
    if not path.exists():
        raise HTTPException(404, "log file not found")
    return FileResponse(str(path), filename=f"{name}.log")


@app.get("/profiles")
def list_profiles():
    cfg = load_config()
    return cfg.get("profiles", {})


@app.post("/profiles/apply")
def apply_profile(body: ProfileAction):
    cfg = load_config()
    profiles = cfg.get("profiles", {})
    if body.name not in profiles:
        raise HTTPException(404, "profile not found")
    target = profiles[body.name] or []
    ordered = _resolve_order_with_deps(target)
    # 可选：先停掉非该配置内的其他服务
    if body.stop_others:
        others = [s for s in (cfg.get("services", {}) or {}).keys() if s not in ordered]
        for s in others:
            try:
                stop_service(ServiceAction(name=s))
            except Exception:
                pass
    # 固定进度日志目录到项目内 logs/，避免写到下载目录等异常路径
    os.environ.setdefault("DEVMGR_PROGRESS_LOG", str(ROOT / "logs" / "devmgr_progress.jsonl"))
    try:
        _op_begin(body.name, ordered)
    except Exception:
        (ROOT / "logs").mkdir(parents=True, exist_ok=True)
        _op_begin(body.name, ordered)
    started: List[Dict[str, Any]] = []
    for s in ordered:
        try:
            _op_event(s, "start", "starting")
            res = start_service(ServiceAction(name=s))
            started.append({"service": s, **res})
            if body.wait_ready:
                ok = _wait_until_ready(s, int(body.timeout_sec or 120))
                _op_event(s, "ready", "healthy" if ok else "not_ready", level=("info" if ok else "warn"))
        except Exception as e:
            _op_event(s, "error", str(e), level="error")
            started.append({"service": s, "error": str(e)})
            _op_end("failed", error=str(e))
            return {"result": "failed", "profile": body.name, "ordered": ordered, "details": started, "error": str(e)}
    _op_end("ok")
    return {"result": "applied", "profile": body.name, "ordered": ordered, "details": started}


@app.post("/profiles/stop")
def stop_profile(body: ProfileAction):
    cfg = load_config()
    profiles = cfg.get("profiles", {})
    if body.name not in profiles:
        raise HTTPException(404, "profile not found")
    target = profiles[body.name] or []
    ordered = _resolve_order_with_deps(target)
    # 停止顺序应与启动相反
    for s in reversed(ordered):
        try:
            stop_service(ServiceAction(name=s))
        except Exception:
            pass
    return {"result": "stopped", "profile": body.name}


def _require_token(token: Optional[str]):
    if ADMIN_TOKEN and token == ADMIN_TOKEN:
        return
    if ADMIN_TOKEN:
        raise HTTPException(403, "invalid token")
    # 如果未配置令牌，默认允许（开发环境）
    return


@app.get("/diagnose/ports")
def diagnose_ports():
    cfg = load_config()
    svcs = cfg.get("services", {})
    rows = []
    for sid, meta in svcs.items():
        # 合并 dev.local 覆盖后的实时定义
        port = (service_def(sid).get("stop") or {}).get("port") or (meta.get("stop") or {}).get("port")
        if not port:
            continue
        p = _find_by_port(int(port))
        rows.append({
            "service": sid,
            "port": int(port),
            "occupied": bool(p and p.is_running()),
            "pid": p.pid if p and p.is_running() else None,
        })
    return rows


@app.post("/diagnose/kill_port")
def kill_port(body: KillPortAction):
    _require_token(body.token)
    p = _find_by_port(int(body.port))
    if not p or not p.is_running():
        return {"result": "not found"}
    try:
        _kill_process_tree(p.pid)
        _wait_port_state(int(body.port), expect_open=False, timeout=8.0)
        return {"result": "killed", "pid": p.pid}
    except Exception as e:
        raise HTTPException(500, f"kill failed: {e}")


@app.get("/metrics")
def metrics():
    # 刷新服务运行状态度量
    cfg = load_config()
    for sid in (cfg.get("services", {}) or {}).keys():
        metric_service_running.labels(service=sid).set(1.0 if status_of(sid).get("running") else 0.0)
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/progress")
def progress():
    with _op_lock:
        # 提供一个快照（浅拷贝），避免前端引用内部结构
        snap = json.loads(json.dumps(_current_op)) if _current_op else {}
        # 附带每个服务的当前健康状态，便于前端展示更直观的进度
        try:
            svcs = load_config().get("services", {})
            states = {}
            for sid in (snap.get("ordered") or svcs.keys()):
                try:
                    states[sid] = status_of(sid)
                except Exception:
                    states[sid] = {"running": False}
            snap["states"] = states
        except Exception:
            pass
        return snap


@app.get("/diagnose/vendor")
def diagnose_vendor():
    """Scan vendor directories and resolve executable paths for data services.
    Returns resolved path candidates and existence checks for redis/elasticsearch/qdrant.
    """
    result: Dict[str, Any] = {"root": str(ROOT)}
    def exists(p: Optional[Path]):
        try:
            return bool(p and p.exists())
        except Exception:
            return False
    # Redis
    red_dir = ROOT / "vendor" / "redis"
    red_candidates = [p.resolve() for p in red_dir.rglob("redis-server.exe")]
    result["redis"] = {
        "cwd": str(red_dir),
        "candidates": [str(p) for p in red_candidates],
        "preferred": str((red_dir / "redis-server.exe").resolve()),
        "preferred_exists": exists(red_dir / "redis-server.exe"),
    }
    # Elasticsearch
    es_dir = ROOT / "vendor" / "elasticsearch"
    es_candidates = [p.resolve() for p in es_dir.rglob("bin/elasticsearch.bat")]
    if not es_candidates:
        es_candidates = [p.resolve() for p in es_dir.rglob("bin/elasticsearch")]
    result["elasticsearch"] = {
        "cwd": str(es_dir),
        "candidates": [str(p) for p in es_candidates],
        "preferred": str((es_dir / "bin" / "elasticsearch.bat").resolve()),
        "preferred_exists": exists(es_dir / "bin" / "elasticsearch.bat"),
    }
    # Qdrant
    qd_dir = ROOT / "vendor" / "qdrant"
    qd_candidates = [p.resolve() for p in qd_dir.rglob("qdrant.exe")]
    result["qdrant"] = {
        "cwd": str(qd_dir),
        "candidates": [str(p) for p in qd_candidates],
        "preferred": str((qd_dir / "qdrant.exe").resolve()),
        "preferred_exists": exists(qd_dir / "qdrant.exe"),
    }
    return result


def _probe_url(url: str, timeout: float = 1.2) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return 200 <= r.status_code < 400
    except Exception:
        return False


@app.get("/diagnose/frontend_url")
def diagnose_frontend_url():
    cfg = load_config()
    host = "127.0.0.1"
    # 优先配置的端口
    port = (((cfg.get("services", {}) or {}).get("frontend", {}) or {}).get("stop") or {}).get("port") or 3000
    candidates = [int(port)] + [p for p in range(3000, 3011)] + [3333]
    tried: List[str] = []
    for p in candidates:
        url = f"http://{host}:{p}/"
        tried.append(url)
        if _probe_url(url):
            return {"url": url, "tried": tried}
    return {"url": None, "tried": tried}


@app.get("/progress/events")
def progress_events(limit: int = Query(200, ge=1, le=2000)):
    if not PROGRESS_LOG.exists():
        return {"events": []}
    # 读取最后 limit 条 JSON 行
    lines = _tail_file(PROGRESS_LOG, lines=limit)
    events: List[Dict[str, Any]] = []
    for ln in lines:
        try:
            events.append(json.loads(ln))
        except Exception:
            events.append({"raw": ln})
    return {"events": events}


@app.get("/progress/download")
def progress_download():
    if not PROGRESS_LOG.exists():
        raise HTTPException(404, "no progress log")
    return FileResponse(str(PROGRESS_LOG), filename="devmgr_progress.jsonl")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5500)


