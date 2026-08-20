"""
Application Service: URL Shortener business logic orchestrator.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, Optional

from app.domain.click_event import ClickEvent
from app.domain.short_url import ShortUrl
from app.ports.repository import IAnalyticsRepository, IUrlRepository


class ShortCodeGenerator:
    """Generates 7-character Base62 short codes from target URLs."""

    BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    @classmethod
    def generate(cls, target_url: str, salt: int = 0) -> str:
        """Compute deterministic Base62 short code."""
        hasher = hashlib.sha256()
        hasher.update(target_url.encode("utf-8"))
        hasher.update(str(salt).encode("utf-8"))
        digest = hasher.digest()

        # Extract 64-bit integer from first 8 bytes
        num = int.from_bytes(digest[:8], byteorder="big")
        chars = []
        for _ in range(7):
            num, rem = divmod(num, 62)
            chars.append(cls.BASE62_ALPHABET[rem])

        return "".join(reversed(chars))


class UrlShortenerService:
    """Coordinates URL shortening, redirection lookup, and click recording."""

    def __init__(self, url_repo: IUrlRepository, analytics_repo: IAnalyticsRepository):
        self.url_repo = url_repo
        self.analytics_repo = analytics_repo
        # In-memory hot cache of full records for sub-ms redirects
        self._cache: Dict[str, ShortUrl] = {}

    def shorten_url(self, target_url: str, custom_alias: Optional[str] = None) -> ShortUrl:
        """Create a shortened URL record."""
        if custom_alias:
            code = custom_alias.strip()
            existing = self.url_repo.get_by_code(code)
            if existing:
                raise ValueError(f"Custom alias '{code}' is already taken.")
        else:
            salt = 0
            code = ShortCodeGenerator.generate(target_url, salt)
            while True:
                existing = self.url_repo.get_by_code(code)
                if not existing:
                    break
                if existing.target_url == target_url:
                    # Duplicate shorten: this URL already maps to the same code — reuse the
                    # existing record instead of re-inserting (which would violate UNIQUE(code)).
                    self._cache[code] = existing
                    return existing
                salt += 1
                code = ShortCodeGenerator.generate(target_url, salt)

        short_url = ShortUrl(
            id=str(uuid.uuid4()),
            code=code,
            target_url=target_url,
        )
        self.url_repo.save(short_url)
        self._cache[code] = short_url
        return short_url

    def resolve_url(self, code: str, ip: str = "", user_agent: str = "", referrer: str = "") -> Optional[str]:
        """Resolve short code to target URL and record a click event synchronously."""
        # 1. Hot Cache check (full record, so the real url_id is always available)
        url_record = self._cache.get(code)

        if url_record is None:
            url_record = self.url_repo.get_by_code(code)
            if url_record is not None and url_record.is_active:
                self._cache[code] = url_record

        # Never serve unknown or inactive records — even on a cache hit.
        if url_record is None or not url_record.is_active:
            return None

        # 2. Synchronous Click Telemetry
        click_event = ClickEvent(
            id=str(uuid.uuid4()),
            url_id=url_record.id,
            code=code,
            ip_address=ip,
            user_agent=user_agent,
            referrer=referrer,
        )
        self.analytics_repo.record_click(click_event)
        self.url_repo.increment_clicks(code)

        return url_record.target_url

    def get_analytics(self, code: str) -> Dict[str, Any]:
        """Retrieve aggregated analytics for short code."""
        url_record = self.url_repo.get_by_code(code)
        if not url_record:
            raise FileNotFoundError(f"Short code '{code}' not found.")

        stats = self.analytics_repo.get_analytics(code)
        return {
            "code": code,
            "target_url": url_record.target_url,
            "total_clicks": stats.get("total_clicks", url_record.click_count),
            "created_at": url_record.created_at.isoformat(),
            "recent_referrers": stats.get("recent_referrers", []),
        }
