"""
Unit tests for the ClickEvent domain entity.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/url-shortener is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.domain.click_event import ClickEvent


class TestClickEventDomain(unittest.TestCase):
    """ClickEvent field defaults & population tests."""

    def test_default_fields(self) -> None:
        event = ClickEvent(id="evt1", url_id="url1", code="k7X9qZb")
        self.assertEqual(event.id, "evt1")
        self.assertEqual(event.url_id, "url1")
        self.assertEqual(event.code, "k7X9qZb")
        self.assertEqual(event.ip_address, "")
        self.assertEqual(event.user_agent, "")
        self.assertEqual(event.referrer, "")

    def test_all_fields_populated(self) -> None:
        event = ClickEvent(
            id="evt2",
            url_id="url2",
            code="abc123",
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0",
            referrer="https://twitter.com",
        )
        self.assertEqual(event.ip_address, "203.0.113.7")
        self.assertEqual(event.user_agent, "Mozilla/5.0")
        self.assertEqual(event.referrer, "https://twitter.com")

    def test_timestamp_is_utc_aware(self) -> None:
        event = ClickEvent(id="evt3", url_id="url3", code="abc123")
        self.assertIsNotNone(event.timestamp.tzinfo)
        self.assertEqual(event.timestamp.utcoffset().total_seconds(), 0)

    def test_timestamps_independent_per_event(self) -> None:
        first = ClickEvent(id="evt4", url_id="url4", code="abc123")
        second = ClickEvent(id="evt5", url_id="url4", code="abc123")
        self.assertGreaterEqual(second.timestamp, first.timestamp)


if __name__ == "__main__":
    unittest.main()
