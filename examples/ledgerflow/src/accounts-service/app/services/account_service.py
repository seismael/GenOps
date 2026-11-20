"""Application service orchestrating Account lifecycle and CloudEvents emission (US-001-01, US-001-03)."""

from __future__ import annotations

import logging
from typing import List, Optional

from app.domain.account import Account, AccountStatus, AccountType
from app.domain.exceptions import NotFoundProblem
from app.ports.repository import (
    AccountRepositoryPort,
    EventPublisherPort,
    LedgerPolicyRepositoryPort,
    build_cloudevent,
)

logger = logging.getLogger("ledgerflow.accounts.service")


class AccountService:
    """Hexagonal use-case orchestrator for Chart-of-Accounts provisioning and transitions."""

    def __init__(
        self,
        account_repo: AccountRepositoryPort,
        policy_repo: LedgerPolicyRepositoryPort,
        publisher: EventPublisherPort,
    ) -> None:
        self._account_repo = account_repo
        self._policy_repo = policy_repo
        self._publisher = publisher

    def open_account(
        self,
        code: str,
        name: str,
        account_type: AccountType | str,
        currency: str,
        policy_id: str,
        traceparent: Optional[str] = None,
    ) -> Account:
        if self._policy_repo.get_by_id(policy_id) is None:
            raise NotFoundProblem(
                f"Cannot open account '{code}': LedgerPolicy '{policy_id}' does not exist.",
                instance="/api/v1/accounts",
            )
        account = Account.create(
            code=code,
            name=name,
            account_type=account_type,
            currency=currency,
            policy_id=policy_id,
        )
        created = self._account_repo.create(account)
        event = build_cloudevent(
            source="/ledgerflow/accounts-service",
            event_type="com.ledgerflow.account.created",
            subject=created.id,
            data={
                "account_id": created.id,
                "code": created.code,
                "currency": created.currency,
                "account_type": created.account_type.value,
                "status": created.status.value,
            },
            traceparent=traceparent,
        )
        self._publisher.publish(event)
        logger.info("Opened account id=%s code=%s currency=%s", created.id, created.code, created.currency)
        return created

    def get_account(self, account_id: str) -> Account:
        account = self._account_repo.get_by_id(account_id)
        if account is None:
            raise NotFoundProblem(
                f"Account '{account_id}' was not found.",
                instance=f"/api/v1/accounts/{account_id}",
            )
        return account

    def list_accounts(self, currency: Optional[str] = None) -> List[Account]:
        return self._account_repo.list_all(currency=currency)

    def transition_status(
        self,
        account_id: str,
        new_status: AccountStatus | str,
        traceparent: Optional[str] = None,
    ) -> Account:
        current = self.get_account(account_id)
        updated = current.transition_status(new_status)
        persisted = self._account_repo.update_status(account_id, updated.status, updated.updated_at)
        if persisted is None:
            raise NotFoundProblem(f"Account '{account_id}' was not found.", instance=f"/api/v1/accounts/{account_id}/status")
        event = build_cloudevent(
            source="/ledgerflow/accounts-service",
            event_type="com.ledgerflow.account.status_changed",
            subject=persisted.id,
            data={
                "account_id": persisted.id,
                "previous_status": current.status.value,
                "new_status": persisted.status.value,
            },
            traceparent=traceparent,
        )
        self._publisher.publish(event)
        logger.info("Transitioned account id=%s %s -> %s", persisted.id, current.status.value, persisted.status.value)
        return persisted
