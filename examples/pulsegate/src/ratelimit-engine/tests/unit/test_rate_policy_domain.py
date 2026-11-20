"""Unit & SQLite WAL integration tests for ratelimit-engine."""

import tempfile
import unittest
from pathlib import Path

from app.adapters.persistence.rate_policy_repository import SqliteRateLimitStore
from app.domain.rate_policy import RatePolicy


class TestRateLimitEngine(unittest.TestCase):
    def test_invalid_policy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RatePolicy(tenant_id="t1", capacity=0, refill_per_sec=1.0)
        with self.assertRaises(ValueError):
            RatePolicy(tenant_id="t1", capacity=5, refill_per_sec=-2.0)

    def test_atomic_acquire_and_refill_over_wal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteRateLimitStore(str(Path(tmp) / "rl.db"))
            try:
                store.upsert_policy(RatePolicy(tenant_id="acme", capacity=2, refill_per_sec=1.0), now_ms=1000)
                ok1, rem1, r1 = store.acquire("acme", now_ms=1000)
                ok2, rem2, r2 = store.acquire("acme", now_ms=1000)
                ok3, rem3, r3 = store.acquire("acme", now_ms=1000)
                self.assertEqual((ok1, rem1, r1), (True, 1, 0))
                self.assertEqual((ok2, rem2, r2), (True, 0, 0))
                self.assertFalse(ok3)
                self.assertEqual(rem3, 0)
                self.assertEqual(r3, 1000)

                # After 1.5s, 1.5 tokens refill -> 1 request succeeds
                ok4, rem4, _ = store.acquire("acme", now_ms=2500)
                self.assertTrue(ok4)
                self.assertEqual(rem4, 0)
            finally:
                store.close()
