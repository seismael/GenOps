---
id: PRD-002-webhooks
domain: webhooks
stage: prd
version: 1.0.0
status: approved
summary: |-
  Reliable HMAC-SHA256 signed webhook fan-out and exponential-backoff retry delivery.
  Reuses LedgerFlow's CloudEvents v1.0.2 envelope standard across service boundaries.
meta: {owner: platform-events, tier: p0}
upstream_refs: []
downstream_refs: [HLD-002-webhooks]
---

# PRD-002: PulseGate Webhook Delivery

## 1. Personas
| Persona | Role Description |
|---|---|
| Webhook Subscriber | Registers HTTPS callback endpoints and verifies `X-PulseGate-Signature` |
| Delivery Worker | Dispatches CloudEvents payloads and records bounded retry attempts |

## 2. Key Capabilities & User Stories

### US-002-01: Register Signed Webhook Endpoints
* **Story:** As a Webhook Subscriber, I want to register HTTPS endpoints with rotating HMAC secrets so forged payloads are rejected.
* **Priority:** `P0`
* **Acceptance Criteria:**
  1. Non-HTTPS URLs (except loopback test targets) are rejected.
  2. Payloads are signed with HMAC-SHA256 using the active endpoint secret.

### US-002-02: Bounded Delivery Retry & Dead-Lettering
* **Story:** As a Delivery Worker, I want failed deliveries to transition through `PENDING` -> `RETRYING` -> `DEAD_LETTERED` after `max_attempts`.
* **Priority:** `P1`
* **Acceptance Criteria:**
  1. Successful `2xx` responses mark `DeliveryAttempt` as `DELIVERED`.
  2. Exceeding `max_attempts` moves the attempt to `DEAD_LETTERED` without unbounded loops.
