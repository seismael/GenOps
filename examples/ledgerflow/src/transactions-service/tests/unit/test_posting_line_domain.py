"""Unit tests for PostingLine validation and signed normal-balance deltas."""

from __future__ import annotations

import unittest

from app.domain.exceptions import ValidationProblem
from app.domain.posting_line import PostingLine, PostingSide


class TestPostingLineDomain(unittest.TestCase):
    def test_signed_delta_for_debit_and_credit_normal_accounts(self) -> None:
        debit_line = PostingLine.create("jrnl_1", "acct_cash", "DEBIT", 2500, "USD")
        credit_line = PostingLine.create("jrnl_1", "acct_rev", PostingSide.CREDIT, 2500, "USD")

        self.assertEqual(debit_line.signed_delta("DEBIT"), 2500)
        self.assertEqual(debit_line.signed_delta("CREDIT"), -2500)
        self.assertEqual(credit_line.signed_delta("CREDIT"), 2500)
        self.assertEqual(credit_line.signed_delta("DEBIT"), -2500)

    def test_reject_non_positive_or_invalid_side(self) -> None:
        with self.assertRaises(ValidationProblem):
            PostingLine.create("jrnl_1", "acct_1", "DEBIT", 0, "USD")
        with self.assertRaises(ValidationProblem):
            PostingLine.create("jrnl_1", "acct_1", "DEBIT", -100, "USD")
        with self.assertRaises(ValidationProblem):
            PostingLine.create("jrnl_1", "acct_1", "TRANSFER", 100, "USD")


if __name__ == "__main__":
    unittest.main()
