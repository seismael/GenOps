"""Read/query service for PostingLine projections."""

from __future__ import annotations

from typing import List

from app.domain.posting_line import PostingLine
from app.ports.repository import PostingLineRepositoryPort


class PostingLineService:
    """Provides immutable account and journal posting line history."""

    def __init__(self, line_repo: PostingLineRepositoryPort) -> None:
        self._line_repo = line_repo

    def list_by_journal(self, journal_id: str) -> List[PostingLine]:
        return self._line_repo.list_by_journal(journal_id)

    def list_by_account(self, account_id: str) -> List[PostingLine]:
        return self._line_repo.list_by_account(account_id)
