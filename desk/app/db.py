"""Minimal Postgres helpers. Each role uses its own DATABASE_URL / database."""

from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("desk.db")


SCHEMA_SUPPLIER = """
CREATE TABLE IF NOT EXISTS contract_accounts (
    buyer_did TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quote_log (
    quote_id TEXT PRIMARY KEY,
    buyer_did TEXT NOT NULL,
    kind TEXT NOT NULL,
    body JSONB NOT NULL,
    quote_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_log (
    order_id TEXT PRIMARY KEY,
    buyer_did TEXT NOT NULL,
    quote_hash TEXT NOT NULL,
    accepted BOOLEAN NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SCHEMA_BUYER = """
CREATE TABLE IF NOT EXISTS session_audit (
    session_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    body JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SCHEMA_MARKET = """
CREATE TABLE IF NOT EXISTS registration (
    did TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    public_url TEXT NOT NULL,
    description_url TEXT NOT NULL,
    offers JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row)


def init_schema(database_url: str, role: str) -> None:
    if role in {"s1", "s2", "s3"}:
        ddl = SCHEMA_SUPPLIER
    elif role == "buyer":
        ddl = SCHEMA_BUYER
    elif role == "market":
        ddl = SCHEMA_MARKET
    else:
        return
    try:
        with connect(database_url) as conn:
            conn.execute(ddl)
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("db init skipped: %s", type(exc).__name__)


def exec_sql(database_url: str, sql: str, params: tuple[Any, ...] | None = None) -> None:
    try:
        with connect(database_url) as conn:
            conn.execute(sql, params or ())
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("db write skipped: %s", type(exc).__name__)


def fetch_all(database_url: str, sql: str, params: tuple[Any, ...] | None = None) -> list[dict]:
    try:
        with connect(database_url) as conn:
            cur = conn.execute(sql, params or ())
            return list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        logger.warning("db read skipped: %s", type(exc).__name__)
        return []
