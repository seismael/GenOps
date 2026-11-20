---
id: HLD-002-webhooks
domain: webhooks
stage: hld
version: 1.0.0
status: approved
upstream_refs: [PRD-002-webhooks, ext://ledger/ADR-002-cloudevents-audit-stream]
downstream_refs: [ADR-001-token-bucket-sqlite, LLD-002-webhooks]
---

# HLD-002: PulseGate Webhook Delivery Topology

## 1. System Topology
```mermaid
flowchart LR
  Producer["Domain Event"] --> Dispatcher["webhook-dispatcher"]
  Dispatcher --> Signer["HMAC-SHA256 Signer"]
  Signer --> Endpoint["Subscriber HTTPS Endpoint"]
```

## 2. Cross-Project Federation
* Reuses `ext://ledger/ADR-002-cloudevents-audit-stream` for CNCF CloudEvents v1.0.2 envelope headers (`specversion`, `id`, `source`, `type`) and RFC 9457 error formatting.

## 3. Technology Decisions
| Concern | Candidate | Status |
|---|---|---|
| Delivery State Persistence | SQLite WAL | Needs ADR |
