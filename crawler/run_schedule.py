#!/usr/bin/env python3
"""Run registered crawlers continuously and publish an observable status file."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


DATA_ROOT = Path(os.getenv("QSOU_DATA_ROOT", "/var/lib/qsou"))
STATUS_PATH = DATA_ROOT / "collector-status.json"
INTERVAL_SECONDS = max(300, int(os.getenv("QSOU_CRAWL_INTERVAL_SECONDS", "1800")))
SPIDERS = [
    value.strip()
    for value in os.getenv(
        "QSOU_CRAWLER_SPIDERS", "company_announcement,financial_news"
    ).split(",")
    if value.strip()
]
STOP_REQUESTED = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def write_status(**values: object) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"spiders": SPIDERS, "interval_seconds": INTERVAL_SECONDS, **values}
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(STATUS_PATH)


def request_stop(signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    write_status(state="stopping", stopped_by_signal=signum, updated_at=iso(utc_now()))


def wait_until(deadline: datetime) -> None:
    while not STOP_REQUESTED:
        remaining = (deadline - utc_now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(5, remaining))


def run_cycle() -> None:
    started_at = utc_now()
    write_status(state="running", last_started_at=iso(started_at), updated_at=iso(started_at))
    results: dict[str, int] = {}

    for spider in SPIDERS:
        if STOP_REQUESTED:
            break
        completed = subprocess.run(
            ["scrapy", "crawl", spider, "-L", "INFO"],
            cwd="/app/crawler",
            check=False,
        )
        results[spider] = completed.returncode

    finished_at = utc_now()
    next_run_at = finished_at + timedelta(seconds=INTERVAL_SECONDS)
    state = "idle" if results and all(code == 0 for code in results.values()) else "degraded"
    write_status(
        state=state,
        last_started_at=iso(started_at),
        last_finished_at=iso(finished_at),
        next_run_at=iso(next_run_at),
        results=results,
        updated_at=iso(finished_at),
    )
    wait_until(next_run_at)


def main() -> int:
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    if not SPIDERS:
        write_status(state="disabled", updated_at=iso(utc_now()))
        return 0
    while not STOP_REQUESTED:
        run_cycle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
