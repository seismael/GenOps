"""Hexagonal ports and CNCF CloudEvents v1.0.2 event contract for transactions-service (ADR-002)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from app.domain.journal_entry import JournalEntry
from app.domain.posting_line import PostingLine

logger = logging.getLogger("ledgerflow.transactions.events")


def new_traceparent() -> str:
    """Generate a W3C Trace Context version-00 traceparent header."""
    return f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"


def build_cloudevent(
    source: str,
    event_type: str,
    subject: str,
    data: Dict[str, Any],
    traceparent: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical CNCF CloudEvents v1.0.2 envelope with W3C traceparent."""
    return {
        "specversion": "1.0",
        "id": f"evt_{uuid.uuid4().hex[:24]}",
        "source": source,
        "type": event_type,
        "datacontenttype": "application/json",
        "subject": subject,
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "traceparent": traceparent or new_traceparent(),
        "data": data,
    }


class JournalEntryRepositoryPort(Protocol):
    def atomic_post_journal(self, entry: JournalEntry) -> Tuple[JournalEntry, bool]: ...
    def atomic_reverse_journal(self, original_id: str, reversal_key: str, reason: str) -> Tuple[JournalEntry, bool]: ...
    def get_by_id(self, journal_id: str) -> Optional[JournalEntry]: ...
    def list_all(self) -> List[JournalEntry]: ...


class PostingLineRepositoryPort(Protocol):
    def list_by_journal(self, journal_id: str) -> List[PostingLine]: ...
    def list_by_account(self, account_id: str) -> List[PostingLine]: ...


class EventPublisherPort(Protocol):
    def publish(self, event: Dict[str, Any]) -> None: ...


class InMemoryEventPublisher:
    """Zero-dependency CloudEvents collector for tests and offline diagnostics."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def publish(self, event: Dict[str, Any]) -> None:
        self.events.append(event)
        logger.info(
            "Published CloudEvent type=%s subject=%s id=%s",
            event.get("type"),
            event.get("subject"),
            event.get("id"),
        )
