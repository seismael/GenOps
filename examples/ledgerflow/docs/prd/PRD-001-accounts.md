---
id: PRD-001-accounts
domain: accounts
stage: prd
version: 1.0.0
status: approved
created_at: 2026-11-20T12:40:00Z
updated_at: 2026-11-20T12:39:44Z
upstream_refs: []
downstream_refs: ["HLD-001-accounts"]
tags: [accounts, ledgerflow, prd, requirements]
---

# LedgerFlow Accounts — Product Requirements Document

## 1. Executive Summary & Problem Statement
LedgerFlow provides an auditable, double-entry financial ledger backend for fintech platforms, marketplace wallets, and treasury operations. Without dedicated account governance, teams scatter mutable balance counters across relational tables, leading to silent rounding drift, unauthorized overdrafts, and broken reconciliation audits. The `accounts` domain establishes strictly typed ledger accounts, multi-currency minor-unit precision, and deterministic lifecycle policies (`ACTIVE` -> `FROZEN` -> `CLOSED`).

## 2. Business Goals & Measurable North Star
| Metric | Baseline | Target | Measurement Method | Target Timeline |
|---|---|---|---|---|
| Primary (North Star): Balance Discrepancy Rate | 0.42% manual journal reconciliation mismatches | 0.00% discrepancy across daily close checks | Automated SQLite double-entry invariant checker & RTM verification | At v1.0 launch |
| Secondary Metric: Account Read/Provisioning Latency | 180ms p95 legacy accounting service | < 15ms p95 lookup, < 35ms p95 account creation | End-to-end API latency histograms | At v1.0 launch |

## 3. User Personas & Permissions
| Persona | Role Description | Key Motivations | Operational Constraints |
|---|---|---|---|
| Treasury Admin | Configures ledger policies, freezes anomalous accounts | Zero silent balance mutation, full audit history | Authenticated via tenant admin scope; cannot delete ledger history |
| Platform Integrator | Backend payment service opening wallets & reading balances | Deterministic IDs, strict currency & policy validation | Scoped to explicit `accounts:write` and `accounts:read` privileges |

## 4. Key Capabilities & User Stories (ISO/IEC/IEEE 29148 & BDD Format)

### Requirements Traceability Summary
| Req ID | I want to... | Priority | Verification Method | Acceptance Reference |
|---|---|---|---|---|
| `US-001-01` | Open a strongly typed ledger account bound to an ISO 4217 currency and normal balance | `P0` | `Unit & API Test` | `HLD-001-accounts, LLD-001-accounts` |
| `US-001-02` | Enforce LedgerPolicy limits (overdraft allowance and single-posting cap) per account class | `P0` | `Unit & API Test` | `HLD-001-accounts, LLD-001-accounts` |
| `US-001-03` | Transition account lifecycle status (`ACTIVE`, `FROZEN`, `CLOSED`) safely with zero-balance close guard | `P1` | `Unit & API Test` | `HLD-001-accounts, LLD-001-accounts` |

### US-001-01: Typed Ledger Account Provisioning
* **Story:** As a `Platform Integrator`, I want to create an immutable-currency ledger account with an explicit normal balance (`DEBIT` or `CREDIT`) and integer minor-unit balance so that floating-point rounding never corrupts financial totals.
* **Priority:** `P0`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Happy Path):**
    * **Given:** A valid request specifying `code: "CASH-USD-001"`, `name: "Operating Cash"`, `account_type: "ASSET"`, and `currency: "USD"`.
    * **When:** The client submits `POST /api/v1/accounts`.
    * **Then:** HTTP `201 Created` returns the provisioned `Account` with `status: "ACTIVE"`, `balance_minor: 0`, and `normal_balance: "DEBIT"`.
  * **Scenario 2 (Edge Case / Validation Rejection):**
    * **Given:** A payload requesting unsupported currency `"XYZ"` or invalid account code containing whitespace.
    * **When:** The client submits `POST /api/v1/accounts`.
    * **Then:** HTTP `400 Bad Request` returns RFC 9457 `application/problem+json` explaining the constraint violation.

