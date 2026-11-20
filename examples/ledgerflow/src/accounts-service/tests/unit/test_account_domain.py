"""Unit tests for Account aggregate invariants and lifecycle rules (US-001-01, US-001-03)."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.domain.account import Account, AccountStatus, AccountType, NormalBalance
from app.domain.exceptions import ConflictProblem, ValidationProblem


class TestAccountDomain(unittest.TestCase):
    def test_create_account_normal_balance_mapping(self) -> None:
        asset = Account.create("CASH-USD-001", "Operating Cash", "ASSET", "usd", "pol_std")
        self.assertEqual(asset.code, "CASH-USD-001")
        self.assertEqual(asset.normal_balance, NormalBalance.DEBIT)
        self.assertEqual(asset.currency, "USD")
        self.assertEqual(asset.balance_minor, 0)
        self.assertEqual(asset.status, AccountStatus.ACTIVE)

        rev = Account.create("REV-USD-001", "Platform Fees", AccountType.REVENUE, "USD", "pol_std")
        self.assertEqual(rev.normal_balance, NormalBalance.CREDIT)

    def test_reject_invalid_code_or_currency(self) -> None:
        with self.assertRaises(ValidationProblem) as ctx:
            Account.create("bad code!", "Bad", "ASSET", "USD", "pol_std")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(ValidationProblem):
            Account.create("CASH-001", "Bad Currency", "ASSET", "XYZ", "pol_std")

    def test_lifecycle_transitions_and_nonzero_close_guard(self) -> None:
        acct = Account.create("CASH-USD-002", "Settlement Wallet", "ASSET", "USD", "pol_std")
        frozen = acct.transition_status(AccountStatus.FROZEN)
        self.assertEqual(frozen.status, AccountStatus.FROZEN)

        unfrozen = frozen.transition_status(AccountStatus.ACTIVE)
        self.assertEqual(unfrozen.status, AccountStatus.ACTIVE)

        funded = replace(unfrozen, balance_minor=1500)
        with self.assertRaises(ConflictProblem) as err_close:
            funded.transition_status(AccountStatus.CLOSED)
        problem = err_close.exception.to_problem_details()
        self.assertEqual(problem["status"], 409)
        self.assertIn("non-zero balance", problem["detail"])

        closed = unfrozen.transition_status(AccountStatus.CLOSED)
        self.assertEqual(closed.status, AccountStatus.CLOSED)
        with self.assertRaises(ConflictProblem):
            closed.transition_status(AccountStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
