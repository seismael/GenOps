"""SQLite WAL connection manager and LedgerPolicy persistence adapter (ADR-001, LLD-001)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from app.domain.exceptions import ConflictProblem
from app.domain.ledger_policy import LedgerPolicy

_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ledger_policies (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    allow_overdraft INTEGER NOT NULL DEFAULT 0 CHECK (allow_overdraft IN (0, 1)),
    max_posting_minor INTEGER NOT NULL CHECK (max_posting_minor > 0),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL CHECK (account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')),
    normal_balance TEXT NOT NULL CHECK (normal_balance IN ('DEBIT', 'CREDIT')),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'EUR', 'GBP')),
    balance_minor INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
    policy_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES ledger_policies(id)
);

CREATE INDEX IF NOT EXISTS idx_accounts_code ON accounts(code);
CREATE INDEX IF NOT EXISTS idx_accounts_currency_status ON accounts(currency, status);
"""


class SqliteAccountsDatabase:
    """Thread-safe SQLite WAL database handle managing transactions and cleanup."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 5000;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.executescript(_SCHEMA_SQL)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Acquire RLock and serialize writes with BEGIN IMMEDIATE."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE;")
            try:
                yield self._conn
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def close(self) -> None:
        with self._lock:
            if getattr(self, "_conn", None) is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> "SqliteAccountsDatabase":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class SqliteLedgerPolicyRepository:
    """Parameterized SQLite repository implementing LedgerPolicyRepositoryPort."""

    def __init__(self, db: SqliteAccountsDatabase) -> None:
        self._db = db

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> LedgerPolicy:
        return LedgerPolicy(
            id=row["id"],
            name=row["name"],
            allow_overdraft=bool(row["allow_overdraft"]),
            max_posting_minor=int(row["max_posting_minor"]),
            description=row["description"],
            created_at=row["created_at"],
        )

    def create(self, policy: LedgerPolicy) -> LedgerPolicy:
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO ledger_policies (id, name, allow_overdraft, max_posting_minor, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        policy.id,
                        policy.name,
                        1 if policy.allow_overdraft else 0,
                        policy.max_posting_minor,
                        policy.description,
                        policy.created_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictProblem(f"LedgerPolicy '{policy.name}' or id '{policy.id}' already exists.") from exc
        return policy

    def get_by_id(self, policy_id: str) -> Optional[LedgerPolicy]:
        row = self._db.connection.execute(
            "SELECT id, name, allow_overdraft, max_posting_minor, description, created_at FROM ledger_policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def get_by_name(self, name: str) -> Optional[LedgerPolicy]:
        row = self._db.connection.execute(
            "SELECT id, name, allow_overdraft, max_posting_minor, description, created_at FROM ledger_policies WHERE name = ?",
            (name,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def list_all(self) -> List[LedgerPolicy]:
        rows = self._db.connection.execute(
            "SELECT id, name, allow_overdraft, max_posting_minor, description, created_at FROM ledger_policies ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [self._row_to_entity(r) for r in rows]
