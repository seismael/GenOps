"""LedgerPolicy domain entity governing overdrafts and posting caps (LLD-001, US-001-02)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict

from app.domain.account import Account, AccountStatus, utc_now_iso
from app.domain.exceptions import PolicyViolationProblem, ValidationProblem


@dataclass(frozen=True)
class LedgerPolicy:
    """Domain policy evaluating posting eligibility for a LedgerFlow Account."""

    id: str
    name: str
    allow_overdraft: bool
    max_posting_minor: int
    description: str
    created_at: str

    @classmethod
    def create(
        cls,
        name: str,
        allow_overdraft: bool = False,
        max_posting_minor: int = 10_000_000,
        description: str = "",
        policy_id: str | None = None,
    ) -> "LedgerPolicy":
        clean_name = str(name or "").strip()
        if not clean_name or len(clean_name) > 80:
            raise ValidationProblem("Policy name must be between 1 and 80 characters.")
        if not isinstance(max_posting_minor, int) or isinstance(max_posting_minor, bool) or max_posting_minor <= 0:
            raise ValidationProblem("max_posting_minor must be a positive integer.")
        return cls(
            id=policy_id or f"pol_{uuid.uuid4().hex[:20]}",
            name=clean_name,
            allow_overdraft=bool(allow_overdraft),
            max_posting_minor=max_posting_minor,
            description=str(description or "").strip(),
            created_at=utc_now_iso(),
        )

    def evaluate_posting(self, account: Account, side: str, amount_minor: int) -> int:
        """Validate account status, single-posting ceiling, and overdraft invariant; return new balance."""
        if account.status != AccountStatus.ACTIVE:
            raise PolicyViolationProblem(
                f"Account '{account.id}' ({account.code}) has status {account.status.value}; postings require ACTIVE status."
            )
        delta = account.signed_delta_for_side(side, amount_minor)
        if amount_minor > self.max_posting_minor:
            raise PolicyViolationProblem(
                f"Posting {amount_minor} minor units exceeds LedgerPolicy '{self.name}' cap of {self.max_posting_minor}."
            )
        projected_balance = account.balance_minor + delta
        if not self.allow_overdraft and projected_balance < 0:
            raise PolicyViolationProblem(
                f"Overdraft denied on account '{account.code}' by policy '{self.name}': "
                f"current={account.balance_minor}, projected={projected_balance}."
            )
        return projected_balance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "allow_overdraft": self.allow_overdraft,
            "max_posting_minor": self.max_posting_minor,
            "description": self.description,
            "created_at": self.created_at,
        }
