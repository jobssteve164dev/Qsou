import os
import sys
import yaml
import json
import time
import psutil
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from prometheus_client import CollectorRegistry, Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dev_services.yaml"
ADMIN_TOKEN = os.getenv("DEVMAN_TOKEN")
STATIC_DIR = Path(__file__).resolve().parent / "static"


class ServiceAction(BaseModel):
    name: str

class ProfileAction(BaseModel):
    name: str
    stop_others: Optional[bool] = False

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
    return svcs[name]


def _popen(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> psutil.Process:
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return psutil.Process(proc.pid)


def _find_by_port(port: int) -> Optional[psutil.Process]:
    try:
        for p in psutil.process_iter(["pid", "name", "connections"]):
            for c in p.connections(kind="inet"):
                if c.laddr and c.laddr.port == port:
                    return psutil.Process(p.pid)
    except Exception:
        pass
    return None


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
    if "stop" in meta and isinstance(meta["stop"], dict) and meta["stop"].get("port"):
        p = _find_by_port(int(meta["stop"]["port"]))
        if p and p.is_running():
            running = True
            pid = p.pid
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
    return {"running": running, "pid": pid, "healthy": healthy, "latency_ms": latency_ms}


# ---------------- Metrics ----------------
registry = CollectorRegistry()
metric_service_running = Gauge("devmgr_service_running", "Service running state", ["service"], registry=registry)
metric_service_starts = Counter("devmgr_service_start_total", "Service start calls", ["service"], registry=registry)
metric_service_stops = Counter("devmgr_service_stop_total", "Service stop calls", ["service"], registry=registry)
metric_requests = Counter("devmgr_requests_total", "API requests", ["path"], registry=registry)


@app.post("/services/start")
def start_service(body: ServiceAction):
    metric_requests.labels(path="/services/start").inc()
    meta = service_def(body.name)
    if status_of(body.name)["running"]:
        return {"result": "already running"}
    cwd = ROOT / meta.get("cwd", ".")
    cmd = meta.get("start")
    if not isinstance(cmd, list):
        raise HTTPException(400, "start command must be list")
    try:
        p = _popen(cmd, cwd)
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
                p.terminate()
                try:
                    p.wait(timeout=10)
                except Exception:
                    p.kill()
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
        return {"lines": []}
    content = _tail_file(ROOT / log, lines)
    return {"lines": content}


@app.get("/services/{name}/logs/paged")
def service_logs_paged(name: str, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=2000)):
    meta = service_def(name)
    log = meta.get("log")
    if not log:
        return {"total": 0, "lines": []}
    result = _slice_file(ROOT / log, offset=offset, limit=limit)
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
    if body.stop_others:
        others = [s for s in (cfg.get("services", {}) or {}).keys() if s not in target]
        for s in others:
            try:
                stop_service(ServiceAction(name=s))
            except Exception:
                pass
    for s in target:
        try:
            start_service(ServiceAction(name=s))
        except Exception:
            pass
    return {"result": "applied", "profile": body.name}


@app.post("/profiles/stop")
def stop_profile(body: ProfileAction):
    cfg = load_config()
    profiles = cfg.get("profiles", {})
    if body.name not in profiles:
        raise HTTPException(404, "profile not found")
    for s in profiles[body.name] or []:
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
        port = (meta.get("stop") or {}).get("port")
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
        p.terminate()
        try:
            p.wait(timeout=8)
        except Exception:
            p.kill()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5500)


