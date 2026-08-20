---
id: ADR-001-storage-engine
domain: storage
stage: adr
version: 1.0.0
status: accepted
upstream_refs: ["HLD-001-url-shortener"]
downstream_refs: ["LLD-001-url-shortener"]
tags: [adr, architecture, storage, sqlite, persistence]
---

# ADR-001: Storage Engine Selection for High-Throughput URL Shortening

## 1. Context & Problem Statement
The URL shortener gateway requires persistent storage for URL mappings, click analytics records, and API authorization keys. The storage solution must deliver sub-millisecond local reads for redirect queries, high write concurrency for clickstream logging, zero external operational dependencies in local/standalone deployments, and a clean migration path to distributed PostgreSQL for clustered enterprise deployments.

## 2. Decision Candidates Evaluated
- **Option A (Accepted):** Embedded SQLite with Write-Ahead Logging (WAL) mode + Clean Repository Port abstraction.
- **Option B:** External PostgreSQL Database Server.
- **Option C:** Redis In-Memory Key-Value Store with AOF persistence.

## 3. Weighted Multi-Criteria Decision Matrix
*Scale: 1 (Poor) to 5 (Excellent). Weights sum to 100%.*

| Evaluation Vector | Weight | Option A: SQLite WAL | Option B: PostgreSQL | Option C: Redis AOF |
|---|---|---|---|---|
| **Read Latency (Sub-ms)** | 25% | **5** (0.1ms in-proc) | 3 (2.0ms network) | 5 (0.3ms memory) |
| **Zero Operational Overhead** | 25% | **5** (Zero daemon) | 2 (Requires DB ops) | 3 (Requires daemon) |
| **Write Concurrency & WAL** | 20% | **4** (WAL multi-reader) | 5 (MVCC distributed) | 4 (Single-threaded) |
| **Relational Query Flexibility** | 15% | **5** (Full SQL analytics) | 5 (Full SQL analytics) | 2 (Limited secondary idx) |
| **Total Cost of Ownership (TCO)** | 15% | **5** ($0 infra cost) | 3 (Server provision) | 3 (RAM cost) |
| **Weighted Total** | **100%** | **4.80 / 5.00** | 3.35 / 5.00 | 3.55 / 5.00 |

## 4. Decision Outcome & Rationale
**Selected Option A (SQLite in WAL mode).**  
SQLite provides zero-dependency operational simplicity, embedded sub-millisecond in-process query latency, full SQL analytical aggregation power for clickstream metrics, and robust crash resilience via Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`).

## 5. Consequences & Reversibility Strategy
- **Positive Consequences:** Single-binary deployment with zero external network hops or connection pool management.
- **Negative Consequences:** Multi-node horizontal scaling requires migrating database storage to distributed PostgreSQL.
- **Reversibility Plan:** All database interactions are decoupled through an abstract `UrlRepositoryPort` and `AnalyticsRepositoryPort` interface. Swapping SQLite for PostgreSQL or asyncpg requires zero modifications to domain or routing layers.

## 6. Downstream Directives for LLD & Code
1. Database initialization MUST execute `PRAGMA journal_mode=WAL;` and `PRAGMA foreign_keys=ON;`.
2. All tables MUST define explicit `PRIMARY KEY` and `INDEX` on lookup columns (`code`, `created_at`).
3. Domain services MUST interact strictly via repository ports (`IUrlRepository`, `IAnalyticsRepository`), isolating SQL queries inside the adapter layer.
