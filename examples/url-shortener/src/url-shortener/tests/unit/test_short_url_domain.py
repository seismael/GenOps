"""
Unit tests for the ShortUrl domain entity: validation & SSRF guard.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/url-shortener is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.domain.short_url import ShortUrl


class TestShortUrlValidation(unittest.TestCase):
    """Domain invariant tests for ShortUrl."""

    def test_valid_short_url_creation(self) -> None:
        url = ShortUrl(id="1", code="k7X9qZb", target_url="https://example.com/page?q=genops")
        self.assertEqual(url.code, "k7X9qZb")
        self.assertEqual(url.target_url, "https://example.com/page?q=genops")
        self.assertEqual(url.click_count, 0)
        self.assertTrue(url.is_active)

    def test_code_too_short_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="1", code="ab", target_url="https://example.com")

    def test_code_too_long_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="1", code="a" * 31, target_url="https://example.com")

    def test_code_invalid_characters_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="1", code="bad code!", target_url="https://example.com")

    def test_non_http_scheme_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="1", code="abc123", target_url="ftp://example.com/file")

    def test_missing_host_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ShortUrl(id="1", code="abc123", target_url="https://")

    def test_increment_clicks(self) -> None:
        url = ShortUrl(id="1", code="abc123", target_url="https://example.com")
        url.increment_clicks()
        url.increment_clicks()
        self.assertEqual(url.click_count, 2)


class TestShortUrlSSRF(unittest.TestCase):
    """SSRF guard must reject loopback, private, and link-local IP literals."""

    PROHIBITED_HOSTS = [
        "http://127.0.0.1/admin",              # loopback
        "http://localhost:8080/",              # localhost name
        "http://169.254.169.254/metadata",     # cloud metadata link-local
        "http://10.0.0.1/internal",            # RFC1918 10/8
        "http://10.255.255.255/internal",      # RFC1918 10/8 upper bound
        "http://192.168.1.1/admin",            # RFC1918 192.168/16
        "http://172.16.0.1/admin",             # RFC1918 172.16/12 lower bound
        "http://172.31.255.254/admin",         # RFC1918 172.16/12 upper bound
        "http://169.254.0.1/link-local",       # link-local 169.254/16
        "http://0.0.0.0/",                     # unspecified
        "http://[::1]/admin",                  # IPv6 loopback
        "http://[fc00::1]/internal",           # IPv6 unique-local fc00::/7
        "http://[fd00::1]/internal",           # IPv6 unique-local fd00::/7
        "http://[fe80::1]/link-local",         # IPv6 link-local fe80::/10
    ]

    def test_prohibited_hosts_raise(self) -> None:
        for index, target in enumerate(self.PROHIBITED_HOSTS):
            with self.assertRaises(ValueError, msg=f"expected rejection for {target}"):
                ShortUrl(id=str(index), code=f"bad{index:02d}", target_url=target)

    def test_public_hosts_allowed(self) -> None:
        url = ShortUrl(id="1", code="pub001", target_url="https://example.com")
        self.assertEqual(url.target_url, "https://example.com")

        url2 = ShortUrl(id="2", code="pub002", target_url="http://8.8.8.8/")
        self.assertEqual(url2.target_url, "http://8.8.8.8/")

    def test_private_range_boundaries_allowed(self) -> None:
        # 172.15.x and 172.32.x fall outside 172.16.0.0/12 and must be accepted.
        url = ShortUrl(id="1", code="pub003", target_url="http://172.15.0.1/")
        self.assertEqual(url.target_url, "http://172.15.0.1/")

        url2 = ShortUrl(id="2", code="pub004", target_url="http://172.32.0.1/")
        self.assertEqual(url2.target_url, "http://172.32.0.1/")


if __name__ == "__main__":
    unittest.main()
