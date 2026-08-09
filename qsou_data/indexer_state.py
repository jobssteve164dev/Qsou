"""Shared readiness state for the always-on Elasticsearch projector."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def state_path() -> Path:
    root = Path(os.getenv("QSOU_DATA_ROOT", "data/qsou")).resolve()
    return root / "indexer-status.json"


def write_indexer_state(state: str, **details: Any) -> dict[str, Any]:
    payload = {
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def read_indexer_state(max_age_seconds: int | None = None) -> dict[str, Any]:
    maximum_age = max_age_seconds or max(
        30,
        int(os.getenv("QSOU_INDEXER_MAX_HEALTH_AGE_SECONDS", "60")),
    )
    path = state_path()
    if not path.is_file():
        return {"status": "unavailable", "error": "索引器尚未完成首次同步"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(str(payload["updated_at"]).replace("Z", "+00:00"))
        age_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds(),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "error": f"索引器状态无效: {exc}"}
    payload["age_seconds"] = round(age_seconds, 3)
    payload["status"] = (
        "healthy"
        if payload.get("state") == "healthy" and age_seconds <= maximum_age
        else "unavailable"
    )
    if age_seconds > maximum_age:
        payload["error"] = "索引器状态已过期"
    return payload


def main() -> int:
    state = read_indexer_state()
    if state.get("status") != "healthy":
        print(json.dumps(state, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
