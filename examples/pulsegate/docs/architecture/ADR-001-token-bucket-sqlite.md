---
id: ADR-001-token-bucket-sqlite
domain: core
stage: adr
version: 1.0.0
status: accepted
upstream_refs: [HLD-001-ratelimit, HLD-002-webhooks]
downstream_refs: [LLD-001-ratelimit, LLD-002-webhooks]
---

# ADR-001: Atomic SQLite WAL Persistence for Quota & Delivery State

## 1. Context & Decision
Use zero-dependency Python `sqlite3` in `WAL` journal mode with `BEGIN IMMEDIATE` transactions for both token-bucket quota checks and webhook delivery state transitions.

## 2. Downstream Directives
- Enable `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` on every connection.
- Perform token refill and consumption inside a single `BEGIN IMMEDIATE` transaction.
- Represent timestamps as UTC ISO-8601 strings and token counts as bounded floats/integers.
