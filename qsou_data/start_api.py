"""Run an explicitly requested catalog migration before starting the API."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

from .migrate import LegacySqliteMigrator
from .store import DataAssetError, DataAssetStore
from .verify import verify_storage


DISABLED_PHASES = {"", "off", "none"}
MIGRATION_PHASES = {"backfill", "final", "rollback-check", "verify"}


def run_configured_migration() -> Dict[str, Any] | None:
    """Execute only the migration phase selected through governed environment."""
    phase = os.getenv("QSOU_MIGRATION_PHASE", "off").strip().lower()
    if phase in DISABLED_PHASES:
        return None
    if phase not in MIGRATION_PHASES:
        raise DataAssetError(f"不支持的启动迁移阶段: {phase}")

    if phase == "rollback-check":
        result = LegacySqliteMigrator(None).rollback_check()
    elif phase == "verify":
        if os.getenv("QSOU_CATALOG_BACKEND", "sqlite").strip().lower() != "postgres":
            raise DataAssetError("生产验收要求 QSOU_CATALOG_BACKEND=postgres")
        result = verify_storage(DataAssetStore())
    else:
        runtime_backend = os.getenv("QSOU_CATALOG_BACKEND", "sqlite").strip().lower()
        if phase == "final" and runtime_backend != "postgres":
            raise DataAssetError("最终迁移要求 QSOU_CATALOG_BACKEND=postgres")

        previous_backend = os.environ.get("QSOU_CATALOG_BACKEND")
        os.environ["QSOU_CATALOG_BACKEND"] = "postgres"
        try:
            result = LegacySqliteMigrator(DataAssetStore()).run(phase)
        finally:
            if previous_backend is None:
                os.environ.pop("QSOU_CATALOG_BACKEND", None)
            else:
                os.environ["QSOU_CATALOG_BACKEND"] = previous_backend

    print(
        "QSOU_DATABASE_MIGRATION_RESULT="
        + json.dumps(result, ensure_ascii=False, sort_keys=True),
        flush=True,
    )
    return result


def main() -> int:
    run_configured_migration()
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
