"""SQLite WAL double-entry transaction manager & JournalEntry adapter (ADR-001, LLD-002)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from app.domain.exceptions import (
    ConflictProblem,
    FrozenAccountProblem,
    IdempotencyConflictProblem,
    NotFoundProblem,
    PolicyViolationProblem,
    ValidationProblem,
)
from app.domain.journal_entry import JournalEntry, JournalStatus, utc_now_iso
from app.domain.posting_line import PostingLine, PostingSide

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

CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    request_digest TEXT NOT NULL,
    description TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'EUR', 'GBP')),
    status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('POSTED', 'REVERSED')),
    reverses_journal_id TEXT UNIQUE,
    posted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posting_lines (
    id TEXT PRIMARY KEY,
    journal_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('DEBIT', 'CREDIT')),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'EUR', 'GBP')),
    balance_after_minor INTEGER NOT NULL,
    FOREIGN KEY (journal_id) REFERENCES journal_entries(id)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL,
    journal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (journal_id) REFERENCES journal_entries(id)
);

CREATE INDEX IF NOT EXISTS idx_posting_lines_journal ON posting_lines(journal_id);
CREATE INDEX IF NOT EXISTS idx_posting_lines_account ON posting_lines(account_id);
"""


class SqliteLedgerDatabase:
    """Thread-safe SQLite WAL handle coordinating double-entry atomic writes."""

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
        """Serialize SQLite writers cleanly via BEGIN IMMEDIATE."""
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

    def __enter__(self) -> "SqliteLedgerDatabase":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class SqliteJournalEntryRepository:
    """Transactional persistence adapter enforcing policy, status, and idempotency invariants."""

    def __init__(self, db: SqliteLedgerDatabase) -> None:
        self._db = db

    @staticmethod
    def _row_to_line(row: sqlite3.Row) -> PostingLine:
        return PostingLine(
            id=row["id"],
            journal_id=row["journal_id"],
            account_id=row["account_id"],
            side=PostingSide(row["side"]),
            amount_minor=int(row["amount_minor"]),
            currency=row["currency"],
            balance_after_minor=int(row["balance_after_minor"]),
        )

    def _fetch_entry_with_conn(self, conn: sqlite3.Connection, journal_id: str) -> Optional[JournalEntry]:
        row = conn.execute(
            """
            SELECT id, idempotency_key, request_digest, description, currency, status, reverses_journal_id, posted_at
            FROM journal_entries WHERE id = ?
            """,
            (journal_id,),
        ).fetchone()
        if not row:
            return None
        line_rows = conn.execute(
            """
            SELECT id, journal_id, account_id, side, amount_minor, currency, balance_after_minor
            FROM posting_lines WHERE journal_id = ? ORDER BY rowid ASC
            """,
            (journal_id,),
        ).fetchall()
        return JournalEntry(
            id=row["id"],
            idempotency_key=row["idempotency_key"],
            request_digest=row["request_digest"],
            description=row["description"],
            currency=row["currency"],
            status=JournalStatus(row["status"]),
            reverses_journal_id=row["reverses_journal_id"],
            lines=tuple(self._row_to_line(r) for r in line_rows),
            posted_at=row["posted_at"],
        )

    def _apply_lines_and_persist(
        self, conn: sqlite3.Connection, entry: JournalEntry, enforce_policy: bool = True
    ) -> JournalEntry:
        """Apply balance deltas under active BEGIN IMMEDIATE tx and insert immutable journal records."""
        acct_cache: Dict[str, sqlite3.Row] = {}
        running_balances: Dict[str, int] = {}
        final_lines: List[PostingLine] = []
        now = entry.posted_at

        for line in entry.lines:
            acct_row = acct_cache.get(line.account_id)
            if acct_row is None:
                acct_row = conn.execute(
                    """
                    SELECT a.id, a.code, a.normal_balance, a.currency, a.balance_minor, a.status,
                           p.name AS policy_name, p.allow_overdraft, p.max_posting_minor
                    FROM accounts a
                    JOIN ledger_policies p ON a.policy_id = p.id
                    WHERE a.id = ?
                    """,
                    (line.account_id,),
                ).fetchone()
                if acct_row is None:
                    raise NotFoundProblem(f"Referenced account '{line.account_id}' was not found.")
                acct_cache[line.account_id] = acct_row
                running_balances[line.account_id] = int(acct_row["balance_minor"])

            if acct_row["status"] != "ACTIVE":
                raise FrozenAccountProblem(
                    f"Account '{acct_row['code']}' has status {acct_row['status']}; cannot post transactions."
                )
            if acct_row["currency"] != line.currency:
                raise ValidationProblem(
                    f"Currency mismatch for account '{acct_row['code']}': "
                    f"expected {acct_row['currency']}, got {line.currency}."
                )

            if enforce_policy:
                max_posting = int(acct_row["max_posting_minor"])
                if line.amount_minor > max_posting:
                    raise PolicyViolationProblem(
                        f"Posting amount {line.amount_minor} exceeds policy '{acct_row['policy_name']}' "
                        f"limit of {max_posting}."
                    )

            delta = line.signed_delta(acct_row["normal_balance"])
            projected = running_balances[line.account_id] + delta
            if enforce_policy and not bool(acct_row["allow_overdraft"]) and projected < 0:
                raise PolicyViolationProblem(
                    f"Overdraft disallowed on account '{acct_row['code']}' (policy '{acct_row['policy_name']}')."
                )

            running_balances[line.account_id] = projected
            final_lines.append(replace(line, balance_after_minor=projected))

        for acct_id, new_bal in running_balances.items():
            conn.execute(
                "UPDATE accounts SET balance_minor = ?, updated_at = ? WHERE id = ?",
                (new_bal, now, acct_id),
            )

        conn.execute(
            """
            INSERT INTO journal_entries (
                id, idempotency_key, request_digest, description, currency, status, reverses_journal_id, posted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.idempotency_key,
                entry.request_digest,
                entry.description,
                entry.currency,
                entry.status.value,
                entry.reverses_journal_id,
                entry.posted_at,
            ),
        )
        for line in final_lines:
            conn.execute(
                """
                INSERT INTO posting_lines (id, journal_id, account_id, side, amount_minor, currency, balance_after_minor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    line.id,
                    line.journal_id,
                    line.account_id,
                    line.side.value,
                    line.amount_minor,
                    line.currency,
                    line.balance_after_minor,
                ),
            )
        conn.execute(
            """
            INSERT INTO idempotency_records (idempotency_key, request_digest, journal_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (entry.idempotency_key, entry.request_digest, entry.id, utc_now_iso()),
        )
        return replace(entry, lines=tuple(final_lines))

    def atomic_post_journal(self, entry: JournalEntry) -> Tuple[JournalEntry, bool]:
        with self._db.transaction() as conn:
            idem = conn.execute(
                "SELECT request_digest, journal_id FROM idempotency_records WHERE idempotency_key = ?",
                (entry.idempotency_key,),
            ).fetchone()
            if idem is not None:
                if idem["request_digest"] != entry.request_digest:
                    raise IdempotencyConflictProblem(
                        f"Idempotency key '{entry.idempotency_key}' was already used with a different payload."
                    )
                existing = self._fetch_entry_with_conn(conn, idem["journal_id"])
                if existing is None:
                    raise ConflictProblem(f"Corrupt idempotency record for key '{entry.idempotency_key}'.")
                return existing, True
            persisted = self._apply_lines_and_persist(conn, entry, enforce_policy=True)
            return persisted, False

    def atomic_reverse_journal(self, original_id: str, reversal_key: str, reason: str) -> Tuple[JournalEntry, bool]:
        clean_key = str(reversal_key or "").strip()
        if not clean_key:
            raise ValidationProblem("Reversal requires a non-empty idempotency_key.")
        with self._db.transaction() as conn:
            original = self._fetch_entry_with_conn(conn, original_id)
            if original is None:
                raise NotFoundProblem(f"JournalEntry '{original_id}' was not found.")

            clean_reason = str(reason or "").strip() or f"Reversal of {original.id}"
            idem = conn.execute(
                "SELECT request_digest, journal_id FROM idempotency_records WHERE idempotency_key = ?",
                (clean_key,),
            ).fetchone()
            if idem is not None:
                existing = self._fetch_entry_with_conn(conn, idem["journal_id"])
                if existing is not None and existing.reverses_journal_id == original.id:
                    return existing, True
                raise IdempotencyConflictProblem(
                    f"Reversal idempotency key '{clean_key}' conflicts with existing request."
                )

            cand = original.build_reversal(idempotency_key=clean_key, reason=clean_reason)
            persisted = self._apply_lines_and_persist(conn, cand, enforce_policy=False)
            conn.execute(
                "UPDATE journal_entries SET status = ? WHERE id = ?",
                (JournalStatus.REVERSED.value, original.id),
            )
            return persisted, False

    def get_by_id(self, journal_id: str) -> Optional[JournalEntry]:
        return self._fetch_entry_with_conn(self._db.connection, journal_id)

    def list_all(self) -> List[JournalEntry]:
        rows = self._db.connection.execute(
            "SELECT id FROM journal_entries ORDER BY posted_at ASC, rowid ASC"
        ).fetchall()
        entries: List[JournalEntry] = []
        for r in rows:
            item = self._fetch_entry_with_conn(self._db.connection, r["id"])
            if item is not None:
                entries.append(item)
        return entries
