"""Read-only SQLite access for the API."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class DatabaseUnavailable(RuntimeError):
    pass


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    if not db_path.is_file():
        raise DatabaseUnavailable(
            f"Database not found at {db_path}. Build it with: python3 -m pipeline.build_db --source mock")
    # mode=ro: the API can never modify analytical results.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params)]


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM run_metadata")}
