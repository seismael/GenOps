"""
Unit tests for the ApiKey domain entity: create / verify / revoke.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/url-shortener is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.domain.api_key import ApiKey


class TestApiKeyDomain(unittest.TestCase):
    """ApiKey factory, hashing, verification, and revocation tests."""

    def test_create_returns_key_and_raw_token(self) -> None:
        api_key, token = ApiKey.create("super-secret-token", "dev@example.com")
        self.assertIsInstance(api_key, ApiKey)
        self.assertEqual(token, "super-secret-token")
        self.assertEqual(api_key.owner_email, "dev@example.com")
        self.assertFalse(api_key.is_revoked)

    def test_key_id_prefix_and_hash_format(self) -> None:
        api_key, _ = ApiKey.create("super-secret-token", "dev@example.com")
        self.assertTrue(api_key.key_id.startswith("key_"))
        self.assertEqual(len(api_key.key_hash), 64)  # SHA-256 hex digest
        self.assertNotEqual(api_key.key_hash, "super-secret-token")

    def test_verify_correct_token(self) -> None:
        api_key, token = ApiKey.create("super-secret-token", "dev@example.com")
        self.assertTrue(api_key.verify(token))

    def test_verify_wrong_token(self) -> None:
        api_key, _ = ApiKey.create("super-secret-token", "dev@example.com")
        self.assertFalse(api_key.verify("wrong-token"))

    def test_verify_after_revoke(self) -> None:
        api_key, token = ApiKey.create("super-secret-token", "dev@example.com")
        api_key.is_revoked = True
        self.assertFalse(api_key.verify(token))

    def test_same_token_hashes_deterministically(self) -> None:
        key1, _ = ApiKey.create("same-token", "a@example.com")
        key2, _ = ApiKey.create("same-token", "b@example.com")
        self.assertEqual(key1.key_hash, key2.key_hash)
        self.assertEqual(key1.key_id, key2.key_id)


if __name__ == "__main__":
    unittest.main()
