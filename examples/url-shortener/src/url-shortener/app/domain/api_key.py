"""
ApiKey domain entity.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class ApiKey:
    """API Authorization Token domain entity."""
    key_id: str
    key_hash: str
    owner_email: str
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    is_revoked: bool = False

    @classmethod
    def create(cls, raw_token: Optional[str] = None, owner_email: str = "") -> Tuple[ApiKey, str]:
        """Factory for generating a hashed API key (server-generates CSPRNG token if omitted)."""
        if not owner_email or "@" not in owner_email:
            raise ValueError("A valid owner_email is required.")
        token = raw_token.strip() if raw_token else secrets.token_urlsafe(32)
        if len(token) < 8:
            raise ValueError("API token must be at least 8 characters.")
        key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        key_id = f"key_{key_hash[:12]}"
        return cls(key_id=key_id, key_hash=key_hash, owner_email=owner_email.strip()), token

    def verify(self, raw_token: str) -> bool:
        """Constant-time token verification."""
        if self.is_revoked or not raw_token:
            return False
        candidate_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.key_hash, candidate_hash)
