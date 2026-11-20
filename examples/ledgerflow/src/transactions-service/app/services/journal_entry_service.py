"""Application service orchestrating atomic double-entry posting and reversals (US-002-01..03)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.domain.exceptions import NotFoundProblem
from app.domain.journal_entry import JournalEntry
from app.ports.repository import EventPublisherPort, JournalEntryRepositoryPort, build_cloudevent

logger = logging.getLogger("ledgerflow.transactions.journal_service")


class JournalEntryService:
    """Use-case coordinator for idempotent postings and immutable journal reversals."""

    def __init__(self, journal_repo: JournalEntryRepositoryPort, publisher: EventPublisherPort) -> None:
        self._journal_repo = journal_repo
        self._publisher = publisher

    def post_journal(
        self,
        idempotency_key: str,
        description: str,
        currency: str,
        lines: List[Dict[str, Any]],
        traceparent: Optional[str] = None,
    ) -> Tuple[JournalEntry, bool]:
        entry = JournalEntry.create(
            idempotency_key=idempotency_key,
            description=description,
            currency=currency,
            line_specs=lines,
        )
        persisted, is_replay = self._journal_repo.atomic_post_journal(entry)
        if not is_replay:
            event = build_cloudevent(
                source="/ledgerflow/transactions-service",
                event_type="com.ledgerflow.journal.posted",
                subject=persisted.id,
                data={
                    "journal_id": persisted.id,
                    "idempotency_key": persisted.idempotency_key,
                    "currency": persisted.currency,
                    "total_amount_minor": persisted.total_amount_minor,
                    "line_count": len(persisted.lines),
                    "status": persisted.status.value,
                },
                traceparent=traceparent,
            )
            self._publisher.publish(event)
            logger.info("Posted journal id=%s key=%s amount=%d", persisted.id, persisted.idempotency_key, persisted.total_amount_minor)
        return persisted, is_replay

    def reverse_journal(
        self,
        journal_id: str,
        idempotency_key: str,
        reason: str = "",
        traceparent: Optional[str] = None,
    ) -> Tuple[JournalEntry, bool]:
        reversal, is_replay = self._journal_repo.atomic_reverse_journal(journal_id, idempotency_key, reason)
        if not is_replay:
            event = build_cloudevent(
                source="/ledgerflow/transactions-service",
                event_type="com.ledgerflow.journal.reversed",
                subject=reversal.id,
                data={
                    "journal_id": reversal.id,
                    "reverses_journal_id": reversal.reverses_journal_id,
                    "idempotency_key": reversal.idempotency_key,
                    "currency": reversal.currency,
                    "total_amount_minor": reversal.total_amount_minor,
                    "status": reversal.status.value,
                },
                traceparent=traceparent,
            )
            self._publisher.publish(event)
            logger.info("Reversed journal orig=%s reversal=%s", journal_id, reversal.id)
        return reversal, is_replay

    def get_journal(self, journal_id: str) -> JournalEntry:
        entry = self._journal_repo.get_by_id(journal_id)
        if entry is None:
            raise NotFoundProblem(
                f"JournalEntry '{journal_id}' was not found.",
                instance=f"/api/v1/journals/{journal_id}",
            )
        return entry

    def list_journals(self) -> List[JournalEntry]:
        return self._journal_repo.list_all()
