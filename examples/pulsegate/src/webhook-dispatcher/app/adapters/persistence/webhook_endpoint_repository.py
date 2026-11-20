"""SQLite WAL repository for WebhookEndpoint and DeliveryAttempt (ADR-001, LLD-002)."""

from __future__ import annotations

import sqlite3
from typing import Optional

from app.domain.delivery_attempt import DeliveryAttempt
from app.domain.webhook_endpoint import WebhookEndpoint

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS webhook_endpoints (
    endpoint_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS delivery_attempts (
    attempt_id TEXT PRIMARY KEY,
    endpoint_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    FOREIGN KEY (endpoint_id) REFERENCES webhook_endpoints(endpoint_id)
);
"""


class SqliteWebhookStore:
    """Atomic SQLite WAL store for webhook endpoints and delivery attempts."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)

    def register_endpoint(self, ep: WebhookEndpoint) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO webhook_endpoints (endpoint_id, url, secret, active) VALUES (?, ?, ?, ?)",
            (ep.endpoint_id, ep.url, ep.secret, 1 if ep.active else 0),
        )

    def save_attempt(self, attempt: DeliveryAttempt) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO delivery_attempts (attempt_id, endpoint_id, event_id, status, attempt_count, max_attempts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (attempt.attempt_id, attempt.endpoint_id, attempt.event_id, attempt.status, attempt.attempt_count, attempt.max_attempts),
        )

    def get_attempt(self, attempt_id: str) -> Optional[DeliveryAttempt]:
        row = self._conn.execute(
            "SELECT attempt_id, endpoint_id, event_id, status, attempt_count, max_attempts "
            "FROM delivery_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            return None
        return DeliveryAttempt(*row)

    def close(self) -> None:
        self._conn.close()