### US-001-02: LedgerPolicy Enforcement
* **Story:** As a `Treasury Admin`, I want every account linked to a `LedgerPolicy` specifying overdraft allowance and maximum single-posting minor-unit cap so that misconfigured integrations cannot drain custodial balances.
* **Priority:** `P0`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Happy Path):**
    * **Given:** A `LedgerPolicy` restricting `allow_overdraft: false` and `max_posting_minor: 500000` ($5,000.00).
    * **When:** `GET /api/v1/accounts/{account_id}` or transaction policy check queries the account.
    * **Then:** The active policy bounds are returned deterministically and enforced on debits/credits.
  * **Scenario 2 (Policy Breach):**
    * **Given:** An account policy with `max_posting_minor: 1000` and `allow_overdraft: false`.
    * **When:** A policy check evaluates an overdraft or oversized posting.
    * **Then:** The policy guard raises a structured domain policy violation mapped to HTTP `422 Unprocessable Content`.

### US-001-03: Lifecycle Transitions & Safe Closure
* **Story:** As a `Treasury Admin`, I want to freeze suspicious accounts and close settled accounts only at zero balance so that in-flight reconciliations are never orphaned.
* **Priority:** `P1`
* **Acceptance Criteria (Given-When-Then):**
  * **Scenario 1 (Freeze Account):**
    * **Given:** An `ACTIVE` account with `balance_minor: 25000`.
    * **When:** `PATCH /api/v1/accounts/{account_id}/status` sets `status: "FROZEN"`.
    * **Then:** HTTP `200 OK` records `FROZEN`, blocking new debit/credit postings until unfrozen.
  * **Scenario 2 (Non-Zero Closure Guard):**
    * **Given:** An account with `balance_minor: 100`.
    * **When:** A caller attempts `status: "CLOSED"`.
    * **Then:** HTTP `409 Conflict` returns RFC 9457 Problem Details refusing closure until balance equals `0`.

## 5. Scope Boundaries

### In Scope (v1 MVP)
* Single-tenant or tenant-tagged chart-of-accounts management (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`).
* Integer minor-unit accounting (`USD`, `EUR`, `GBP`) eliminating IEEE-754 floating-point drift.
* Named `LedgerPolicy` rules (`allow_overdraft`, `max_posting_minor`) attached at creation or update.

### Anti-Features (Explicitly Out of Scope)
* Multi-currency FX spot conversion and automatic gain/loss revaluation postings (handled externally in v2).
* Hard-deletion of closed accounts or balance history rows (regulatory immutability forbids physical deletes).

## 6. Non-Functional Requirements (NFRs) & SLO Targets
| Category | Requirement Specification | Strict Target Bound |
|---|---|---|
| **Latency** | Account creation and point lookup latency | $p99 < 40\text{ms}$, $p50 < 8\text{ms}$ |
| **Correctness** | Integer minor-unit representation across API and storage | $100\%$ zero floating-point storage |
| **Availability** | Single-node SQLite WAL resilient local read/write availability | $99.95\%$ scheduled uptime |
| **Auditability** | Every account state change stamped with UTC ISO-8601 timestamp | $100\%$ immutable event trail |

## 7. Assumptions, Dependencies & Risks

### Strategic Assumptions
* Upstream callers treat all currency amounts as signed/unsigned 64-bit integer minor units (e.g., `1050` = `$10.50 USD`).

### System Dependencies
* `transactions` domain (`PRD-002-transactions`) reads `Account` status, `LedgerPolicy`, and performs locked atomic balance updates within the shared SQLite ledger transaction boundary.

### Risk & Mitigation Matrix (STRIDE & Operational)
| Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|
| Tampering or direct SQL balance updates bypassing ledger rules | Critical | Low | Encapsulate writes solely through `transactions-service` double-entry commits and enforce parameterized SQL adapters |
| Closing an account with unsettled funds | High | Med | Enforce deterministic domain invariant `balance_minor == 0` prior to `CLOSED` transition |
