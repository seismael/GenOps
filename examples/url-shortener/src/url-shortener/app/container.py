"""
Dependency Injection Container: wires repository adapters & application services.
"""

from __future__ import annotations

import os
from typing import Optional

from app.adapters.persistence.sqlite_repository import (
    SqliteAnalyticsRepository,
    SqliteApiKeyRepository,
    SqliteDatabase,
    SqliteUrlRepository,
)
from app.services.short_url_service import UrlShortenerService


class ApplicationContainer:
    """Dependency injection container."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.getenv("KRYPTON_DB_PATH", "krypton.db")
        self.db = SqliteDatabase(db_path)
        self.url_repo = SqliteUrlRepository(self.db)
        self.analytics_repo = SqliteAnalyticsRepository(self.db)
        self.api_key_repo = SqliteApiKeyRepository(self.db)
        self.url_service = UrlShortenerService(self.url_repo, self.analytics_repo)
