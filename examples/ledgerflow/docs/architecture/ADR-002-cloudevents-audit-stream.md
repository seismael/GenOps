---
id: ADR-002-cloudevents-audit-stream
domain: ledger-core
stage: adr
version: 1.0.0
status: accepted
created_at: 2026-11-20T12:48:00Z
updated_at: 2026-11-20T12:43:08Z
upstream_refs: ["HLD-001-accounts", "HLD-002-transactions"]
downstream_refs: ["LLD-001-accounts", "LLD-002-transactions"]
tags: [ledgerflow, adr, cloudevents, rfc9457, observability]
---

# ADR-002: CNCF CloudEvents v1.0.2 Audit Stream and IETF RFC 9457 Error Contracts

**Status:** `Proposed` <!-- Will promote cleanly on `genops record adr` -->  
**Deciders:** LedgerFlow Architecture Group  
**Date:** 2026-11-20  
**Technical Domain:** `ledger-core` (`accounts`, `transactions`)

---

## 1. Context & Problem Statement
Financial APIs and asynchronous consumers across `HLD-001-accounts` and `HLD-002-transactions` require uniform error reporting and machine-readable event telemetry. Ad-hoc HTTP error payloads (`{"error": "..."}`) confuse client retry policies when differentiating transient lock exhaustion (`503`) from immutable idempotency key mismatches (`409`) or unbalanced debit/credit rejections (`422`). Similarly, inconsistent event payloads impede reconciliation consumers correlating account changes and journal commits back to distributed trace spans.

## 2. Decision Driver Requirements & Constraints
* **Error Interoperability:** Every non-2xx HTTP/domain rejection MUST expose machine-readable `type`, `title`, `status`, `detail`, and optional `instance`/`error_code` metadata.
* **Event Portability:** Every ledger mutation event MUST carry standard CNCF envelope attributes (`specversion`, `id`, `source`, `type`, `datacontenttype`, `time`, `subject`, `data`) and W3C `traceparent`.
* **Runtime Independence:** Envelope builders and exception formatters MUST run cleanly with pure Python stdlib without requiring heavy external SDKs.

## 3. Options Evaluated & Weighted Scoring Matrix

### 3.1 Candidate Descriptions
* **Option A (IETF RFC 9457 Problem Details + CNCF CloudEvents v1.0.2 + W3C `traceparent`):** Standardized error schemas (`application/problem+json`) and CNCF event envelopes published via `EventPublisherPort`.
* **Option B (Proprietary JSON Error Wrapper + Custom Event Dicts):** Minimal ad-hoc `{code, message}` errors and domain-specific event payloads without standard headers.
* **Option C (Unstructured Python Exception Messages + Plaintext Logs):** Rely on FastAPI default HTTPException formatting and unstructured log lines.

### 3.2 Weighted Evaluation Matrix (Scores 1 = Poor, 5 = Excellent)
| Evaluation Criteria | Weight | Option A (RFC 9457 + CloudEvents) | Option B (Custom JSON) | Option C (Unstructured) |
|---|---|---|---|---|
| **Standards Compliance & Interoperability** | 30% | 5 | 2 | 1 |
| **Simplicity & Zero-Dep Implementability** | 25% | 5 | 5 | 5 |
| **Auditability & Distributed Tracing** | 25% | 5 | 3 | 1 |
| **Client Retry Safety & Clarity** | 20% | 5 | 3 | 2 |
| **Weighted Total** | **100%** | **5.00** | **3.15** | **2.20** |

## 4. Decision & Technical Justification
We standardize on **Option A: IETF RFC 9457 `application/problem+json` for all domain/HTTP errors and CNCF CloudEvents v1.0.2 (with W3C `traceparent`) via `EventPublisherPort` for all domain audit events**.

Both standards represent lightweight JSON shapes requiring zero external libraries to construct and validate, while guaranteeing predictable OpenAPI 3.1 contract semantics and end-to-end correlation across downstream settlement, analytics, and alerting pipelines.

### Why Other Options Were Rejected
* **Rejection of Option B (Custom JSON):** Creates unnecessary mapping friction for external treasury integrators and lacks standard extensions (`specversion`, `problem+json` media type).
* **Rejection of Option C (Unstructured Errors):** Fails financial audit requirements and blurs distinction between client bugs (`400`/`422`) and conflict states (`409`).

## 5. Consequences & Trade-Off Analysis

### Positive Consequences (What becomes easier)
* Uniform `to_problem_details()` helper works identically across Python domain exceptions, gateway facades, and FastAPI HTTP exception handlers.
* Downstream consumers can subscribe by standardized `type` prefix (`com.ledgerflow.account.*`, `com.ledgerflow.journal.*`).

### Negative Consequences (What becomes harder & accepted debt)
* Every domain exception subclass must assign an explicit `urn:ledgerflow:problem:<slug>` URI and HTTP status code.

### Neutral / Operational Impact
* `InMemoryEventPublisher` provides deterministic test inspection of emitted CloudEvents while logging structured event summaries via Python `logging`.

## 6. Downstream Directives for LLD & Code (Mandatory Constraints)
1. **Error Taxonomy Contract:** Every domain error MUST inherit from `LedgerProblemError` in `app/domain/exceptions.py` exposing `to_problem_details() -> dict` matching RFC 9457 (`type`, `title`, `status`, `detail`, `instance`, `error_code`).
2. **Event Envelope Contract:** Every account lifecycle mutation and journal post/reversal MUST emit a CloudEvent dict containing `specversion == "1.0"`, valid URI-reference `source`, reverse-DNS `type` (`com.ledgerflow.*`), ISO-8601 UTC `time`, `subject`, `traceparent`, and `data`.
3. **Logging Purity:** Services and adapters MUST use Python stdlib `logging.getLogger(...)` and MUST NEVER call bare `print()`.

## 7. Reversibility & Rollback Plan
* **Abstraction Boundary:** `EventPublisherPort` isolates event emission behind an interface (`publish(event: dict[str, Any]) -> None`).
* **Exit Strategy:** Attach Kafka, Redis Streams, or AWS EventBridge producers as new `EventPublisherPort` adapters without changing service or domain modules.

## 8. Related Decisions
* Upstream: `HLD-001-accounts.md`, `HLD-002-transactions.md`
* Downstream: `LLD-001-accounts.md`, `LLD-002-transactions.md`
