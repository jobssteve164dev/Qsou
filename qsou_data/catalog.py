"""SQLite and PostgreSQL catalog connection compatibility layer."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence


class CatalogConfigurationError(RuntimeError):
    """The requested catalog backend is not safely configured."""


_INSERT_IGNORE_RE = re.compile(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", re.IGNORECASE)


class PostgresConnection:
    """Expose the small sqlite-style surface used by DataAssetStore."""

    def __init__(self, connection) -> None:
        self.connection = connection

    def execute(self, sql: str, parameters: Sequence[Any] = ()):
        normalized = sql.strip().upper()
        if normalized == "BEGIN IMMEDIATE":
            return self.connection.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (781_937_611,),
            )
        return self.connection.execute(_postgres_sql(sql), tuple(parameters))

    def executemany(self, sql: str, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(_postgres_sql(sql), parameters)
        return cursor

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def _postgres_sql(sql: str) -> str:
    translated = _INSERT_IGNORE_RE.sub("INSERT INTO", sql)
    ignored_insert = translated != sql
    translated = translated.replace("?", "%s").strip()
    if ignored_insert and "ON CONFLICT" not in translated.upper():
        translated += " ON CONFLICT DO NOTHING"
    return translated


class Catalog:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.sqlite_path = self.root / "catalog.sqlite3"
        self.backend = os.getenv("QSOU_CATALOG_BACKEND", "sqlite").strip().lower()
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        if self.backend not in {"sqlite", "postgres"}:
            raise CatalogConfigurationError(f"不支持的目录库后端: {self.backend}")
        if self.backend == "postgres" and not self.database_url:
            raise CatalogConfigurationError("PostgreSQL 目录库缺少 DATABASE_URL")

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.backend == "sqlite":
            connection = sqlite3.connect(str(self.sqlite_path), timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 30000")
        else:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise CatalogConfigurationError("PostgreSQL 目录库需要 psycopg") from exc
            connection = PostgresConnection(
                psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=15)
            )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @property
    def label(self) -> str:
        return str(self.sqlite_path) if self.backend == "sqlite" else "postgresql"
