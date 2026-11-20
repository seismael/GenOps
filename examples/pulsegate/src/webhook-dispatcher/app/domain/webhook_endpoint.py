"""Domain model for WebhookEndpoint (LLD-002)."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class WebhookEndpoint:
    """Registered webhook subscriber endpoint with HMAC-SHA256 signing."""

    endpoint_id: str
    url: str
    secret: str
    active: bool = True

    def __post_init__(self) -> None:
        if not self.endpoint_id or not self.endpoint_id.strip():
            raise ValueError("endpoint_id must be non-empty")
        if len(self.secret) < 16:
            raise ValueError("secret must be >= 16 characters")
        parsed = urlparse(self.url)
        is_loopback = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
            raise ValueError(f"Webhook URL must use HTTPS (got '{self.url}')")

    def sign_payload(self, payload_bytes: bytes) -> str:
        """Compute hex HMAC-SHA256 signature header value."""
        return "sha256=" + hmac.new(self.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
