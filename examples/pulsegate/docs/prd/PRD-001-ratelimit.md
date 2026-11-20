---
id: PRD-001-ratelimit
domain: ratelimit
stage: prd
version: 1.0.0
status: approved
summary: |-
  Deterministic token-bucket API rate limiting for multi-tenant edge gateways.
  Enforces per-tenant burst & sustained RPM quotas with zero-allocation hot paths.
meta: {owner: platform-edge, tier: p0, rfc: "RFC-9457"}
deprecated_at:
upstream_refs: []
downstream_refs: [HLD-001-ratelimit]
---

# PRD-001: PulseGate Edge Rate Limiting

## 1. Personas
| Persona | Role Description |
|---|---|
| Platform Operator | Configures tenant rate policies and inspects quota saturation |
| API Consumer | Receives deterministic `429 Too Many Requests` RFC 9457 responses with `Retry-After` |

## 2. Key Capabilities & User Stories

### US-001-01: Manage Rate Policies
* **Story:** As a Platform Operator, I want to define per-tenant token-bucket capacity and refill rate policies so bursty traffic is absorbed safely.
* **Priority:** `P0`
* **Acceptance Criteria:**
  1. Policy rejects non-positive `capacity` or `refill_per_sec` with `ValueError`.
  2. Policy state persists atomically in SQLite WAL storage.

### US-001-02: Atomic Token Acquisition
* **Story:** As an API Consumer, I want quota checks to decrement tokens atomically and return exact `remaining` and `retry_after_ms` headers.
* **Priority:** `P0`
* **Acceptance Criteria:**
  1. Concurrent requests never over-allocate remaining tokens below `0`.
  2. Rejected requests return `allowed=False` with deterministic `retry_after_ms`.
