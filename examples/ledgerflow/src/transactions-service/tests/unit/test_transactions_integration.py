"""End-to-end integration tests for TransactionsGateway atomic commits, idempotency, and reversals."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.main import FastAPI, TransactionsGateway, create_app


class TestTransactionsIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "ledger.db"
        self.gateway = TransactionsGateway(self.db_path)
        self._seed_ledger()

    def tearDown(self) -> None:
        self.gateway.close()
        self._tmp.cleanup()

    def _seed_ledger(self) -> None:
        conn = self.gateway.container.db.connection
        conn.execute(
            "INSERT INTO ledger_policies (id, name, allow_overdraft, max_posting_minor, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("pol_strict", "strict", 0, 50_000, "No overdraft", "2026-11-20T12:00:00Z"),
        )
        accounts = [
            ("acct_cash", "CASH-USD-001", "Operating Cash", "ASSET", "DEBIT", "USD", 20_000, "ACTIVE", "pol_strict"),
            ("acct_rev", "REV-USD-001", "Settlement Revenue", "REVENUE", "CREDIT", "USD", 0, "ACTIVE", "pol_strict"),
            ("acct_frozen", "FRZ-USD-001", "Frozen Escrow", "LIABILITY", "CREDIT", "USD", 5_000, "FROZEN", "pol_strict"),
        ]
        for row in accounts:
            conn.execute(
                "INSERT INTO accounts (id, code, name, account_type, normal_balance, currency, balance_minor, status, policy_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*row, "2026-11-20T12:00:00Z", "2026-11-20T12:00:00Z"),
            )

    def _get_balance(self, account_id: str) -> int:
        row = self.gateway.container.db.connection.execute(
            "SELECT balance_minor FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return int(row["balance_minor"])

    def test_atomic_post_idempotency_conflict_and_reversal(self) -> None:
        trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-b7ad6b7169203331-01"
        lines = [
            {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 10_000},
            {"account_id": "acct_rev", "side": "CREDIT", "amount_minor": 10_000},
        ]
        # US-002-01: First post commits atomically (201)
        st1, j1 = self.gateway.post_journal("pay-991", "Order 991 settlement", "USD", lines, traceparent=trace)
        self.assertEqual(st1, 201)
        self.assertEqual(self._get_balance("acct_cash"), 30_000)
        self.assertEqual(self._get_balance("acct_rev"), 10_000)

        # US-002-02: Identical retry returns 200 OK without altering balances or emitting duplicate event
        st_rep, j_rep = self.gateway.post_journal("pay-991", "Order 991 settlement", "USD", lines, traceparent=trace)
        self.assertEqual(st_rep, 200)
        self.assertEqual(j_rep["id"], j1["id"])
        self.assertEqual(self._get_balance("acct_cash"), 30_000)

        # US-002-02: Reusing idempotency key with modified payload rejects 409 RFC 9457
        st_conf, err_conf = self.gateway.post_journal(
            "pay-991",
            "Order 991 tampered",
            "USD",
            [
                {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 9_000},
                {"account_id": "acct_rev", "side": "CREDIT", "amount_minor": 9_000},
            ],
        )
        self.assertEqual(st_conf, 409)
        self.assertEqual(err_conf["error_code"], "IDEMPOTENCY_KEY_CONFLICT")

        # US-002-03: Offsetting reversal restores prior balances & links reverses_journal_id
        st_rev, j2 = self.gateway.reverse_journal(j1["id"], "rev-pay-991", "Merchant refund", traceparent=trace)
        self.assertEqual(st_rev, 201)
        self.assertEqual(j2["reverses_journal_id"], j1["id"])
        self.assertEqual(self._get_balance("acct_cash"), 20_000)
        self.assertEqual(self._get_balance("acct_rev"), 0)

        # Reversal idempotent retry returns 200, second reversal key returns 409
        st_rev_rep, j2_rep = self.gateway.reverse_journal(j1["id"], "rev-pay-991", "Merchant refund")
        self.assertEqual(st_rev_rep, 200)
        self.assertEqual(j2_rep["id"], j2["id"])

        st_rev2, _ = self.gateway.reverse_journal(j1["id"], "rev-pay-991-dup", "Duplicate reversal")
        self.assertEqual(st_rev2, 409)

        # CloudEvents v1.0.2 telemetry emitted only for state-mutating commits
        events = self.gateway.container.publisher.events
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["specversion"], "1.0")
        self.assertEqual(events[0]["type"], "com.ledgerflow.journal.posted")
        self.assertEqual(events[1]["type"], "com.ledgerflow.journal.reversed")
        self.assertEqual(events[1]["traceparent"], trace)

        # Account posting lines history check
        st_hist, hist = self.gateway.list_account_lines("acct_cash")
        self.assertEqual(st_hist, 200)
        self.assertEqual(len(hist["items"]), 2)

    def test_rollback_on_frozen_account_or_overdraft_policy(self) -> None:
        # Posting referencing FROZEN account fails 422 without modifying acct_cash
        st_frz, err_frz = self.gateway.post_journal(
            "pay-frozen",
            "Blocked escrow",
            "USD",
            [
                {"account_id": "acct_cash", "side": "DEBIT", "amount_minor": 1_000},
                {"account_id": "acct_frozen", "side": "CREDIT", "amount_minor": 1_000},
            ],
        )
        self.assertEqual(st_frz, 422)
        self.assertEqual(err_frz["error_code"], "ACCOUNT_NOT_ACTIVE")
        self.assertEqual(self._get_balance("acct_cash"), 20_000)

        # Attempting to credit CASH-USD-001 (ASSET) by 25_000 causes -5_000 overdraft -> rolls back
        st_od, err_od = self.gateway.post_journal(
            "pay-overdraft",
            "Overdraw cash",
            "USD",
            [
                {"account_id": "acct_rev", "side": "DEBIT", "amount_minor": 25_000},
                {"account_id": "acct_cash", "side": "CREDIT", "amount_minor": 25_000},
            ],
        )
        self.assertEqual(st_od, 422)
        self.assertEqual(err_od["error_code"], "POLICY_VIOLATION")
        self.assertEqual(self._get_balance("acct_cash"), 20_000)

    @unittest.skipIf(FastAPI is None, "FastAPI not installed in offline stdlib environment")
    def test_fastapi_endpoints_when_installed(self) -> None:
        from fastapi.testclient import TestClient

        db_http = Path(self._tmp.name) / "http_tx.db"
        gw = TransactionsGateway(db_http)
        conn = gw.container.db.connection
        conn.execute(
            "INSERT INTO ledger_policies (id, name, allow_overdraft, max_posting_minor, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pol_1", "std", 0, 100000, "std", "2026-11-20T12:00:00Z"),
        )
        for aid, code, atype, nb in [("a1", "CASH-1", "ASSET", "DEBIT"), ("a2", "REV-1", "REVENUE", "CREDIT")]:
            conn.execute(
                "INSERT INTO accounts (id, code, name, account_type, normal_balance, currency, balance_minor, status, policy_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'USD', 0, 'ACTIVE', 'pol_1', '2026-11-20T12:00:00Z', '2026-11-20T12:00:00Z')",
                (aid, code, code, atype, nb),
            )
        gw.close()

        with TestClient(create_app(db_http)) as client:
            r = client.post(
                "/api/v1/journals",
                json={
                    "idempotency_key": "http-j1",
                    "description": "FastAPI settlement",
                    "currency": "USD",
                    "lines": [
                        {"account_id": "a1", "side": "DEBIT", "amount_minor": 2500},
                        {"account_id": "a2", "side": "CREDIT", "amount_minor": 2500},
                    ],
                },
            )
            self.assertEqual(r.status_code, 201)
            self.assertEqual(r.json()["total_amount_minor"], 2500)


if __name__ == "__main__":
    unittest.main()
