"""PostingLine value/entity and normal-balance math helpers (LLD-002, US-002-01)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from app.domain.exceptions import ValidationProblem

SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP"})


class PostingSide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

    def inverted(self) -> "PostingSide":
        return PostingSide.CREDIT if self == PostingSide.DEBIT else PostingSide.DEBIT


@dataclass(frozen=True)
class PostingLine:
    """Single debit or credit posting leg belonging to an immutable JournalEntry."""

    id: str
    journal_id: str
    account_id: str
    side: PostingSide
    amount_minor: int
    currency: str
    balance_after_minor: int = 0

    @classmethod
    def create(
        cls,
        journal_id: str,
        account_id: str,
        side: PostingSide | str,
        amount_minor: int,
        currency: str,
        balance_after_minor: int = 0,
        line_id: str | None = None,
    ) -> "PostingLine":
        acct = str(account_id or "").strip()
        if not acct:
            raise ValidationProblem("Each posting line requires a non-empty account_id.")
        try:
            norm_side = side if isinstance(side, PostingSide) else PostingSide(str(side).strip().upper())
        except ValueError as exc:
            raise ValidationProblem(f"Invalid posting side '{side}': expected DEBIT or CREDIT.") from exc

        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor <= 0:
            raise ValidationProblem("Posting line amount_minor must be a strictly positive integer.")

        norm_cur = str(currency or "").strip().upper()
        if norm_cur not in SUPPORTED_CURRENCIES:
            raise ValidationProblem(
                f"Unsupported posting currency '{currency}': choose from {sorted(SUPPORTED_CURRENCIES)}."
            )

        return cls(
            id=line_id or f"line_{uuid.uuid4().hex[:20]}",
            journal_id=journal_id,
            account_id=acct,
            side=norm_side,
            amount_minor=amount_minor,
            currency=norm_cur,
            balance_after_minor=balance_after_minor,
        )

    def signed_delta(self, normal_balance: str) -> int:
        """Return signed minor-unit delta relative to account normal balance."""
        return self.amount_minor if self.side.value == normal_balance else -self.amount_minor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "journal_id": self.journal_id,
            "account_id": self.account_id,
            "side": self.side.value,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "balance_after_minor": self.balance_after_minor,
        }
