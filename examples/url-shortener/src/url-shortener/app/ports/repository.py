"""
Secondary Ports: Storage repository interfaces for Clean Architecture decoupling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.domain.api_key import ApiKey
from app.domain.click_event import ClickEvent
from app.domain.short_url import ShortUrl


class IUrlRepository(ABC):
    """Abstract port for URL mapping storage."""

    @abstractmethod
    def save(self, url: ShortUrl) -> None:
        """Persist or update a ShortUrl record."""
        pass

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[ShortUrl]:
        """Retrieve a ShortUrl record by its code."""
        pass

    @abstractmethod
    def increment_clicks(self, code: str) -> None:
        """Increment click count for a short code."""
        pass


class IAnalyticsRepository(ABC):
    """Abstract port for clickstream event storage."""

    @abstractmethod
    def record_click(self, event: ClickEvent) -> None:
        """Store clickstream telemetry event."""
        pass

    @abstractmethod
    def get_analytics(self, code: str) -> Dict[str, Any]:
        """Aggregate click counts, unique visitors, and referrers for code."""
        pass


class IApiKeyRepository(ABC):
    """Abstract port for API key authentication storage."""

    @abstractmethod
    def save(self, api_key: ApiKey) -> None:
        """Persist API key metadata."""
        pass

    @abstractmethod
    def get_by_id(self, key_id: str) -> Optional[ApiKey]:
        """Retrieve API key by key_id."""
        pass

    @abstractmethod
    def verify_token(self, token: str) -> bool:
        """Check if raw token matches any active API key."""
        pass
