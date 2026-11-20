"""
ShortUrl domain entity and business invariants.
"""

from __future__ import annotations

import datetime
import ipaddress
import re
import urllib.parse
from dataclasses import dataclass, field


@dataclass
class ShortUrl:
    """Short URL domain aggregate entity."""
    id: str
    code: str
    target_url: str
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    click_count: int = 0
    is_active: bool = True

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Enforce domain invariants specified in LLD-001."""
        if not self.code or not re.match(r"^[a-zA-Z0-9_-]{3,30}$", self.code):
            raise ValueError(f"Invalid short code '{self.code}'. Must be 3-30 alphanumeric characters.")

        parsed = urllib.parse.urlparse(self.target_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Invalid target URL '{self.target_url}'. Must use http or https scheme.")

        # Prevent loopback/private CIDR SSRF attacks as mandated by STRIDE analysis in PRD-001
        hostname = parsed.hostname or ""
        if self._is_prohibited_host(hostname):
            raise ValueError(f"Prohibited target host '{hostname}'. Private and loopback IPs are blocked.")

    @staticmethod
    def _is_prohibited_host(hostname: str) -> bool:
        """Return True for localhost, .local/.internal domains, or non-global/private IP literals."""
        lowered = hostname.lower().rstrip(".")
        if not lowered or lowered == "localhost" or lowered.endswith((".localhost", ".local", ".internal")):
            return True

        try:
            ip = ipaddress.ip_address(lowered)
        except ValueError:
            # Not an IP literal (e.g., a public DNS hostname) — allowed.
            return False

        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped

        # Reject loopback, RFC1918 private, CGNAT (100.64.0.0/10), link-local,
        # unspecified, reserved, and multicast addresses.
        return (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
            or ip.is_multicast
            or not ip.is_global
        )

    def increment_clicks(self) -> None:
        """Increment aggregate click counter."""
        self.click_count += 1
