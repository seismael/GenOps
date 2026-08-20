---
id: ADR-003-language-runtime-selection
domain: runtime
stage: adr
version: 2.0.0
status: accepted
upstream_refs: ["HLD-001-krypton-cluster"]
downstream_refs: ["LLD-001-krypton-cluster"]
tags: [adr, architecture, golang, runtime, performance, microservices]
---

# ADR-003: Language Runtime Selection (Go / Golang for Microservices Ingress)

## 1. Context & Problem Statement
The redirect microservice handles 100,000+ concurrent network connections per second with a strict P99 latency target < 3ms. Python (with GIL limitations) is inadequate for single-instance multi-core CPU efficiency at this scale. We must select a compiled, lightweight, high-concurrency runtime.

## 2. Decision Candidates Evaluated
- **Option A (Accepted):** Go (Golang) — Lightweight goroutines, mature HTTP netpoll, excellent Kafka/Redis SDKs, minimal memory footprint (< 30MB base).
- **Option B:** Rust (Tokio / Actix) — Zero-cost abstractions, zero GC pauses, maximum raw performance.
- **Option C:** Java / JVM (Quarkus / Vert.x) — High throughput, enterprise ecosystem.

## 3. Weighted Multi-Criteria Decision Matrix
*Scale: 1 (Poor) to 5 (Excellent). Weights sum to 100%.*

| Evaluation Vector | Weight | Option A: Go (Golang) | Option B: Rust | Option C: Java (Quarkus) |
|---|---|---|---|---|
| **P99 Concurrency & Netpoll (<3ms)** | 30% | **5** (Sub-ms Goroutines) | 5 (Zero GC) | 4 (GC tuning needed) |
| **Developer Velocity & Maintainability** | 25% | **5** (Simple language, fast compile) | 3 (Steep borrow checker curve) | 4 (Verbose boilerplate) |
| **Container Memory Footprint** | 20% | **5** (~25MB resident) | 5 (~15MB resident) | 2 (~250MB JVM footprint) |
| **Kafka & Redis Client Ecosystem** | 15% | **5** (Segmentio/Kafka-go, Go-Redis) | 4 (rdkafka bindings) | 5 (Native clients) |
| **Cold Start / Autoscaling Latency** | 10% | **5** (Instant < 20ms startup) | 5 (< 10ms startup) | 3 (200ms+ startup) |
| **Weighted Total** | **100%** | **5.00 / 5.00** | 4.35 / 5.00 | 3.60 / 5.00 |

## 4. Decision Outcome & Rationale
**Selected Option A (Go / Golang).**  
Go strikes the optimal balance between ultra-low memory usage, sub-millisecond Goroutine scheduler concurrency, instant container cold starts in Kubernetes HPA, and team developer velocity.

## 5. Downstream Directives for LLD & Code
1. Microservices in `src/` MUST be implemented in Go 1.22+ using standard library `net/http` or lightweight routers.
2. Goroutines handling redirect requests MUST NOT leak memory or spawn unbounded background workers.
