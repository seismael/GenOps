"""SQLite WAL repository for RatePolicy and QuotaBucket (ADR-001, LLD-001)."""

from __future__ import annotations

import sqlite3
from typing import Tuple

from app.domain.quota_bucket import QuotaBucket
from app.domain.rate_policy import RatePolicy

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rate_policies (
    tenant_id TEXT PRIMARY KEY,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    refill_per_sec REAL NOT NULL CHECK (refill_per_sec > 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_buckets (
    tenant_id TEXT PRIMARY KEY,
    tokens REAL NOT NULL,
    last_refill_ms INTEGER NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES rate_policies(tenant_id)
);
"""


class SqliteRateLimitStore:
    """Atomic SQLite WAL store using BEGIN IMMEDIATE transactions."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)

    def upsert_policy(self, policy: RatePolicy, now_ms: int = 0) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO rate_policies (tenant_id, capacity, refill_per_sec, created_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(tenant_id) DO UPDATE SET capacity=excluded.capacity, refill_per_sec=excluded.refill_per_sec",
                (policy.tenant_id, policy.capacity, policy.refill_per_sec, policy.created_at),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO quota_buckets (tenant_id, tokens, last_refill_ms) VALUES (?, ?, ?)",
                (policy.tenant_id, float(policy.capacity), now_ms),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def acquire(self, tenant_id: str, now_ms: int, cost: int = 1) -> Tuple[bool, int, int]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT p.capacity, p.refill_per_sec, b.tokens, b.last_refill_ms "
                "FROM rate_policies p JOIN quota_buckets b ON p.tenant_id = b.tenant_id "
                "WHERE p.tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown tenant_id '{tenant_id}'")
            cap, refill, tokens, last_ms = int(row[0]), float(row[1]), float(row[2]), int(row[3])
            bucket = QuotaBucket(tenant_id=tenant_id, tokens=tokens, last_refill_ms=last_ms)
            allowed, remaining, retry_ms = bucket.consume(now_ms, cap, refill, cost=cost)
            self._conn.execute(
                "UPDATE quota_buckets SET tokens = ?, last_refill_ms = ? WHERE tenant_id = ?",
                (bucket.tokens, bucket.last_refill_ms, tenant_id),
            )
            self._conn.execute("COMMIT")
            return allowed, remaining, retry_ms
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self._conn.close()
