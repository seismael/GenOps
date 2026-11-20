"""Unit tests for LedgerPolicy overdraft and single-posting cap enforcement (US-001-02)."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.domain.account import Account, AccountStatus
from app.domain.exceptions import PolicyViolationProblem, ValidationProblem
from app.domain.ledger_policy import LedgerPolicy


class TestLedgerPolicyDomain(unittest.TestCase):
    def test_policy_blocks_overdraft_when_disallowed(self) -> None:
        policy = LedgerPolicy.create("strict-no-overdraft", allow_overdraft=False, max_posting_minor=50_000)
        acct = replace(Account.create("CASH-USD-010", "Customer Cash", "ASSET", "USD", policy.id), balance_minor=10_000)

        self.assertEqual(policy.evaluate_posting(acct, "DEBIT", 25_000), 35_000)
        self.assertEqual(policy.evaluate_posting(acct, "CREDIT", 10_000), 0)

        with self.assertRaises(PolicyViolationProblem) as err:
            policy.evaluate_posting(acct, "CREDIT", 10_001)
        self.assertEqual(err.exception.status_code, 422)

    def test_policy_enforces_max_cap_and_active_status(self) -> None:
        policy = LedgerPolicy.create("overdraft-allowed", allow_overdraft=True, max_posting_minor=5_000)
        acct = Account.create("CASH-EUR-010", "Overdraft Wallet", "ASSET", "EUR", policy.id)

        self.assertEqual(policy.evaluate_posting(acct, "CREDIT", 2_500), -2_500)

        with self.assertRaises(PolicyViolationProblem):
            policy.evaluate_posting(acct, "DEBIT", 5_001)

        frozen = acct.transition_status(AccountStatus.FROZEN)
        with self.assertRaises(PolicyViolationProblem):
            policy.evaluate_posting(frozen, "DEBIT", 100)

    def test_invalid_policy_inputs(self) -> None:
        with self.assertRaises(ValidationProblem):
            LedgerPolicy.create("", allow_overdraft=False, max_posting_minor=100)
        with self.assertRaises(ValidationProblem):
            LedgerPolicy.create("invalid-cap", allow_overdraft=False, max_posting_minor=0)


if __name__ == "__main__":
    unittest.main()
