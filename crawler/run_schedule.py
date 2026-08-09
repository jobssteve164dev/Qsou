#!/usr/bin/env python3
"""Run registered crawlers continuously and publish an observable status file."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qsou_data import DataAssetStore
from qsou_crawler.adapters import AdapterRegistry


DATA_ROOT = Path(os.getenv("QSOU_DATA_ROOT", "/var/lib/qsou"))
STATUS_PATH = DATA_ROOT / "collector-status.json"
CRAWLER_ROOT = Path(__file__).resolve().parent
POLL_SECONDS = max(30, int(os.getenv("QSOU_CRAWL_POLL_SECONDS", "60")))
SOURCE_IDS = [
    value.strip()
    for value in os.getenv(
        "QSOU_SOURCE_IDS", ""
    ).split(",")
    if value.strip()
]
STOP_REQUESTED = False
STORE = DataAssetStore()
ADAPTERS = AdapterRegistry(STORE.registry)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def write_status(**values: object) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    timeline: dict[str, object] = {}
    if STATUS_PATH.is_file():
        try:
            previous = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            timeline = {
                key: previous[key]
                for key in ("last_started_at", "last_finished_at", "next_run_at")
                if previous.get(key)
            }
        except (OSError, json.JSONDecodeError):
            timeline = {}
    payload = {
        "source_ids": [adapter.source_id for adapter in selected_adapters()],
        "poll_seconds": POLL_SECONDS,
        **timeline,
        **values,
    }
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


def selected_adapters():
    return ADAPTERS.all(SOURCE_IDS or None)


def schedule_seconds(value: object) -> int:
    text = str(value or "30m").strip().lower()
    try:
        if text.endswith("m"):
            return max(300, int(text[:-1]) * 60)
        if text.endswith("h"):
            return max(300, int(text[:-1]) * 3600)
        return max(300, int(text))
    except ValueError:
        return 1800


def parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def is_due(adapter, now: datetime) -> bool:
    latest = STORE.latest_adapter_run(adapter.source_id)
    if not latest or latest.get("state") == "running":
        return latest is None
    finished_at = parse_time(latest.get("finished_at"))
    return finished_at is None or now >= finished_at + timedelta(
        seconds=schedule_seconds(adapter.source.get("schedule"))
    )


def run_adapter(adapter, *, trigger: str = "schedule") -> dict[str, object]:
    run = STORE.begin_adapter_run(
        source_id=adapter.source_id,
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.version,
        trigger=trigger,
    )
    before = STORE.source_counts(adapter.source_id)
    descriptor, report_name = tempfile.mkstemp(prefix=f"qsou-{adapter.source_id}-", suffix=".json")
    os.close(descriptor)
    report_path = Path(report_name)
    report_path.unlink(missing_ok=True)
    report: dict[str, object] = {}
    errors: list[str] = []
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scrapy",
                "crawl",
                "source_adapter",
                "-a",
                f"source_id={adapter.source_id}",
                "-a",
                f"report_path={report_path}",
                "-L",
                "INFO",
                "-s",
                "LOG_FILE=",
            ],
            cwd=CRAWLER_ROOT,
            check=False,
        )
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        if completed.returncode != 0:
            errors.append(f"采集进程退出码 {completed.returncode}")
    except Exception as exc:
        completed = None
        errors.append(str(exc))
    finally:
        report_path.unlink(missing_ok=True)

    after = STORE.source_counts(adapter.source_id)
    metrics = {
        **report,
        "evidence_archived": int(report.get("evidence_archived", 0) or 0),
        "new_raw_objects": max(0, after["raw_objects"] - before["raw_objects"]),
        "new_document_versions": max(
            0, after["document_versions"] - before["document_versions"]
        ),
    }
    errors.extend(str(value) for value in report.get("errors", []) if value)
    entrypoints_succeeded = int(metrics.get("entrypoints_succeeded", 0) or 0)
    documents_indexed = int(metrics.get("documents_indexed", 0) or 0)
    detail_discovered = int(metrics.get("detail_discovered", 0) or 0)
    detail_fetched = int(metrics.get("detail_fetched", 0) or 0)
    documents_emitted = int(metrics.get("documents_emitted", 0) or 0)
    failures = int(metrics.get("failures", 0) or 0)
    if completed is None or completed.returncode != 0 or entrypoints_succeeded == 0:
        state = "failed"
    elif (
        documents_indexed == 0
        or failures > 0
        or detail_fetched != detail_discovered
        or documents_emitted != detail_fetched
    ):
        state = "degraded"
    else:
        state = "healthy"
    return STORE.finish_adapter_run(
        run["run_id"],
        state=state,
        metrics=metrics,
        cursor=report.get("cursor") if state == "healthy" else None,
        errors=errors,
    )


def source_summary() -> dict[str, object]:
    return {
        source["source_id"]: {
            "state": source["collection_state"],
            "adapter_id": source["adapter_id"],
            "adapter_version": source["adapter_version"],
            "last_run": source.get("last_run"),
        }
        for source in STORE.list_sources()
        if source.get("enabled")
    }


def run_requested_sources() -> int:
    completed_count = 0
    while not STOP_REQUESTED:
        request = STORE.claim_adapter_run_request()
        if not request:
            return completed_count
        source_id = str(request["source_id"])
        write_status(
            state="running",
            active_source_id=source_id,
            active_request_id=request["request_id"],
            sources=source_summary(),
            updated_at=iso(utc_now()),
        )
        run_id = None
        result_state = "failed"
        error = None
        try:
            result = run_adapter(ADAPTERS.create(source_id), trigger="manual")
            run_id = str(result["run_id"])
            result_state = str(result["state"])
        except Exception as exc:
            error = str(exc)
        STORE.finish_adapter_run_request(
            str(request["request_id"]),
            run_id=run_id,
            result_state=result_state,
            error=error,
        )
        completed_count += 1
    return completed_count


def run_due_sources() -> None:
    started_at = utc_now()
    run_requested_sources()
    for adapter in selected_adapters():
        if STOP_REQUESTED:
            break
        if not is_due(adapter, utc_now()):
            continue
        write_status(
            state="running",
            active_source_id=adapter.source_id,
            last_started_at=iso(started_at),
            sources=source_summary(),
            updated_at=iso(utc_now()),
        )
        run_adapter(adapter)

    finished_at = utc_now()
    sources = source_summary()
    states = [str(value.get("state")) for value in sources.values()]
    state = "idle" if states and all(value == "healthy" for value in states) else "degraded"
    latest_runs = [
        value["last_run"]
        for value in sources.values()
        if isinstance(value.get("last_run"), dict)
    ]
    last_started_at = max(
        (str(run["started_at"]) for run in latest_runs if run.get("started_at")),
        default=None,
    )
    last_finished_at = max(
        (str(run["finished_at"]) for run in latest_runs if run.get("finished_at")),
        default=None,
    )
    next_run_at = finished_at + timedelta(seconds=POLL_SECONDS)
    write_status(
        state=state,
        active_source_id=None,
        last_started_at=last_started_at,
        last_finished_at=last_finished_at,
        next_run_at=iso(next_run_at),
        sources=sources,
        updated_at=iso(finished_at),
    )
    wait_until(next_run_at)


def main() -> int:
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    recovered = STORE.recover_interrupted_adapter_runs()
    requeued = STORE.recover_interrupted_adapter_run_requests()
    quarantined = STORE.quarantine_generic_snapshots()
    write_status(
        state="starting",
        recovered_interrupted_runs=recovered,
        requeued_interrupted_requests=requeued,
        quarantined_generic_snapshots=quarantined,
        sources=source_summary(),
        updated_at=iso(utc_now()),
    )
    while not STOP_REQUESTED:
        run_due_sources()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
