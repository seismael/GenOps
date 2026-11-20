---
id: PRD-002-transactions
domain: transactions
stage: prd
version: 1.0.0
status: approved
created_at: 2026-11-20T12:40:00Z
updated_at: 2026-11-20T12:39:44Z
upstream_refs: []
downstream_refs: ["HLD-002-transactions"]
tags: [transactions, ledgerflow, prd, requirements, double-entry]
---

# LedgerFlow Transactions — Product Requirements Document

## 1. Executive Summary & Problem Statement
The `transactions` domain executes atomic, idempotent double-entry journal postings across LedgerFlow accounts. Distributed payment workflows routinely suffer duplicate webhook retries, partial transfer commits on crashes, and unbalanced debits/credits. `transactions` enforces zero-sum balanced postings inside ACID transactions, guarantees idempotency via client `idempotency_key`, and emits CNCF CloudEvents v1.0.2 telemetry for every committed journal entry.

## 2. Business Goals & Measurable North Star
| Metric | Baseline | Target | Measurement Method | Target Timeline |
|---|---|---|---|---|
| Primary (North Star): Unbalanced Journal Rate | 1 in 2,500 manual/legacy transfers fail mid-flight | 0 unbalanced commits (`SUM(debit) == SUM(credit)` 100%) | Transactional constraint + automated unit/property tests | At v1.0 launch |
| Secondary Metric: Duplicate Retry Safety | Retried webhooks cause double charges 0.8% of the time | 100% deterministic idempotent replay on duplicate `idempotency_key` | Idempotency conflict & payload-hash check suite | At v1.0 launch |

## 3. User Personas & Permissions
| Persona | Role Description | Key Motivations | Operational Constraints |
|---|---|---|---|
| Payment Orchestrator | Submits multi-leg transfer/settlement journals with retry safety | Idempotent retries, clear RFC 9457 error taxonomy | Must supply unique `idempotency_key` and positive minor-unit amounts |
| Financial Auditor | Queries immutable journal entries and reverses erroneous postings | Reversal audit link instead of mutation/deletion | Read-only inspection + authorized offsetting reversal creation only |

## 4. Key Capabilities & User Stories (ISO/IEC/IEEE 29148 & BDD Format)

### Requirements Traceability Summary
| Req ID | I want to... | Priority | Verification Method | Acceptance Reference |
|---|---|---|---|---|
| `US-002-01` | Commit atomic zero-sum double-entry `JournalEntry` batches across accounts | `P0` | `Unit & API Test` | `HLD-002-transactions, LLD-002-transactions` |
| `US-002-02` | Enforce idempotent `idempotency_key` deduplication and detect payload mismatches | `P0` | `Unit & API Test` | `HLD-002-transactions, LLD-002-transactions` |
| `US-002-03` | Create offsetting reversal journals for posted entries and emit CloudEvents v1.0.2 envelopes | `P1` | `Unit & API Test` | `HLD-002-transactions, LLD-002-transactions` |

### US-002-01: Atomic Zero-Sum Journal Posting
* **Story:** As a `Payment Orchestrator`, I want to post a multi-leg `JournalEntry` containing `PostingLine` debits and credits that either all commit atomically with updated account balances or roll back completely so that books never go out of balance.
* **Priority:** `P0`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Happy Path):**
    * **Given:** Two `ACTIVE` USD accounts (`cash` and `revenue`) and a journal batch debiting `cash` `10000` and crediting `revenue` `10000`.
    * **When:** `POST /api/v1/journals` executes within a serialized `BEGIN IMMEDIATE` transaction.
    * **Then:** HTTP `201 Created` returns the persisted `JournalEntry` (`status: "POSTED"`), balances update atomically, and a `com.ledgerflow.journal.posted` CloudEvent is emitted.
  * **Scenario 2 (Unbalanced or Frozen Account Failure):**
    * **Given:** Posting lines where total debits (`10000`) do not equal credits (`9500`), or a participating account is `FROZEN`.
    * **When:** `POST /api/v1/journals` validates invariants before committing.
    * **Then:** HTTP `422 Unprocessable Content` returns RFC 9457 Problem Details and zero account rows are modified.

