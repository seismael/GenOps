---
id: ADR-001-distributed-storage-stack
domain: storage
stage: adr
version: 2.0.0
status: accepted
upstream_refs: ["HLD-001-krypton-cluster"]
downstream_refs: ["LLD-001-krypton-cluster"]
tags: [adr, architecture, clickhouse, postgresql, redis, tiered-storage]
---

# ADR-001: Tiered Distributed Storage Architecture (PostgreSQL + Redis Cluster + ClickHouse)

## 1. Context & Problem Statement
At 100,000 requests/sec with billions of monthly clicks, no single monolithic database can simultaneously satisfy:
1. Sub-millisecond read latency for URL redirection.
2. Relational ACID consistency for tenant billing, API keys, and custom alias uniqueness.
3. High-throughput (100k events/sec) analytical ingestion and vectorized OLAP queries across petabytes of historical click telemetry.

## 2. Decision Candidates Evaluated
- **Option A (Accepted):** Tiered Polyglot Architecture:
  - **L1/L2 Cache:** Redis Cluster (Sub-millisecond redirect lookups).
  - **ACID Master:** Managed PostgreSQL (Tenant & URL metadata).
  - **OLAP Analytics:** Distributed ClickHouse (Columnar clickstream data).
- **Option B:** Cassandra / ScyllaDB for all data (Key-value + Wide-column).
- **Option C:** Single Distributed SQL Engine (CockroachDB / TiDB) for both OLTP and OLAP.

## 3. Weighted Multi-Criteria Decision Matrix
*Scale: 1 (Poor) to 5 (Excellent). Weights sum to 100%.*

| Evaluation Vector | Weight | Option A: Tiered (Redis+PG+ClickHouse) | Option B: Cassandra | Option C: Distributed SQL |
|---|---|---|---|---|
| **Sub-ms Read Latency** | 25% | **5** (0.3ms in Redis) | 3 (2.5ms) | 3 (3.0ms) |
| **OLAP Aggregation Speed (1B rows)** | 25% | **5** (Vectorized Columnar < 100ms) | 2 (Full scan slow) | 3 (Row-store bottleneck) |
| **ACID Integrity on Metadata** | 20% | **5** (PostgreSQL standard) | 2 (Eventual consistency) | 5 (Serializable) |
| **Cost Efficiency at Petabyte Scale** | 15% | **5** (ClickHouse 10x compression) | 3 (High disk usage) | 3 (Expensive RAM/CPU) |
| **Operational Maturity** | 15% | **4** (Standard enterprise stacks) | 3 (Complex repair/tombstones)| 4 (Well-understood) |
| **Weighted Total** | **100%** | **4.85 / 5.00** | 2.65 / 5.00 | 3.55 / 5.00 |

## 4. Decision Outcome & Rationale
**Selected Option A (Tiered Polyglot Architecture).**  
ClickHouse provides industry-leading 10x-15x data compression and SIMD-vectorized analytical performance for billion-row clickstream queries, PostgreSQL guarantees strict relational consistency for tenant credentials and billing, and Redis Cluster guarantees < 1ms edge redirection lookups.

## 5. Downstream Directives for LLD & Code
1. `RedirectService` MUST read exclusively from `RedisCachePort` with asynchronous PostgreSQL fallback on cache-miss.
2. `IngestionWorker` MUST bulk-insert click batches into ClickHouse using `ReplacingMergeTree` or `MergeTree` engines.
3. `TenantService` MUST manage API keys and URL records inside PostgreSQL with unique transactional constraints.
