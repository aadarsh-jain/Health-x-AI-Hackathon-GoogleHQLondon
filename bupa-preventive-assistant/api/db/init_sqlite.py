"""Build a local SQLite database from the canonical Postgres schema.sql + seed.sql.

Local dev/demo convenience only (spec targets Cloud SQL/AlloyDB). Keeps a single
source of truth: it translates the Postgres DDL/seed on the fly rather than
maintaining a parallel SQLite file.

Usage:
    python db/init_sqlite.py [path/to/bupa.db]     # default: ./bupa.db
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def translate_schema(sql: str) -> str:
    sql = re.sub(r"CREATE EXTENSION[^;]*;", "", sql, flags=re.IGNORECASE)
    sql = sql.replace("gen_random_uuid()", "(lower(hex(randomblob(16))))")
    sql = re.sub(r"DEFAULT now\(\)", "DEFAULT CURRENT_TIMESTAMP", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bUUID\b", "TEXT", sql)  # UUID type -> TEXT (defaults already handled)
    return sql


def translate_seed(sql: str) -> str:
    # Drop the Postgres-only TRUNCATE … RESTART IDENTITY CASCADE; (fresh DB anyway).
    sql = re.sub(r"TRUNCATE[\s\S]*?;", "", sql, count=1, flags=re.IGNORECASE)
    return sql


def build(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        schema = translate_schema(f.read())
    with open(os.path.join(HERE, "seed.sql"), encoding="utf-8") as f:
        seed = translate_seed(f.read())

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.executescript(seed)
        conn.commit()
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("users", "preventive_services", "recommendations",
                            "clinical_signals", "notifications")}
    finally:
        conn.close()
    print(f"Built SQLite DB at {db_path}")
    print("  row counts:", counts)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "bupa.db")
    build(target)
