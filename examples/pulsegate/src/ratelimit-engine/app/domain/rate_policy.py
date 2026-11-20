"""Domain model for RatePolicy (LLD-001)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RatePolicy:
    """Per-tenant token-bucket capacity and refill rate policy."""

    tenant_id: str
    capacity: int
    refill_per_sec: float
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty")
        if self.capacity <= 0:
            raise ValueError("capacity must be > 0")
        if self.refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be > 0")