### US-002-02: Idempotent Retry & Payload Conflict Protection
* **Story:** As a `Payment Orchestrator`, I want retries sharing the same `idempotency_key` and identical body to return the original committed `JournalEntry`, while differing bodies with a reused key return HTTP `409 Conflict`, so that network retries never double-post funds.
* **Priority:** `P0`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Idempotent Replay):**
    * **Given:** A journal previously posted with `idempotency_key: "pay-991"` and canonical SHA-256 request digest `D1`.
    * **When:** The client retries `POST /api/v1/journals` with the same key and digest `D1`.
    * **Then:** HTTP `200 OK` returns the exact previously committed `JournalEntry` without incrementing balances again.
  * **Scenario 2 (Idempotency Key Reuse Mismatch):**
    * **Given:** A previously committed entry for `"pay-991"` with digest `D1`.
    * **When:** A client submits `"pay-991"` with modified posting amounts (digest `D2 != D1`).
    * **Then:** HTTP `409 Conflict` returns RFC 9457 Problem Details alerting to key reuse conflict.

### US-002-03: Immutable Journal Reversals & Audit Event Streaming
* **Story:** As a `Financial Auditor`, I want to issue an offsetting reversal `JournalEntry` linking `reverses_journal_id` to an existing entry without deleting history so that corrections preserve a cryptographic-grade audit trail.
* **Priority:** `P1`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Happy Path):**
    * **Given:** A posted `JournalEntry` `J1` and a reversal request referencing `J1`.
    * **When:** `POST /api/v1/journals/{journal_id}/reverse` executes.
    * **Then:** HTTP `201 Created` records an inverted-direction `JournalEntry` `J2` (`reverses_journal_id: J1.id`), restores prior balances, and emits `com.ledgerflow.journal.reversed`.
  * **Scenario 2 (Duplicate Reversal Guard):**
    * **Given:** A journal `J1` already reversed by `J2`.
    * **When:** Another reversal attempt targets `J1`.
    * **Then:** HTTP `409 Conflict` refuses double reversal.

## 5. Scope Boundaries

### In Scope (v1 MVP)
* N-leg balanced double-entry journals (`len(lines) >= 2`, all legs sharing currency per currency-balanced ledger).
* Strict SHA-256 canonical request hashing for idempotency verification.
* Standardized CloudEvents v1.0.2 domain event emission to in-process / pluggable event sink port.

### Anti-Features (Explicitly Out of Scope)
* Deleting or mutating posted `JournalEntry` or `PostingLine` records (compensating reversal entries only).
* Asynchronous scheduled/recurring standing orders (caller orchestration schedules externally).

## 6. Non-Functional Requirements (NFRs) & SLO Targets
| Category | Requirement Specification | Strict Target Bound |
|---|---|---|
| **Consistency** | Strict serializable / immediate-lock ACID transaction per journal | $100\%$ ACID zero partial commits |
| **Latency** | Journal commit latency (2-4 posting lines) | $p99 < 50\text{ms}$, $p50 < 12\text{ms}$ |
| **Idempotency Window** | Deterministic deduplication lookup by `idempotency_key` | $100\%$ retained across ledger lifetime |
| **Observability** | Structured W3C `traceparent` + CNCF CloudEvents v1.0.2 envelope | $100\%$ of posted and reversed journals |

## 7. Assumptions, Dependencies & Risks

### Strategic Assumptions
* Concurrent writers share one SQLite WAL database configured with `busy_timeout = 5000` and `BEGIN IMMEDIATE` write serialization.

### System Dependencies
* `accounts` domain (`PRD-001-accounts`) owns the `accounts` and `ledger_policies` tables read and updated under transaction lock.

### Risk & Mitigation Matrix (STRIDE & Operational)
| Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|
| Concurrent overdraft race condition on simultaneous debits | Critical | High | Acquire SQLite `BEGIN IMMEDIATE` write lock before reading balances and evaluating `LedgerPolicy` |
| Unbounded integer overflow or negative line amount injection | High | Low | Validate `amount_minor > 0` in domain entities and cap single posting via `LedgerPolicy.max_posting_minor` |
