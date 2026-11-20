"""JournalEntry aggregate root enforcing zero-sum invariants, digests, and reversals (LLD-002)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.domain.exceptions import (
    ConflictProblem,
    UnbalancedJournalProblem,
    ValidationProblem,
)
from app.domain.posting_line import PostingLine, PostingSide


class JournalStatus(str, Enum):
    POSTED = "POSTED"
    REVERSED = "REVERSED"


def utc_now_iso() -> str:
    """Return canonical UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_request_digest(
    description: str,
    currency: str,
    lines: Iterable[Dict[str, Any]],
) -> str:
    """Compute canonical SHA-256 digest of a posting payload for idempotency checks."""
    normalized_lines = [
        {
            "account_id": str(item.get("account_id", "")).strip(),
            "side": str(item.get("side", "")).strip().upper(),
            "amount_minor": item.get("amount_minor"),
        }
        for item in lines
    ]
    payload = {
        "description": str(description or "").strip(),
        "currency": str(currency or "").strip().upper(),
        "lines": normalized_lines,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class JournalEntry:
    """Immutable double-entry journal header and balanced posting legs."""

    id: str
    idempotency_key: str
    request_digest: str
    description: str
    currency: str
    status: JournalStatus
    reverses_journal_id: Optional[str]
    lines: Tuple[PostingLine, ...]
    posted_at: str

    @property
    def total_amount_minor(self) -> int:
        return sum(line.amount_minor for line in self.lines if line.side == PostingSide.DEBIT)

    @classmethod
    def create(
        cls,
        idempotency_key: str,
        description: str,
        currency: str,
        line_specs: List[Dict[str, Any]],
        reverses_journal_id: Optional[str] = None,
        journal_id: Optional[str] = None,
        request_digest: Optional[str] = None,
    ) -> "JournalEntry":
        clean_key = str(idempotency_key or "").strip()
        if not clean_key or len(clean_key) > 128:
            raise ValidationProblem("idempotency_key must be between 1 and 128 characters.")
        clean_desc = str(description or "").strip()
        if not clean_desc:
            raise ValidationProblem("Journal description cannot be empty.")
        if not line_specs or len(line_specs) < 2:
            raise ValidationProblem("Double-entry JournalEntry requires at least 2 posting lines.")

        jid = journal_id or f"jrnl_{uuid.uuid4().hex[:20]}"
        norm_cur = str(currency or "").strip().upper()
        built_lines = tuple(
            PostingLine.create(
                journal_id=jid,
                account_id=str(spec.get("account_id", "")),
                side=spec.get("side", ""),
                amount_minor=spec.get("amount_minor", 0),
                currency=str(spec.get("currency") or norm_cur),
            )
            for spec in line_specs
        )
        if any(ln.currency != built_lines[0].currency for ln in built_lines):
            raise ValidationProblem("All posting lines within a JournalEntry must use the same currency.")

        debit_sum = sum(ln.amount_minor for ln in built_lines if ln.side == PostingSide.DEBIT)
        credit_sum = sum(ln.amount_minor for ln in built_lines if ln.side == PostingSide.CREDIT)
        if debit_sum != credit_sum or debit_sum <= 0:
            raise UnbalancedJournalProblem(
                f"JournalEntry must balance debits == credits: debits={debit_sum}, credits={credit_sum}."
            )

        digest = request_digest or canonical_request_digest(clean_desc, built_lines[0].currency, line_specs)
        return cls(
            id=jid,
            idempotency_key=clean_key,
            request_digest=digest,
            description=clean_desc,
            currency=built_lines[0].currency,
            status=JournalStatus.POSTED,
            reverses_journal_id=reverses_journal_id,
            lines=built_lines,
            posted_at=utc_now_iso(),
        )

    def build_reversal(self, idempotency_key: str, reason: str) -> "JournalEntry":
        """Build an offsetting inverse journal entry if not already reversed."""
        if self.status == JournalStatus.REVERSED:
            raise ConflictProblem(f"JournalEntry '{self.id}' has already been reversed.")
        if self.reverses_journal_id is not None:
            raise ConflictProblem(f"JournalEntry '{self.id}' is itself a reversal and cannot be re-reversed.")

        reversed_specs = [
            {
                "account_id": line.account_id,
                "side": line.side.inverted().value,
                "amount_minor": line.amount_minor,
                "currency": line.currency,
            }
            for line in self.lines
        ]
        clean_reason = str(reason or "").strip() or f"Reversal of {self.id}"
        digest = canonical_request_digest(f"reverse:{self.id}:{clean_reason}", self.currency, reversed_specs)
        return JournalEntry.create(
            idempotency_key=idempotency_key,
            description=clean_reason,
            currency=self.currency,
            line_specs=reversed_specs,
            reverses_journal_id=self.id,
            request_digest=digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "idempotency_key": self.idempotency_key,
            "request_digest": self.request_digest,
            "description": self.description,
            "currency": self.currency,
            "status": self.status.value,
            "reverses_journal_id": self.reverses_journal_id,
            "total_amount_minor": self.total_amount_minor,
            "posted_at": self.posted_at,
            "lines": [line.to_dict() for line in self.lines],
        }
