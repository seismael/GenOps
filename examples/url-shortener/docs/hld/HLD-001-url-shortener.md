---
id: HLD-001-url-shortener
domain: url-shortener
stage: hld
version: 1.0.0
status: approved
upstream_refs: ["PRD-001-url-shortener"]
downstream_refs: ["ADR-001-storage-engine", "ADR-002-short-code-generation", "LLD-001-url-shortener"]
tags: [hld, architecture, topology, c4]
---

# HLD-001: High-Level System Architecture & Topology

## 1. System Topology & C4 Container Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontFamily': 'Inter, system-ui, sans-serif', 'lineColor': '#64748b', 'primaryTextColor': '#0f172a' }}}%%
flowchart TB
    USER["End User / Browser"]
    CLIENT["API Consumer / Client App"]
    
    subgraph Krypton ["Krypton URL Shortener Gateway (FastAPI Service)"]
        direction TB
        ROUTER["HTTP Ingress Router<br/>(Endpoints: /api/v1/shorten, /{code}, /analytics)"]
        AUTH["Token Authenticator<br/>(API Key validation)"]
        SVC["URL Shortener Domain Service<br/>(Base62 generator & redirect resolver)"]
        CLICK_REC["Click Recorder<br/>(Synchronous insert after cache lookup)"]
        
        ROUTER --> AUTH
        AUTH --> SVC
        SVC --> CLICK_REC
    end

    subgraph Storage ["Persistence Layer"]
        DB[("SQLite / PostgreSQL<br/>(URLs, Clicks, API Keys)")]
        CACHE[("In-Memory LRU Cache<br/>(Hot short-code redirects)")]
    end

    USER ==>|"GET /{code} (Redirect)"| ROUTER
    CLIENT ==>|"POST /api/v1/shorten"| ROUTER
    CLIENT ==>|"GET /api/v1/analytics/{code}"| ROUTER

    SVC <--> CACHE
    SVC <--> DB
    CLICK_REC -->|"Record Click (sync)"| DB

    classDef userNode fill:#f8fafc,stroke:#2563eb,stroke-width:1.5px,color:#0f172a,rx:6px,ry:6px;
    classDef appNode fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px,color:#14532d,rx:6px,ry:6px;
    classDef dbNode fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764,rx:6px,ry:6px;
    
    class USER,CLIENT userNode;
    class ROUTER,AUTH,SVC,CLICK_REC appNode;
    class DB,CACHE dbNode;
```

## 2. Dynamic Sequence Flows

### A. URL Shortening Flow (Synchronous)
```mermaid
sequenceDiagram
    autonumber
    participant C as API Consumer
    participant R as Ingress Router
    participant S as URL Service
    participant D as Storage Engine

    C->>R: POST /api/v1/shorten {url: "https://example.com/page"}
    R->>R: Validate API Key & URL Schema
    R->>S: ShortenURL(target_url)
    S->>S: Generate Base62 Code (7 chars)
    S->>D: Insert URLRecord (code, target_url, created_at)
    D-->>S: Record Persisted
    S-->>R: ShortURL Entity
    R-->>C: HTTP 201 Created {code: "k7X9qZb", short_url: "https://krp.tn/k7X9qZb"}
```

### B. High-Throughput Redirection with Synchronous Click Recording
```mermaid
sequenceDiagram
    autonumber
    participant U as Visitor Browser
    participant R as Ingress Router
    participant S as URL Service
    participant C as Memory Cache
    participant D as Storage Engine

    U->>R: GET /{code}
    R->>S: Resolve(code)
    alt Cache Hit
        S->>C: Lookup(code)
        C-->>S: URLRecord
    else Cache Miss
        S->>D: Query(code)
        D-->>S: URLRecord
        S->>C: Populate(code, URLRecord)
    end
    S->>D: RecordClick(code, ip, user_agent, referrer) (synchronous after cache lookup)
    S-->>R: HTTP 302 Location: target_url
    R-->>U: Instant 302 Redirect
```

## 3. Failure Domain & Resilience Matrix
| Subsystem Failure | Impact | Mitigation Strategy | Recovery Time Objective (RTO) |
|---|---|---|---|
| **Database Read Latency Spike** | Redirection slowdown | In-memory LRU cache serves hot links directly without DB touch | RTO = 0s (Graceful fallback) |
| **Click Event Buffer Saturation** | Memory pressure under DDoS | Fixed-size bounded queue with drop-oldest policy; analytics degrades before redirect ingress | RTO < 5s |
| **Invalid Target Hostname** | Consumer error | Strict validation against RFC 3986 with DNS pre-check before persistence | Instant 400 Bad Request |

## 4. Adversarial Red-Team Stress-Test & Vulnerability Assessment
1. **Concurrency Race / Short Code Collision:**
   - *Attack Scenario:* 100 concurrent requests trigger identical hash offsets.
   - *Mitigation:* Cryptographic Murmur3/SHA-256 + nano-timestamp salt with unique database index constraint on `code`. Automatic retry with alternative salt on collision.
2. **Click Event Flooding / DDoS Amplification:**
   - *Attack Scenario:* Botnet generates 50,000 GET requests/sec on short code to saturate database writes.
   - *Mitigation:* Background click dispatcher decouples HTTP worker thread from database write; click ingestion uses batched bulk transactions every 100ms or 500 events.
3. **Internal Network Scanning via Redirects (SSRF):**
   - *Attack Scenario:* Attacker creates short URL to `http://169.254.169.254/latest/meta-data/` or internal admin ports.
   - *Mitigation:* Target URL validator parses hostname and resolves IP; loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), and private CIDRs (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are strictly rejected.

## 5. Technology Decisions Backlog (Needs ADR)
1. **ADR-001: Storage Engine Selection** — Embedded SQLite with WAL mode vs. External PostgreSQL for single-node vs. distributed deployment.
2. **ADR-002: Short-Code Generation Algorithm** — Base62 Counter vs. Cryptographic Hash Truncation vs. UUIDv7.
