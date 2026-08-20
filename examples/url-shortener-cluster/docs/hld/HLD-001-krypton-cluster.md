---
id: HLD-001-krypton-cluster
domain: krypton-cluster
stage: hld
version: 2.0.0
status: approved
upstream_refs: ["PRD-001-krypton-cluster"]
downstream_refs: ["ADR-001-distributed-storage-stack", "ADR-002-event-streaming-engine", "ADR-003-language-runtime-selection", "LLD-001-krypton-cluster"]
tags: [hld, cluster, microservices, c4, distributed-systems, kafka]
---

# HLD-001: Krypton Enterprise Clustered Microservices Architecture

## 1. Clustered System Topology & C4 Container Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontFamily': 'Inter, system-ui, sans-serif', 'lineColor': '#64748b', 'primaryTextColor': '#0f172a' }}}%%
flowchart TB
    GEO_DNS["Global Anycast DNS / Cloudflare CDN Edge"]
    VISITORS["Global Web Visitors (100k RPS)"]
    TENANTS["Enterprise API Clients / Marketing BI"]

    VISITORS ==> GEO_DNS
    TENANTS ==> GEO_DNS

    subgraph EdgePlane ["1. Regional Edge Ingress Tier (Stateless Kubernetes Nodes)"]
        direction TB
        REDIRECT_SVC["Redirect & Ingress Service (Go)<br/>- High-concurrency epoll/kqueue<br/>- P99 < 3ms redirect<br/>- Non-blocking Kafka producer"]
        MGMT_SVC["URL Admin & Tenant Service (Go)<br/>- API Auth & Key Hashing<br/>- URL creation & validation"]
    end

    subgraph CacheTier ["2. Distributed L2 Memory Cache"]
        REDIS_CLUSTER[("Redis Cluster 7.x (Multi-Region Shards)<br/>- Hot URL code mappings<br/>- Sub-millisecond get()")]
    end

    subgraph StreamPlane ["3. Resilient Event Streaming Tier"]
        KAFKA_BUS[("Apache Kafka / Redpanda Cluster<br/>- Topic: krypton.events.click<br/>- Partitioned by hash(code)<br/>- 3x In-Sync Replicas (ISR)")]
    end

    subgraph WorkerPlane ["4. Ingestion & Analytical Processing Tier"]
        INGEST_WORKERS["Clickstream Ingestion Workers (Go)<br/>- Consumer Group: click-archivers<br/>- Micro-batching 5,000 events/batch"]
        ANALYTICS_API["Analytics Query Microservice (Go)<br/>- Aggregated SQL queries<br/>- Tenant BI dashboards"]
    end

    subgraph StorageTier ["5. Tiered Distributed Storage Engine"]
        CLICKHOUSE[("ClickHouse Columnar OLAP DB<br/>- Petabyte-scale telemetry<br/>- Vectorized analytics queries")]
        POSTGRES_CLUSTER[("PostgreSQL / CockroachDB<br/>- URL metadata & Tenant accounts<br/>- Strict ACID master")]
    end

    GEO_DNS -->|"HTTP GET /{code}"| REDIRECT_SVC
    GEO_DNS -->|"REST API /api/v1/shorten"| MGMT_SVC
    GEO_DNS -->|"REST API /api/v1/analytics"| ANALYTICS_API

    REDIRECT_SVC <-->|"Hot Lookup (0.4ms)"| REDIS_CLUSTER
    REDIRECT_SVC -.->|"Async Cache-Miss Fetch"| POSTGRES_CLUSTER
    REDIRECT_SVC ==>|"Async Produce (zero wait)"| KAFKA_BUS

    MGMT_SVC -->|"Write URL & Invalidate Cache"| POSTGRES_CLUSTER
    MGMT_SVC -->|"Warm Cache"| REDIS_CLUSTER

    KAFKA_BUS ==>|"Consume Partition Stream"| INGEST_WORKERS
    INGEST_WORKERS ==>|"Vectorized Bulk Insert"| CLICKHOUSE

    ANALYTICS_API <-->|"Fast Columnar SQL"| CLICKHOUSE

    classDef edgeNode fill:#eff6ff,stroke:#1d4ed8,stroke-width:1.5px,color:#1e3a8a,rx:6px,ry:6px;
    classDef cacheNode fill:#fef2f2,stroke:#dc2626,stroke-width:1.5px,color:#7f1d1d,rx:6px,ry:6px;
    classDef streamNode fill:#fffbeb,stroke:#d97706,stroke-width:1.5px,color:#78350f,rx:6px,ry:6px;
    classDef workerNode fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#14532d,rx:6px,ry:6px;
    classDef dbNode fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764,rx:6px,ry:6px;

    class REDIRECT_SVC,MGMT_SVC edgeNode;
    class REDIS_CLUSTER cacheNode;
    class KAFKA_BUS streamNode;
    class INGEST_WORKERS,ANALYTICS_API workerNode;
    class CLICKHOUSE,POSTGRES_CLUSTER dbNode;
