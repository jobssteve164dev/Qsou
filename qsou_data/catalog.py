"""PostgreSQL catalog access through SQLAlchemy transactions."""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import CursorResult, Engine, make_url


class CatalogConfigurationError(RuntimeError):
    """The PostgreSQL catalog is not safely configured."""


TEXT_NUL_REPLACEMENT = "\ufffd"


def normalize_catalog_value(value: Any) -> Any:
    """Return a stable value accepted by PostgreSQL text columns."""
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


class Result:
    """Expose mapping rows while preserving DB-API row-count semantics."""

    def __init__(self, result: CursorResult[Any]) -> None:
        self._result = result
        self._rows = result.mappings() if result.returns_rows else None

    @property
    def rowcount(self) -> int:
        return self._result.rowcount

    def fetchone(self):
        return self._rows.fetchone() if self._rows is not None else None

    def fetchall(self):
        return self._rows.fetchall() if self._rows is not None else []

    def fetchmany(self, size: int | None = None):
        if self._rows is None:
            return []
        return self._rows.fetchmany(size) if size is not None else self._rows.fetchmany()


class EmptyResult:
    rowcount = 0

    @staticmethod
    def fetchone():
        return None

    @staticmethod
    def fetchall():
        return []

    @staticmethod
    def fetchmany(_size: int | None = None):
        return []


class PostgresConnection:
    """Small PostgreSQL-native surface used by the data asset repository."""

    def __init__(self, connection) -> None:
        self.connection = connection

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Result:
        if parameters:
            result = self.connection.exec_driver_sql(
                sql,
                _normalize_parameters(parameters),
            )
        else:
            result = self.connection.exec_driver_sql(sql)
        return Result(result)

    def executemany(self, sql: str, parameters) -> Result | EmptyResult:
        rows = [_normalize_parameters(row) for row in parameters]
        if not rows:
            return EmptyResult()
        return Result(self.connection.exec_driver_sql(sql, rows))


def _postgres_url(database_url: str) -> str:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise CatalogConfigurationError("PostgreSQL DATABASE_URL 格式无效") from exc
    if url.get_backend_name() != "postgresql":
        raise CatalogConfigurationError("QSou 目录库只支持 PostgreSQL")
    return url.set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


@lru_cache(maxsize=4)
def _engine_for(database_url: str) -> Engine:
    return create_engine(
        _postgres_url(database_url),
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
    )


class Catalog:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.backend = "postgres"
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        if not self.database_url:
            raise CatalogConfigurationError("PostgreSQL 目录库缺少 DATABASE_URL")
        self.engine = _engine_for(self.database_url)

    @contextmanager
    def connection(self) -> Iterator[PostgresConnection]:
        with self.engine.begin() as connection:
            yield PostgresConnection(connection)

    @property
    def label(self) -> str:
        return "postgresql"
