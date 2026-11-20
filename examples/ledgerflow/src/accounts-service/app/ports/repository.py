"""Hexagonal ports and CNCF CloudEvents v1.0.2 event contract for accounts-service (ADR-002)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from app.domain.account import Account, AccountStatus
from app.domain.ledger_policy import LedgerPolicy

logger = logging.getLogger("ledgerflow.accounts.events")


def new_traceparent() -> str:
    """Generate a W3C Trace Context version-00 traceparent string."""
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


class LedgerPolicyRepositoryPort(Protocol):
    def create(self, policy: LedgerPolicy) -> LedgerPolicy: ...
    def get_by_id(self, policy_id: str) -> Optional[LedgerPolicy]: ...
    def get_by_name(self, name: str) -> Optional[LedgerPolicy]: ...
    def list_all(self) -> List[LedgerPolicy]: ...


class AccountRepositoryPort(Protocol):
    def create(self, account: Account) -> Account: ...
    def get_by_id(self, account_id: str) -> Optional[Account]: ...
    def get_by_code(self, code: str) -> Optional[Account]: ...
    def list_all(self, currency: Optional[str] = None) -> List[Account]: ...
    def update_status(self, account_id: str, new_status: AccountStatus, updated_at: str) -> Optional[Account]: ...


class EventPublisherPort(Protocol):
    def publish(self, event: Dict[str, Any]) -> None: ...


class InMemoryEventPublisher:
    """Zero-dependency CloudEvents collector for local execution and deterministic testing."""

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
