"""Runtime gate that keeps writers behind completed, independently-run migrations."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable


ALEMBIC_REVISION = "20260809_01"
SQLITE_IMPORT_VERSION = "one-time-sqlite-to-postgres-20260809"
OBJECT_IMPORT_VERSION = "one-time-file-objects-to-s3-20260809"


def required_migrations(data_root: Path) -> dict[str, str]:
    required = {"schema": ALEMBIC_REVISION}
    if (data_root.resolve() / "catalog.sqlite3").is_file():
        required["catalog"] = SQLITE_IMPORT_VERSION
    if os.getenv("QSOU_OBJECT_STORAGE_BACKEND", "file").strip().lower() == "s3":
        required["objects"] = OBJECT_IMPORT_VERSION
    return required


def migration_state(store) -> dict[str, Any]:
    required = required_migrations(store.root)
    try:
        with store._connection() as connection:
            alembic = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            applied = {
                row["version"]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
    except Exception as exc:
        return {
            "status": "waiting",
            "required": required,
            "missing": list(required),
            "error_type": type(exc).__name__,
        }

    missing = []
    if not alembic or alembic["version_num"] != required["schema"]:
        missing.append("schema")
    for name in ("catalog", "objects"):
        if name in required and required[name] not in applied:
            missing.append(name)
    return {
        "status": "ready" if not missing else "waiting",
        "required": required,
        "missing": missing,
    }


def wait_for_migrations(
    store,
    *,
    on_wait: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    poll_seconds: int = 5,
) -> dict[str, Any]:
    while True:
        if should_stop and should_stop():
            return {"status": "stopped"}
        state = migration_state(store)
        if state["status"] == "ready":
            return state
        if on_wait:
            on_wait(state)
        time.sleep(max(1, poll_seconds))
