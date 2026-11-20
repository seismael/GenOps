"""SQLite WAL persistence adapter for Account aggregates (ADR-001, LLD-001)."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from app.adapters.persistence.ledger_policy_repository import SqliteAccountsDatabase
from app.domain.account import Account, AccountStatus, AccountType, NormalBalance
from app.domain.exceptions import ConflictProblem


class SqliteAccountRepository:
    """Parameterized SQLite repository implementing AccountRepositoryPort."""

    def __init__(self, db: SqliteAccountsDatabase) -> None:
        self._db = db

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            account_type=AccountType(row["account_type"]),
            normal_balance=NormalBalance(row["normal_balance"]),
            currency=row["currency"],
            balance_minor=int(row["balance_minor"]),
            status=AccountStatus(row["status"]),
            policy_id=row["policy_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, account: Account) -> Account:
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts (
                        id, code, name, account_type, normal_balance,
                        currency, balance_minor, status, policy_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account.id,
                        account.code,
                        account.name,
                        account.account_type.value,
                        account.normal_balance.value,
                        account.currency,
                        account.balance_minor,
                        account.status.value,
                        account.policy_id,
                        account.created_at,
                        account.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictProblem(
                f"Account code '{account.code}' already exists or policy '{account.policy_id}' is missing."
            ) from exc
        return account

    def get_by_id(self, account_id: str) -> Optional[Account]:
        row = self._db.connection.execute(
            """
            SELECT id, code, name, account_type, normal_balance, currency,
                   balance_minor, status, policy_id, created_at, updated_at
            FROM accounts WHERE id = ?
            """,
            (account_id,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def get_by_code(self, code: str) -> Optional[Account]:
        row = self._db.connection.execute(
            """
            SELECT id, code, name, account_type, normal_balance, currency,
                   balance_minor, status, policy_id, created_at, updated_at
            FROM accounts WHERE code = ?
            """,
            (code.strip().upper(),),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def list_all(self, currency: Optional[str] = None) -> List[Account]:
        if currency:
            rows = self._db.connection.execute(
                """
                SELECT id, code, name, account_type, normal_balance, currency,
                       balance_minor, status, policy_id, created_at, updated_at
                FROM accounts WHERE currency = ? ORDER BY created_at ASC, code ASC
                """,
                (currency.strip().upper(),),
            ).fetchall()
        else:
            rows = self._db.connection.execute(
                """
                SELECT id, code, name, account_type, normal_balance, currency,
                       balance_minor, status, policy_id, created_at, updated_at
                FROM accounts ORDER BY created_at ASC, code ASC
                """
            ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def update_status(self, account_id: str, new_status: AccountStatus, updated_at: str) -> Optional[Account]:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "UPDATE accounts SET status = ?, updated_at = ? WHERE id = ?",
                (new_status.value, updated_at, account_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_by_id(account_id)
