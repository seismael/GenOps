"""Application service for LedgerPolicy rules and validation (US-001-02)."""

from __future__ import annotations

import logging
from typing import List

from app.domain.account import Account
from app.domain.exceptions import NotFoundProblem
from app.domain.ledger_policy import LedgerPolicy
from app.ports.repository import LedgerPolicyRepositoryPort

logger = logging.getLogger("ledgerflow.accounts.policy_service")


class LedgerPolicyService:
    """Coordinates creation, lookup, and evaluation of LedgerPolicies."""

    def __init__(self, policy_repo: LedgerPolicyRepositoryPort) -> None:
        self._policy_repo = policy_repo

    def create_policy(
        self,
        name: str,
        allow_overdraft: bool = False,
        max_posting_minor: int = 10_000_000,
        description: str = "",
        policy_id: str | None = None,
    ) -> LedgerPolicy:
        policy = LedgerPolicy.create(
            name=name,
            allow_overdraft=allow_overdraft,
            max_posting_minor=max_posting_minor,
            description=description,
            policy_id=policy_id,
        )
        created = self._policy_repo.create(policy)
        logger.info("Created LedgerPolicy id=%s name=%s allow_overdraft=%s", created.id, created.name, created.allow_overdraft)
        return created

    def get_policy(self, policy_id: str) -> LedgerPolicy:
        policy = self._policy_repo.get_by_id(policy_id)
        if policy is None:
            raise NotFoundProblem(f"LedgerPolicy '{policy_id}' was not found.", instance=f"/api/v1/policies/{policy_id}")
        return policy

    def list_policies(self) -> List[LedgerPolicy]:
        return self._policy_repo.list_all()

    def evaluate_posting(self, account: Account, side: str, amount_minor: int) -> int:
        policy = self.get_policy(account.policy_id)
        return policy.evaluate_posting(account, side, amount_minor)
