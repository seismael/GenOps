---
id: ADR-002-event-streaming-engine
domain: streaming
stage: adr
version: 2.0.0
status: accepted
upstream_refs: ["HLD-001-krypton-cluster"]
downstream_refs: ["LLD-001-krypton-cluster"]
tags: [adr, architecture, kafka, streaming, message-bus, redpanda]
---

# ADR-002: Apache Kafka / Redpanda Distributed Event Streaming Architecture

## 1. Context & Problem Statement
Redirect workers must emit up to 100,000 click events per second without adding blocking latency to HTTP responses or risking data loss during database ingestion spikes or downstream maintenance windows.

## 2. Decision Candidates Evaluated
- **Option A (Accepted):** Apache Kafka / Redpanda Distributed Commit Log with consumer groups.
- **Option B:** NATS JetStream Distributed Messaging.
- **Option C:** RabbitMQ with AMQP queues.

## 3. Weighted Multi-Criteria Decision Matrix
*Scale: 1 (Poor) to 5 (Excellent). Weights sum to 100%.*

| Evaluation Vector | Weight | Option A: Kafka / Redpanda | Option B: NATS JetStream | Option C: RabbitMQ |
|---|---|---|---|---|
| **Sustained Throughput (>100k msg/s)** | 35% | **5** (Million msg/s disk append) | 5 (Very fast) | 2 (Queue lock contention) |
| **Partition Replayability & Durability** | 25% | **5** (7-day persistent log replay) | 4 (Good replay) | 1 (Ack deletes message) |
| **Backpressure Decoupling** | 20% | **5** (Pull-based consumer groups) | 4 (Pull-based) | 3 (Push memory pressure) |
| **Ecosystem & ClickHouse Ingestion** | 20% | **5** (Native ClickHouse Kafka Engine) | 2 (Custom connector) | 2 (Custom connector) |
| **Weighted Total** | **100%** | **4.90 / 5.00** | 4.05 / 5.00 | 2.05 / 5.00 |

## 4. Decision Outcome & Rationale
**Selected Option A (Apache Kafka / Redpanda).**  
Kafka's immutable append-only commit log and native ClickHouse integration allows seamless asynchronous clickstream ingestion with zero message loss and multi-day replayability.

## 5. Downstream Directives for LLD & Code
1. `RedirectService` MUST use an asynchronous non-blocking Kafka producer with linger ms = 5 and batch size = 16KB.
2. Kafka topics MUST be partitioned using `hash(code) + salt` across 64 partitions to prevent partition skew.
3. Ingestion workers MUST commit offsets only after ClickHouse batch insert confirmation.
