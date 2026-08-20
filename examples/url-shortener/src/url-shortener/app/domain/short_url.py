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
        """Return True for localhost or loopback/private/link-local IP literals."""
        lowered = hostname.lower()
        if lowered == "localhost":
            return True

        try:
            ip = ipaddress.ip_address(lowered)
        except ValueError:
            # Not an IP literal (e.g., a public DNS hostname) — allowed.
            return False

        if ip.version == 4:
            octets = [int(part) for part in str(ip).split(".")]
            a, b = octets[0], octets[1]
            if a == 127:                        # 127.0.0.0/8 loopback
                return True
            if a == 10:                         # 10.0.0.0/8 RFC1918
                return True
            if a == 192 and b == 168:           # 192.168.0.0/16 RFC1918
                return True
            if a == 172 and 16 <= b <= 31:      # 172.16.0.0/12 RFC1918
                return True
            if a == 169 and b == 254:           # 169.254.0.0/16 link-local
                return True
            if a == 0 and all(o == 0 for o in octets):  # 0.0.0.0 unspecified
                return True
            return False

        # IPv6: ::1 loopback, fe80::/10 link-local, fc00::/7 unique-local
        return ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_unspecified

    def increment_clicks(self) -> None:
        """Increment aggregate click counter."""
        self.click_count += 1
