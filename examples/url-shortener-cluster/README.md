# Krypton Enterprise Clustered Platform (GenOps Example Project #2)

A complete example of an **Enterprise Clustered Microservices System** designed via the **GenOps Software Specification Pipeline** (`PRD → HLD → ADR → LLD → Code`).

## Pipeline Artifacts & Architecture

```
examples/url-shortener-cluster/
├── docs/
│   ├── prd/PRD-001-krypton-cluster.md               # Socratic demand justification & hyperscale OKRs (100k RPS)
│   ├── hld/HLD-001-krypton-cluster.md               # Clustered C4 topology, Kafka bus, edge gateways & failover
│   ├── architecture/
│   │   ├── ADR-001-distributed-storage-stack.md    # Tiered Redis + PostgreSQL + ClickHouse storage
│   │   ├── ADR-002-event-streaming-engine.md       # Apache Kafka / Redpanda partitioned commit log
│   │   └── ADR-003-language-runtime-selection.md   # High-concurrency Go microservices
│   └── lld/LLD-001-krypton-cluster.md               # DDD microservice contracts, ClickHouse DDL & ports
└── src/
    ├── redirect-service/                            # High-throughput Go ingress gateway
    │   ├── internal/domain/                         # RedirectRoute, ClickTelemetry
    │   ├── internal/ports/                          # IRedisCachePort, IKafkaProducerPort
    │   ├── internal/services/                       # RedirectService (sub-ms resolution)
    │   ├── internal/adapters/cache/                 # Thread-safe Redis cluster adapter (in-memory mock)
    │   ├── internal/adapters/streaming/             # Non-blocking async Kafka producer (mock)
    │   └── tests/unit/                              # 20,000-concurrent-goroutine benchmark
    └── analytics-service/                           # Columnar OLAP analytics microservice
        ├── internal/domain/                         # MetricQuery, ClickRecord, AnalyticsReport
        ├── internal/ports/                          # IClickHouseAdapter
        ├── internal/services/                       # AnalyticsService
        ├── internal/adapters/persistence/           # Vectorized in-memory ClickHouse adapter (mock)
        └── tests/unit/                              # 5,000-event batch ingestion & aggregation test
```

> The Redis/Kafka/ClickHouse adapters are **in-memory mocks** that faithfully model the ADR-chosen stacks, so the example builds and tests with zero external infrastructure.

## Run the microservice test suites

Each service is a standalone Go module — run `go test` from its module root:

```powershell
# 1. Redirect service (20,000 concurrent redirects)
cd examples/url-shortener-cluster/src/redirect-service
go test ./...

# 2. Analytics service (OLAP aggregation)
cd ../analytics-service
go test ./...
```

## Notable design qualities

- **SSRF-hardened** redirect validation (loopback, link-local, and RFC1918 literals rejected).
- **Non-blocking telemetry** design: drop-oldest on a full producer buffer, per ADR-002.
- **Clean architecture**: domain → ports → services → adapters, decoupled for the Redis→PostgreSQL→ClickHouse tier swap described in ADR-001.
