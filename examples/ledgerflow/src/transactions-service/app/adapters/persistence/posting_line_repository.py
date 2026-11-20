"""SQLite read projection adapter implementing PostingLineRepositoryPort (LLD-002)."""

from __future__ import annotations

from typing import List

from app.adapters.persistence.journal_entry_repository import SqliteJournalEntryRepository, SqliteLedgerDatabase
from app.domain.posting_line import PostingLine


class SqlitePostingLineRepository:
    """Parameterized SQLite queries over immutable posting_lines."""

    def __init__(self, db: SqliteLedgerDatabase) -> None:
        self._db = db

    def list_by_journal(self, journal_id: str) -> List[PostingLine]:
        rows = self._db.connection.execute(
            """
            SELECT id, journal_id, account_id, side, amount_minor, currency, balance_after_minor
            FROM posting_lines WHERE journal_id = ? ORDER BY rowid ASC
            """,
            (journal_id,),
        ).fetchall()
        return [SqliteJournalEntryRepository._row_to_line(r) for r in rows]

    def list_by_account(self, account_id: str) -> List[PostingLine]:
        rows = self._db.connection.execute(
            """
            SELECT id, journal_id, account_id, side, amount_minor, currency, balance_after_minor
            FROM posting_lines WHERE account_id = ? ORDER BY rowid ASC
            """,
            (account_id,),
        ).fetchall()
        return [SqliteJournalEntryRepository._row_to_line(r) for r in rows]
