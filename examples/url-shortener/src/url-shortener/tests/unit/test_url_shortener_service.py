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


if __name__ == "__main__":
    unittest.main()