```

## 2. Dynamic End-to-End Clustered Sequence Flows

### A. Sub-3ms High-Throughput Redirection & Zero-Wait Streaming
```mermaid
sequenceDiagram
    autonumber
    participant V as Visitor Browser
    participant R as Redirect Microservice (Go)
    participant C as Redis Cluster
    participant K as Kafka Stream Bus
    participant W as Ingestion Worker
    participant CH as ClickHouse OLAP

    V->>R: GET /blackfriday (100k RPS)
    R->>C: GET code:blackfriday
    C-->>R: "https://shop.acme.com/promo" (0.3ms)
    R->>K: ProduceAsync(topic: "click", event: ClickTelemetry) (0.1ms non-blocking)
    R-->>V: HTTP 302 Location: https://shop.acme.com/promo (Total latency: 1.2ms)
    
    Note over K,W: Asynchronous Decoupled Stream Processing
    K--)W: FetchMessageBatch (5,000 events)
    W->>CH: Vectorized Bulk Insert INTO clicks_mv
    CH-->>W: Batch ACK
```

## 3. Clustered Failure Domain & Partition Resiliency Matrix
| Subsystem Failure | Failure Impact | Automatic Fault Mitigation | RTO / RPO |
|---|---|---|---|
| **Redis Cache Node Crash** | Cache miss surge | Fallback to read-replica PostgreSQL with exponential jittered backoff; automatic Redis Sentinel/Cluster failover. | RTO < 2s, RPO = 0 |
| **Kafka Broker Partition Outage** | Click events buffered in memory | Ingress Go workers buffer locally up to 250MB per node in ring buffer; flushes to alternative broker. | RTO < 5s, RPO = 0 |
| **ClickHouse Cluster Maintenance** | Telemetry writes paused | Kafka retains 7 days of event history; ingestion workers pause and resume smoothly without dropping events. | RTO = N/A, RPO = 0 |

## 4. Adversarial Red-Team Stress-Test & Threat Mitigations
1. **DDoS Click Amplification & Traffic Spikes:**
   - *Attack Scenario:* 500,000 requests/sec syn-flood aimed at exhausting HTTP socket descriptors.
   - *Mitigation:* Anycast BGP network shedding at Cloudflare edge + Linux `epoll` / Go netpoll worker pool with bounded concurrency tokens.
2. **Kafka Hot-Partition Skew:**
   - *Attack Scenario:* Viral link receives 95% of traffic, saturating a single Kafka partition.
   - *Mitigation:* Dual-key hashing algorithm (`hash(code) + round_robin_salt(1..16)`) spreads load evenly across 64 Kafka topic partitions.
3. **Cross-Region Replication Lag:**
   - *Attack Scenario:* URL created in `us-east-1` accessed immediately in `eu-west-1` before DB sync.
   - *Mitigation:* Short-code creation publishes synchronously to global Redis replication channel, pre-warming all POPs within 50ms.

## 5. Technology Decisions Backlog (Needs ADR)
1. **ADR-001: Distributed Storage & Tiered Database Stack** — ClickHouse + PostgreSQL vs. DynamoDB vs. Cassandra.
2. **ADR-002: Event Streaming Engine** — Apache Kafka / Redpanda vs. NATS JetStream vs. AWS Kinesis.
3. **ADR-003: Microservices Language Runtime** — Go (Golang) vs. Rust vs. Java/JVM for high-concurrency redirect nodes.
