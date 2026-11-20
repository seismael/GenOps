---
id: HLD-001-ratelimit
domain: ratelimit
stage: hld
version: 1.0.0
status: approved
upstream_refs: [PRD-001-ratelimit]
downstream_refs: [ADR-001-token-bucket-sqlite, LLD-001-ratelimit]
---

# HLD-001: PulseGate Edge Rate-Limiting Topology

## 1. System Topology
```mermaid
flowchart LR
  Client["API Consumer"] --> Edge["ratelimit-engine"]
  Edge --> Store["SQLite WAL Quota Store"]
```

## 2. Technology Decisions
| Concern | Candidate | Status |
|---|---|---|
| Atomic Token-Bucket Persistence | SQLite WAL + BEGIN IMMEDIATE | Needs ADR |
| Error Contract | RFC 9457 Problem Details | Adopted |
