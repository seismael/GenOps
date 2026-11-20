---
id: ADR-001-sqlite-double-entry-ledger
domain: ledger-core
stage: adr
version: 1.0.0
status: accepted
created_at: 2026-11-20T12:48:00Z
updated_at: 2026-11-20T12:43:08Z
upstream_refs: ["HLD-001-accounts", "HLD-002-transactions"]
downstream_refs: ["LLD-001-accounts", "LLD-002-transactions"]
tags: [ledgerflow, adr, sqlite, persistence, acid, double-entry]
---

# ADR-001: SQLite WAL Mode with Integer Minor Units for Double-Entry Persistence

**Status:** `Proposed` <!-- Will promote cleanly on `genops record adr` -->  
**Deciders:** LedgerFlow Architecture Group  
**Date:** 2026-11-20  
**Technical Domain:** `ledger-core` (`accounts`, `transactions`)

---

## 1. Context & Problem Statement
Both `HLD-001-accounts` and `HLD-002-transactions` require strict ACID commit semantics across `Account`, `LedgerPolicy`, `JournalEntry`, `PostingLine`, and `IdempotencyRecord` entities. A journal posting touching 2-10 accounts must verify account statuses (`ACTIVE`), validate overdraft and single-posting limits, update account balances, insert immutable journal lines, and store the idempotency request digest atomically. Additionally, LedgerFlow must execute deterministically in offline developer workstations, CI runners, and single-binary containers without external database daemon setup while maintaining high concurrent read throughput.

## 2. Decision Driver Requirements & Constraints
* **Atomicity & Isolation:** Multi-table balance updates and journal inserts must commit all-or-nothing under serialized write locking.
* **Precision:** Zero floating-point representation anywhere in storage or domain calculations; exact 64-bit signed integers in minor currency units (`INTEGER`).
* **Zero-Ops Portability:** Must run out-of-the-box with Python stdlib `sqlite3` while retaining hexagonal port abstractions for future PostgreSQL migration.
* **Throughput Target:** $\ge 2,000\text{ reads/sec}$ concurrent reads via WAL snapshots and $< 15\text{ms}$ serialized write commits.

## 3. Options Evaluated & Weighted Scoring Matrix

### 3.1 Candidate Descriptions
* **Option A (SQLite 3 WAL Mode + `BEGIN IMMEDIATE` + Integer Minor Units):** Built-in stdlib transactional relational store configured with `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`, and `busy_timeout=5000`.
* **Option B (Dedicated PostgreSQL 16 Cluster):** External multi-node relational engine with `SERIALIZABLE` isolation and connection pooling (`asyncpg`).
* **Option C (Append-Only JSONL / EventStoreDB Only):** Pure log stream storing only events and reconstructing account balances in memory on startup.

### 3.2 Weighted Evaluation Matrix (Scores 1 = Poor, 5 = Excellent)
| Evaluation Criteria | Weight | Option A (SQLite WAL) | Option B (PostgreSQL) | Option C (EventStore Log) |
|---|---|---|---|---|
| **Transactional Correctness & ACID** | 25% | 5 | 5 | 4 |
| **Simplicity & Developer Ergonomics** | 25% | 5 | 3 | 3 |
| **Zero-Ops & Test Determinism** | 25% | 5 | 2 | 3 |
| **Ecosystem Maturity & Tooling** | 15% | 5 | 5 | 4 |
| **Total Cost of Ownership (TCO)** | 10% | 5 | 3 | 3 |
| **Weighted Total** | **100%** | **5.00** | **3.55** | **3.35** |

## 4. Decision & Technical Justification
We adopt **Option A: SQLite 3 in Write-Ahead Logging (WAL) mode with explicit `BEGIN IMMEDIATE` write transactions and integer minor-unit columns**.

SQLite WAL enables non-blocking concurrent readers alongside deterministic, deadlock-free writer serialization (`BEGIN IMMEDIATE` acquires the write lock upfront rather than promoting mid-transaction and failing with `SQLITE_BUSY` deadlocks). Combined with Python's standard library `sqlite3` driver and hexagonal `RepositoryPort` interfaces, every service and integration test executes with zero external infrastructure dependencies.

### Why Other Options Were Rejected
* **Rejection of Option B (PostgreSQL):** Introduces mandatory daemon provisioning, external network latency, and credential management overhead unwarranted for an embeddable, standalone ledger service example.
* **Rejection of Option C (Event-Only Log):** Queries checking overdraft policies across thousands of transactions would degrade linearly without materialized read state, duplicating relational indexing work poorly.

## 5. Consequences & Trade-Off Analysis

### Positive Consequences (What becomes easier)
* Zero external database containers or driver wheels required in unit, integration, or CI runs.
* Deterministic `FOREIGN KEY` and `CHECK` constraints protect referential integrity even at storage level.

### Negative Consequences (What becomes harder & accepted debt)
* Horizontal multi-writer scaling across separate physical hosts is constrained to single primary writer throughput unless migrated to Option B.
* Requires explicit `.close()` lifecycle discipline in connections so Windows file locks and Python `ResourceWarning` never occur.

### Neutral / Operational Impact
* Schema DDL initializes idempotently (`CREATE TABLE IF NOT EXISTS`) upon database adapter startup.

## 6. Downstream Directives for LLD & Code (Mandatory Constraints)
1. **Schema & Types:** All money columns (`balance_minor`, `amount_minor`, `max_posting_minor`) MUST be SQLite `INTEGER` minor units; `FLOAT`/`REAL` types are forbidden for monetary quantities.
2. **Parameterized SQL & Lock Discipline:** All persistence adapters MUST use bound `?` query parameters (zero string interpolation) and wrap multi-row ledger postings in explicit `BEGIN IMMEDIATE` ... `COMMIT` / `ROLLBACK`.
3. **Hexagonal Abstraction & Lifecycle:** Business services MUST depend solely on `*RepositoryPort` protocols (`app/ports/repository.py`) and adapters MUST expose explicit `.close()` cleanup hooks.

## 7. Reversibility & Rollback Plan
* **Abstraction Boundary:** All SQL statements reside strictly inside `app/adapters/persistence/`. Domain entities and application services never import `sqlite3`.
* **Exit Strategy:** Swap `SqliteAccountsDatabase` / `SqliteLedgerDatabase` adapters for PostgreSQL (`psycopg` / `asyncpg`) implementations behind existing port protocols without altering domain or router logic.

## 8. Related Decisions
* Upstream: `HLD-001-accounts.md`, `HLD-002-transactions.md`
* Downstream: `LLD-001-accounts.md`, `LLD-002-transactions.md`
