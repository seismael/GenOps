"""
Unit & Integration test suite for Krypton URL Shortener.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/url-shortener is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.domain.api_key import ApiKey
from app.domain.short_url import ShortUrl
from app.main import ApplicationContainer, KryptonGateway
from app.services.short_url_service import ShortCodeGenerator, UrlShortenerService


class TestShortUrlDomain(unittest.TestCase):
    """Domain model tests."""

    def test_valid_short_url_creation(self) -> None:
        url = ShortUrl(id="1", code="k7X9qZb", target_url="https://google.com/search?q=genops")
        self.assertEqual(url.code, "k7X9qZb")
        self.assertEqual(url.click_count, 0)
        url.increment_clicks()
        self.assertEqual(url.click_count, 1)

    def test_ssrf_protection_in_domain(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="2", code="bad01", target_url="http://127.0.0.1/admin")

        with self.assertRaises(ValueError):
            ShortUrl(id="3", code="bad02", target_url="http://localhost:8080/")

        with self.assertRaises(ValueError):
            ShortUrl(id="4", code="bad03", target_url="http://169.254.169.254/metadata")


class TestApiKeyDomain(unittest.TestCase):
    """API Key authentication tests."""

    def test_api_key_verification(self) -> None:
        api_key, token = ApiKey.create("super-secret-token", "dev@example.com")
        self.assertTrue(api_key.verify(token))
        self.assertFalse(api_key.verify("wrong-token"))

        api_key.is_revoked = True
        self.assertFalse(api_key.verify(token))


class TestShortCodeGenerator(unittest.TestCase):
    """Base62 ShortCodeGenerator tests."""

    def test_deterministic_generation(self) -> None:
        code1 = ShortCodeGenerator.generate("https://example.com/page", salt=0)
        code2 = ShortCodeGenerator.generate("https://example.com/page", salt=0)
        self.assertEqual(code1, code2)
        self.assertEqual(len(code1), 7)

        # Different salt produces different code
        code_salted = ShortCodeGenerator.generate("https://example.com/page", salt=1)
        self.assertNotEqual(code1, code_salted)
        self.assertEqual(len(code_salted), 7)


class TestKryptonGatewayEndToEnd(unittest.TestCase):
    """End-to-end gateway handler tests."""

    def setUp(self) -> None:
        self.container = ApplicationContainer(":memory:")
        self.gateway = KryptonGateway(self.container)
        self.token = self.gateway.create_api_key("marketing@acme.com", "marketing-token-123")

    def tearDown(self) -> None:
        self.container.db.close()

    def test_full_shorten_redirect_analytics_lifecycle(self) -> None:
        # 1. Shorten URL
        res = self.gateway.handle_shorten(self.token, "https://github.com/seismael/genops")
        self.assertEqual(res["status"], 201)
        code = res["data"]["code"]
        self.assertTrue(bool(code))

        # 2. Redirect visitor 1
        redir1 = self.gateway.handle_redirect(code, ip="1.2.3.4", referrer="https://twitter.com")
        self.assertEqual(redir1["status"], 302)
        self.assertEqual(redir1["location"], "https://github.com/seismael/genops")

        # 3. Redirect visitor 2
        redir2 = self.gateway.handle_redirect(code, ip="5.6.7.8", referrer="https://linkedin.com")
        self.assertEqual(redir2["status"], 302)

        # 4. Check Analytics
        analytics = self.gateway.handle_analytics(self.token, code)
        self.assertEqual(analytics["status"], 200)
        self.assertEqual(analytics["data"]["total_clicks"], 2)
        self.assertEqual(len(analytics["data"]["recent_referrers"]), 2)

    def test_unauthorized_access(self) -> None:
        res = self.gateway.handle_shorten("invalid-token", "https://example.com")
        self.assertEqual(res["status"], 401)

    def test_duplicate_custom_alias_returns_409_and_cache_preserves_clicks(self) -> None:
        first = self.gateway.handle_shorten(self.token, "https://example.com/one", custom_alias="myalias")
        self.assertEqual(first["status"], 201)
        dup = self.gateway.handle_shorten(self.token, "https://example.com/two", custom_alias="myalias")
        self.assertEqual(dup["status"], 409)

        # Repeated cached redirects must increment live click_count consistently
        for _ in range(3):
            redir = self.gateway.handle_redirect("myalias", ip="9.9.9.9")
            self.assertEqual(redir["status"], 302)
        cached_obj = self.container.url_service._cache.get("myalias")
        self.assertIsNotNone(cached_obj)
        self.assertEqual(cached_obj.click_count, 3)

    def test_lru_cache_bounded_eviction(self) -> None:
        svc = UrlShortenerService(self.container.url_repo, self.container.analytics_repo, max_cache_size=2)
        s1 = svc.shorten_url("https://example.com/1", custom_alias="code001")
        s2 = svc.shorten_url("https://example.com/2", custom_alias="code002")
        s3 = svc.shorten_url("https://example.com/3", custom_alias="code003")
        self.assertEqual(len(svc._cache), 2)
        self.assertNotIn(s1.code, svc._cache)
        self.assertIn(s2.code, svc._cache)
        self.assertIn(s3.code, svc._cache)

    def test_api_key_hydration_duplicate_and_foreign_keys_enabled(self) -> None:
        self.assertTrue(self.container.api_key_repo.verify_token(self.token))
        expected_key, _ = ApiKey.create(self.token, "marketing@acme.com")
        loaded = self.container.api_key_repo.get_by_id(expected_key.key_id)
        self.assertIsNotNone(loaded)
        self.assertIsNotNone(loaded.created_at)

        dup_key, _ = ApiKey.create(self.token, "other@example.com")
        with self.assertRaises(ValueError):
            self.container.api_key_repo.save(dup_key)

        with self.container.db.connection() as conn:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(fk, 1)


if __name__ == "__main__":
    unittest.main()
