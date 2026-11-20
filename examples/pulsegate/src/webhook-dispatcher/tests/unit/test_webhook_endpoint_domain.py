"""Unit & SQLite WAL tests for webhook-dispatcher."""

import unittest

from app.adapters.persistence.webhook_endpoint_repository import SqliteWebhookStore
from app.domain.delivery_attempt import DeliveryAttempt
from app.domain.webhook_endpoint import WebhookEndpoint


class TestWebhookDispatcher(unittest.TestCase):
    def test_https_enforcement_and_hmac_signature(self) -> None:
        with self.assertRaises(ValueError):
            WebhookEndpoint(endpoint_id="ep-bad", url="http://example.com/hook", secret="s" * 20)

        ep = WebhookEndpoint(endpoint_id="ep-1", url="https://hooks.acme.test/events", secret="super-secret-signing-key")
        sig = ep.sign_payload(b'{"specversion":"1.0","id":"evt-1"}')
        self.assertTrue(sig.startswith("sha256="))
        self.assertEqual(len(sig), 7 + 64)

    def test_retry_dead_letter_state_machine_and_persistence(self) -> None:
        store = SqliteWebhookStore(":memory:")
        try:
            ep = WebhookEndpoint(endpoint_id="ep-1", url="https://hooks.acme.test/events", secret="super-secret-signing-key")
            store.register_endpoint(ep)

            att = DeliveryAttempt(attempt_id="att-1", endpoint_id="ep-1", event_id="evt-1", max_attempts=2)
            self.assertEqual(att.record_result(503), "RETRYING")
            self.assertEqual(att.record_result(502), "DEAD_LETTERED")
            store.save_attempt(att)

            loaded = store.get_attempt("att-1")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.status, "DEAD_LETTERED")
            self.assertEqual(loaded.attempt_count, 2)
        finally:
            store.close()
