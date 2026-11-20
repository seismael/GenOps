"""End-to-end integration tests for AccountsGateway, SQLite WAL, RFC 9457, and CloudEvents v1.0.2."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.main import AccountsGateway, FastAPI, create_app


class TestAccountsIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "ledger.db"
        self.gateway = AccountsGateway(self.db_path)

    def tearDown(self) -> None:
        self.gateway.close()
        self._tmp.cleanup()

    def test_full_account_and_policy_lifecycle_with_cloudevents(self) -> None:
        st_pol, pol = self.gateway.create_policy("treasury-default", allow_overdraft=False, max_posting_minor=500_000)
        self.assertEqual(st_pol, 201)

        st_acct, acct = self.gateway.open_account(
            code="CASH-USD-001",
            name="Primary Operating Cash",
            account_type="ASSET",
            currency="USD",
            policy_id=pol["id"],
            traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        )
        self.assertEqual(st_acct, 201)
        self.assertEqual(acct["balance_minor"], 0)
        self.assertEqual(acct["normal_balance"], "DEBIT")

        # Duplicate code yields RFC 9457 409 Conflict
        st_dup, dup_err = self.gateway.open_account(
            code="CASH-USD-001",
            name="Duplicate Code",
            account_type="ASSET",
            currency="USD",
            policy_id=pol["id"],
        )
        self.assertEqual(st_dup, 409)
        self.assertEqual(dup_err["type"], "urn:ledgerflow:problem:conflict")

        # Freeze and close zero-balance account
        st_frz, frz = self.gateway.transition_status(acct["id"], "FROZEN")
        self.assertEqual(st_frz, 200)
        self.assertEqual(frz["status"], "FROZEN")

        st_cls, cls = self.gateway.transition_status(acct["id"], "CLOSED")
        self.assertEqual(st_cls, 200)
        self.assertEqual(cls["status"], "CLOSED")

        # Verify CNCF CloudEvents v1.0.2 telemetry
        events = self.gateway.container.publisher.events
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["specversion"], "1.0")
        self.assertEqual(events[0]["type"], "com.ledgerflow.account.created")
        self.assertEqual(events[0]["traceparent"], "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
        self.assertEqual(events[1]["type"], "com.ledgerflow.account.status_changed")
        self.assertEqual(events[2]["data"]["new_status"], "CLOSED")

    @unittest.skipIf(FastAPI is None, "FastAPI not installed in offline stdlib environment")
    def test_fastapi_endpoints_when_installed(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(create_app(Path(self._tmp.name) / "http_accounts.db")) as client:
            r_pol = client.post("/api/v1/policies", json={"name": "http-policy", "max_posting_minor": 10000})
            self.assertEqual(r_pol.status_code, 201)
            r_acct = client.post(
                "/api/v1/accounts",
                json={
                    "code": "REV-USD-001",
                    "name": "Revenue Account",
                    "account_type": "REVENUE",
                    "currency": "USD",
                    "policy_id": r_pol.json()["id"],
                },
            )
            self.assertEqual(r_acct.status_code, 201)
            self.assertEqual(r_acct.json()["normal_balance"], "CREDIT")


if __name__ == "__main__":
    unittest.main()
