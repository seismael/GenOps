"""
ApiKey domain entity.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class ApiKey:
    """API Authorization Token domain entity."""
    key_id: str
    key_hash: str
    owner_email: str
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    is_revoked: bool = False

    @classmethod
    def create(cls, raw_token: str, owner_email: str) -> Tuple[ApiKey, str]:
        """Factory for generating new hashed API key."""
        key_id = f"key_{hashlib.sha256(raw_token.encode()).hexdigest()[:12]}"
        key_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return cls(key_id=key_id, key_hash=key_hash, owner_email=owner_email), raw_token

    def verify(self, raw_token: str) -> bool:
        """Constant-time token verification."""
        if self.is_revoked:
            return False
        candidate_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return hmac.compare_digest(self.key_hash, candidate_hash)
