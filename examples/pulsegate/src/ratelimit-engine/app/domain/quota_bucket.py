"""Domain model for QuotaBucket (LLD-001)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class QuotaBucket:
    """Mutable token-bucket state for a tenant."""

    tenant_id: str
    tokens: float
    last_refill_ms: int

    def consume(self, now_ms: int, capacity: int, refill_per_sec: float, cost: int = 1) -> Tuple[bool, int, int]:
        """Refill tokens up to *capacity* and atomically consume *cost* if available."""
        if cost <= 0:
            raise ValueError("cost must be >= 1")
        elapsed_ms = max(0, now_ms - self.last_refill_ms)
        replenished = (elapsed_ms / 1000.0) * refill_per_sec
        self.tokens = min(float(capacity), self.tokens + replenished)
        self.last_refill_ms = max(self.last_refill_ms, now_ms)

        if self.tokens >= cost:
            self.tokens -= cost
            return True, int(math.floor(self.tokens)), 0

        deficit = float(cost) - self.tokens
        retry_after_ms = max(1, int(math.ceil((deficit / refill_per_sec) * 1000.0)))
        return False, int(math.floor(self.tokens)), retry_after_ms
