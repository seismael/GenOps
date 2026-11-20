"""Account aggregate root and financial ledger invariants (LLD-001, US-001-01, US-001-03)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from app.domain.exceptions import ConflictProblem, ValidationProblem

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")
SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP"})


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class NormalBalance(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


_NORMAL_BALANCE_BY_TYPE: Dict[AccountType, NormalBalance] = {
    AccountType.ASSET: NormalBalance.DEBIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
    AccountType.LIABILITY: NormalBalance.CREDIT,
    AccountType.EQUITY: NormalBalance.CREDIT,
    AccountType.REVENUE: NormalBalance.CREDIT,
}


def utc_now_iso() -> str:
    """Return canonical UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Account:
    """Strongly typed Chart-of-Accounts aggregate root storing integer minor units."""

    id: str
    code: str
    name: str
    account_type: AccountType
    normal_balance: NormalBalance
    currency: str
    balance_minor: int
    status: AccountStatus
    policy_id: str
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        account_type: AccountType | str,
        currency: str,
        policy_id: str,
        account_id: str | None = None,
    ) -> "Account":
        norm_code = str(code or "").strip().upper()
        if not _CODE_RE.match(norm_code):
            raise ValidationProblem(
                f"Invalid account code '{code}': must match ^[A-Z0-9][A-Z0-9_-]{{2,31}}$."
            )
        norm_name = str(name or "").strip()
        if not norm_name or len(norm_name) > 120:
            raise ValidationProblem("Account name must be between 1 and 120 characters.")

        try:
            acct_type = account_type if isinstance(account_type, AccountType) else AccountType(str(account_type).strip().upper())
        except ValueError as exc:
            raise ValidationProblem(f"Unsupported account_type '{account_type}'.") from exc

        norm_currency = str(currency or "").strip().upper()
        if norm_currency not in SUPPORTED_CURRENCIES:
            raise ValidationProblem(
                f"Unsupported currency '{currency}': choose from {sorted(SUPPORTED_CURRENCIES)}."
            )
        if not str(policy_id or "").strip():
            raise ValidationProblem("policy_id is required when opening a ledger account.")

        now = utc_now_iso()
        return cls(
            id=account_id or f"acct_{uuid.uuid4().hex[:20]}",
            code=norm_code,
            name=norm_name,
            account_type=acct_type,
            normal_balance=_NORMAL_BALANCE_BY_TYPE[acct_type],
            currency=norm_currency,
            balance_minor=0,
            status=AccountStatus.ACTIVE,
            policy_id=policy_id.strip(),
            created_at=now,
            updated_at=now,
        )

    def signed_delta_for_side(self, side: str, amount_minor: int) -> int:
        """Compute signed integer balance delta using account normal balance."""
        norm_side = str(side or "").strip().upper()
        if norm_side not in ("DEBIT", "CREDIT"):
            raise ValidationProblem(f"Invalid posting side '{side}': expected DEBIT or CREDIT.")
        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor <= 0:
            raise ValidationProblem("Posting amount_minor must be a strictly positive integer.")
        return amount_minor if norm_side == self.normal_balance.value else -amount_minor

    def transition_status(self, target_status: AccountStatus | str) -> "Account":
        """Transition lifecycle state while protecting closed and non-zero accounts."""
        try:
            new_status = target_status if isinstance(target_status, AccountStatus) else AccountStatus(str(target_status).strip().upper())
        except ValueError as exc:
            raise ValidationProblem(f"Invalid target status '{target_status}'.") from exc

        if self.status == AccountStatus.CLOSED:
            raise ConflictProblem(f"Account '{self.id}' is already CLOSED and cannot transition to {new_status.value}.")
        if new_status == self.status:
            raise ConflictProblem(f"Account '{self.id}' is already in status {self.status.value}.")
        if new_status == AccountStatus.CLOSED and self.balance_minor != 0:
            raise ConflictProblem(
                f"Cannot close account '{self.id}' with non-zero balance ({self.balance_minor} {self.currency} minor units)."
            )
        return Account(
            id=self.id,
            code=self.code,
            name=self.name,
            account_type=self.account_type,
            normal_balance=self.normal_balance,
            currency=self.currency,
            balance_minor=self.balance_minor,
            status=new_status,
            policy_id=self.policy_id,
            created_at=self.created_at,
            updated_at=utc_now_iso(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "account_type": self.account_type.value,
            "normal_balance": self.normal_balance.value,
            "currency": self.currency,
            "balance_minor": self.balance_minor,
            "status": self.status.value,
            "policy_id": self.policy_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
