"""Dependency-injection container wiring accounts-service ports and adapters."""

from __future__ import annotations

from pathlib import Path

from app.adapters.persistence.account_repository import SqliteAccountRepository
from app.adapters.persistence.ledger_policy_repository import (
    SqliteAccountsDatabase,
    SqliteLedgerPolicyRepository,
)
from app.ports.repository import InMemoryEventPublisher
from app.services.account_service import AccountService
from app.services.ledger_policy_service import LedgerPolicyService


class AccountsContainer:
    """Explicit composition root owning database lifecycle and service instances."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db = SqliteAccountsDatabase(db_path)
        self.publisher = InMemoryEventPublisher()
        self.policy_repo = SqliteLedgerPolicyRepository(self.db)
        self.account_repo = SqliteAccountRepository(self.db)
        self.policy_service = LedgerPolicyService(self.policy_repo)
        self.account_service = AccountService(self.account_repo, self.policy_repo, self.publisher)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "AccountsContainer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
