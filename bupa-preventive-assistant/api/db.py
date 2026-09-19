"""Thin DB access layer supporting two dialects.

Primary target (spec §7): Postgres via psycopg 3 (Cloud SQL/AlloyDB).
Local convenience: SQLite, so the app can run with zero server setup — set
DATABASE_URL="sqlite:///path/to/bupa.db". The SQLite path translates the
Postgres placeholder style and auto-parses JSON/date columns so the rest of the
app is dialect-agnostic. This is a local dev/demo aid, NOT for production.

Every query returns plain dicts so FastAPI/Pydantic can serialise them directly.
"""
from __future__ import annotations

import datetime as _dt
import json
from contextlib import contextmanager
from typing import Any, Iterable

from config import DATABASE_URL

IS_SQLITE = DATABASE_URL.startswith("sqlite:")


def _sqlite_path() -> str:
    # sqlite:///C:/path/bupa.db  ->  C:/path/bupa.db
    return DATABASE_URL.split("sqlite:///", 1)[-1]


# =========================================================================
# SQLite dialect
# =========================================================================
if IS_SQLITE:
    import sqlite3

    # JSON columns come back as parsed Python objects (matches psycopg JSONB).
    sqlite3.register_converter("JSONB", lambda b: json.loads(b.decode()) if b else None)
    sqlite3.register_converter("DATE", lambda b: _dt.date.fromisoformat(b.decode()) if b else None)

    def _ts(b: bytes):
        s = b.decode()
        try:
            return _dt.datetime.fromisoformat(s)
        except ValueError:
            return s
    sqlite3.register_converter("TIMESTAMP", _ts)

    def _dict_factory(cursor, row):
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def _adapt(params):
        """SQLite needs %s -> ? and date/datetime params as ISO strings."""
        out = []
        for p in params or ():
            if isinstance(p, (_dt.date, _dt.datetime)):
                out.append(p.isoformat())
            else:
                out.append(p)
        return out

    @contextmanager
    def get_conn():
        conn = sqlite3.connect(_sqlite_path(), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = _dict_factory
        try:
            yield conn
        finally:
            conn.close()

    def _translate(sql: str) -> str:
        return sql.replace("%s", "?")

    def query(sql: str, params: Iterable[Any] | None = None) -> list[dict]:
        with get_conn() as conn:
            cur = conn.execute(_translate(sql), _adapt(params))
            return cur.fetchall()

    def query_one(sql: str, params: Iterable[Any] | None = None) -> dict | None:
        rows = query(sql, params)
        return rows[0] if rows else None

    def execute(sql: str, params: Iterable[Any] | None = None) -> dict | None:
        with get_conn() as conn:
            cur = conn.execute(_translate(sql), _adapt(params))
            row = cur.fetchone() if cur.description is not None else None
            conn.commit()
            return row

    def jsonb(value: Any) -> str:
        return json.dumps(value)


# =========================================================================
# Postgres dialect (psycopg 3) — the production target
# =========================================================================
else:
    import psycopg
    from psycopg.rows import dict_row

    @contextmanager
    def get_conn():
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Point it at Cloud SQL/AlloyDB (or a local "
                "postgres), or use sqlite:///./bupa.db for a zero-setup local run."
            )
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            yield conn

    def query(sql: str, params: Iterable[Any] | None = None) -> list[dict]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def query_one(sql: str, params: Iterable[Any] | None = None) -> dict | None:
        rows = query(sql, params)
        return rows[0] if rows else None

    def execute(sql: str, params: Iterable[Any] | None = None) -> dict | None:
        """Run an INSERT/UPDATE. Add `RETURNING ...` to get a row back."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = None
            if cur.description is not None:
                row = cur.fetchone()
            conn.commit()
            return row

    def jsonb(value: Any) -> str:
        """Serialise a Python object for a JSONB column parameter."""
        return json.dumps(value)
