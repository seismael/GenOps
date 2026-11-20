"""Domain model for DeliveryAttempt (LLD-002)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryAttempt:
    """Bounded retry delivery attempt for a CloudEvents v1.0.2 payload."""

    attempt_id: str
    endpoint_id: str
    event_id: str
    status: str = "PENDING"
    attempt_count: int = 0
    max_attempts: int = 3

    def record_result(self, status_code: int) -> str:
        """Update status based on HTTP delivery status code."""
        self.attempt_count += 1
        if 200 <= status_code < 300:
            self.status = "DELIVERED"
        elif self.attempt_count >= self.max_attempts:
            self.status = "DEAD_LETTERED"
        else:
            self.status = "RETRYING"
        return self.status
