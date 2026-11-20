"""Unit tests for JournalEntry double-entry balance invariants, digests, and reversals."""

from __future__ import annotations

import unittest

from app.domain.exceptions import ConflictProblem, UnbalancedJournalProblem, ValidationProblem
from app.domain.journal_entry import JournalEntry, canonical_request_digest


class TestJournalEntryDomain(unittest.TestCase):
    def test_balanced_journal_and_canonical_digest(self) -> None:
        lines = [
            {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 12_500},
            {"account_id": "acct_rev", "side": "CREDIT", "amount_minor": 12_500},
        ]
        entry = JournalEntry.create("idem-1", "Customer checkout", "USD", lines)
        self.assertEqual(entry.total_amount_minor, 12_500)
        self.assertEqual(
            entry.request_digest,
            canonical_request_digest("Customer checkout", "USD", lines),
        )

    def test_reject_unbalanced_or_mixed_currency_lines(self) -> None:
        with self.assertRaises(UnbalancedJournalProblem) as err:
            JournalEntry.create(
                "idem-bad-1",
                "Out of balance",
                "USD",
                [
                    {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 1000},
                    {"account_id": "acct_rev", "side": "CREDIT", "amount_minor": 900},
                ],
            )
        self.assertEqual(err.exception.status_code, 422)

        with self.assertRaises(ValidationProblem):
            JournalEntry.create(
                "idem-bad-cur",
                "Mixed currencies",
                "USD",
                [
                    {"account_id": "acct_a", "side": "DEBIT", "amount_minor": 1000, "currency": "USD"},
                    {"account_id": "acct_b", "side": "CREDIT", "amount_minor": 1000, "currency": "EUR"},
                ],
            )

    def test_reversal_inverts_sides_and_rejects_chaining(self) -> None:
        entry = JournalEntry.create(
            "idem-rev-src",
            "Transfer",
            "USD",
            [
                {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 5000},
                {"account_id": "acct_rev", "side": "CREDIT", "amount_minor": 5000},
            ],
        )
        rev = entry.build_reversal("idem-rev-1", "Chargeback refund")
        self.assertEqual(rev.reverses_journal_id, entry.id)
        self.assertEqual(rev.lines[0].side.value, "CREDIT")
        self.assertEqual(rev.lines[1].side.value, "DEBIT")

        with self.assertRaises(ConflictProblem):
            rev.build_reversal("idem-rev-2", "Double reversal")


if __name__ == "__main__":
    unittest.main()
