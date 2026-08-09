"""SQLite and PostgreSQL catalog connection compatibility layer."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


class CatalogConfigurationError(RuntimeError):
    """The requested catalog backend is not safely configured."""


_INSERT_IGNORE_RE = re.compile(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", re.IGNORECASE)
TEXT_NUL_REPLACEMENT = "\ufffd"


def normalize_catalog_value(value: Any) -> Any:
    """Return a stable catalog value accepted by SQLite and PostgreSQL."""
    if isinstance(value, str):
        return value.replace("\x00", TEXT_NUL_REPLACEMENT)
    if isinstance(value, Mapping):
        return {
            normalize_catalog_value(key): normalize_catalog_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_catalog_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_catalog_value(item) for item in value)
    return value


def _normalize_parameters(parameters: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(normalize_catalog_value(value) for value in parameters)


class SQLiteConnection:
    """Normalize catalog writes before SQLite can retain PostgreSQL-invalid text."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def execute(self, sql: str, parameters: Sequence[Any] = ()):
        return self.connection.execute(sql, _normalize_parameters(parameters))

    def executemany(self, sql: str, parameters):
        return self.connection.executemany(
            sql,
            (_normalize_parameters(row) for row in parameters),
        )

    def executescript(self, script: str) -> None:
        self.connection.executescript(script)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


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
        return self.connection.execute(
            _postgres_sql(sql),
            _normalize_parameters(parameters),
        )

    def executemany(self, sql: str, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(
            _postgres_sql(sql),
            (_normalize_parameters(row) for row in parameters),
        )
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
            sqlite_connection = sqlite3.connect(str(self.sqlite_path), timeout=30)
            sqlite_connection.row_factory = sqlite3.Row
            sqlite_connection.execute("PRAGMA foreign_keys = ON")
            sqlite_connection.execute("PRAGMA busy_timeout = 30000")
            connection = SQLiteConnection(sqlite_connection)
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
