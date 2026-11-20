"""
Secondary Adapter: SQLite persistence implementation using standard library sqlite3.
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import hmac
import logging
import sqlite3
import threading
from typing import Any, Dict, Iterator, Optional

from app.domain.api_key import ApiKey
from app.domain.click_event import ClickEvent
from app.domain.short_url import ShortUrl
from app.ports.repository import IAnalyticsRepository, IApiKeyRepository, IUrlRepository

logger = logging.getLogger("krypton.persistence")


class SqliteDatabase:
    """Manages SQLite connection, WAL mode, thread safety, and schema migrations."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            # Shared in-memory connection is reused across FastAPI threadpool threads
            # (container is lru_cached); all operations synchronize on self._lock.
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextlib.contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Thread-safe connection context manager protecting shared :memory: connections."""
        if self._shared_conn is not None:
            with self._lock:
                yield self._shared_conn
        else:
            conn = self.get_connection()
            try:
                yield conn
            finally:
                conn.close()

    def close(self) -> None:
        """Close the shared in-memory connection if open."""
        if self._shared_conn is not None:
            with self._lock:
                self._shared_conn.close()
                self._shared_conn = None

    def _init_db(self) -> None:
        with self.connection() as conn:
            conn.executescript("""
        CREATE TABLE IF NOT EXISTS urls (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            target_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            click_count INTEGER DEFAULT 0 NOT NULL,
            is_active INTEGER DEFAULT 1 NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_urls_code ON urls(code);
        CREATE INDEX IF NOT EXISTS idx_urls_created_at ON urls(created_at);

        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT PRIMARY KEY,
            url_id TEXT NOT NULL,
            code TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            referrer TEXT,
            FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
        CREATE INDEX IF NOT EXISTS idx_clicks_timestamp ON clicks(timestamp);

        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            is_revoked INTEGER DEFAULT 0 NOT NULL
        );
        """)
            conn.commit()
        logger.debug("Initialized SQLite schema at %s", self.db_path)


class SqliteUrlRepository(IUrlRepository):
    """SQLite implementation of IUrlRepository."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def save(self, url: ShortUrl) -> None:
        with self.db.connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO urls (id, code, target_url, created_at, click_count, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        click_count = excluded.click_count,
                        is_active = excluded.is_active;
                    """,
                    (url.id, url.code, url.target_url, url.created_at.isoformat(), url.click_count, int(url.is_active)),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValueError(f"Short code '{url.code}' is already taken.") from exc

    def get_by_code(self, code: str) -> Optional[ShortUrl]:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
            if not row:
                return None
            return ShortUrl(
                id=row["id"],
                code=row["code"],
                target_url=row["target_url"],
                created_at=datetime.datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
                click_count=row["click_count"],
                is_active=bool(row["is_active"]),
            )

    def increment_clicks(self, code: str) -> None:
        with self.db.connection() as conn:
            conn.execute("UPDATE urls SET click_count = click_count + 1 WHERE code = ?", (code,))
            conn.commit()


class SqliteAnalyticsRepository(IAnalyticsRepository):
    """SQLite implementation of IAnalyticsRepository."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def record_click(self, event: ClickEvent) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO clicks (id, url_id, code, timestamp, ip_address, user_agent, referrer)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event.id, event.url_id, event.code, event.timestamp.isoformat(), event.ip_address, event.user_agent, event.referrer),
            )
            conn.commit()

    def get_analytics(self, code: str) -> Dict[str, Any]:
        with self.db.connection() as conn:
            count_row = conn.execute("SELECT COUNT(*) as total FROM clicks WHERE code = ?", (code,)).fetchone()
            total_clicks = count_row["total"] if count_row else 0

            ref_rows = conn.execute(
                "SELECT referrer, COUNT(*) as ref_count FROM clicks WHERE code = ? AND referrer != '' GROUP BY referrer ORDER BY ref_count DESC LIMIT 5",
                (code,),
            ).fetchall()
            recent_referrers = [f"{r['referrer']} ({r['ref_count']})" for r in ref_rows]

            return {
                "total_clicks": total_clicks,
                "recent_referrers": recent_referrers,
            }


class SqliteApiKeyRepository(IApiKeyRepository):
    """SQLite implementation of IApiKeyRepository."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def save(self, api_key: ApiKey) -> None:
        with self.db.connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO api_keys (key_id, key_hash, owner_email, created_at, is_revoked)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (api_key.key_id, api_key.key_hash, api_key.owner_email, api_key.created_at.isoformat(), int(api_key.is_revoked)),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValueError(f"API key '{api_key.key_id}' already exists.") from exc

    def get_by_id(self, key_id: str) -> Optional[ApiKey]:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
            if not row:
                return None
            created_at = (
                datetime.datetime.fromisoformat(row["created_at"])
                if isinstance(row["created_at"], str)
                else row["created_at"]
            )
            return ApiKey(
                key_id=row["key_id"],
                key_hash=row["key_hash"],
                owner_email=row["owner_email"],
                created_at=created_at,
                is_revoked=bool(row["is_revoked"]),
            )

    def verify_token(self, token: str) -> bool:
        if not token:
            return False
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        key_id = f"key_{token_hash[:12]}"
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT key_hash, is_revoked FROM api_keys WHERE key_id = ? AND is_revoked = 0",
                (key_id,),
            ).fetchone()
            if row is None:
                return False
            return hmac.compare_digest(str(row["key_hash"]), token_hash)
