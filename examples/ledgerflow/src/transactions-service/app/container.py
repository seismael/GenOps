"""Dependency-injection container wiring transactions-service ports and adapters."""

from __future__ import annotations

from pathlib import Path

from app.adapters.persistence.journal_entry_repository import (
    SqliteJournalEntryRepository,
    SqliteLedgerDatabase,
)
from app.adapters.persistence.posting_line_repository import SqlitePostingLineRepository
from app.ports.repository import InMemoryEventPublisher
from app.services.journal_entry_service import JournalEntryService
from app.services.posting_line_service import PostingLineService


class TransactionsContainer:
    """Explicit composition root owning database handles and service instances."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db = SqliteLedgerDatabase(db_path)
        self.publisher = InMemoryEventPublisher()
        self.journal_repo = SqliteJournalEntryRepository(self.db)
        self.line_repo = SqlitePostingLineRepository(self.db)
        self.journal_service = JournalEntryService(self.journal_repo, self.publisher)
        self.line_service = PostingLineService(self.line_repo)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "TransactionsContainer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
