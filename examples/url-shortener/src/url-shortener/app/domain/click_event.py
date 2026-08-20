"""
ClickEvent domain entity.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass
class ClickEvent:
    """Clickstream analytics event entity."""
    id: str
    url_id: str
    code: str
    timestamp: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    ip_address: str = ""
    user_agent: str = ""
    referrer: str = ""
