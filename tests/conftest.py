import os

import pytest


@pytest.fixture(autouse=True)
def isolate_postgres_test_state():
    database_url = os.getenv("QSOU_TEST_DATABASE_URL", "").strip()
    if database_url:
        if os.getenv("QSOU_TEST_DATABASE_RESET") != "confirmed":
            raise RuntimeError(
                "QSOU_TEST_DATABASE_RESET=confirmed is required before resetting test data"
            )
        import psycopg
        from psycopg import sql

        with psycopg.connect(database_url, autocommit=True) as connection:
            if connection.info.dbname != "qsou_test":
                raise RuntimeError(
                    f"refusing to reset non-test database: {connection.info.dbname}"
                )
            rows = connection.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = 'public' AND tablename <> 'alembic_version'
                ORDER BY tablename
                """
            ).fetchall()
            if rows:
                tables = sql.SQL(", ").join(sql.Identifier(row[0]) for row in rows)
                connection.execute(
                    sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(tables)
                )
    yield
