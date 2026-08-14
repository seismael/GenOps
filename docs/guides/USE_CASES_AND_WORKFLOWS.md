# GenOps: User Experience, Real-World Use Cases & Architectural Evolution Guide

**How development teams and AI coding agents build, maintain, modify, and upgrade complex software systems step by step.**

---

## 1. Executive Philosophy: Simplicity First, Infinite Depth on Demand

GenOps is designed around a dual-track developer experience:

```mermaid
flowchart LR
    subgraph TrackA ["Track A: Everyday Simplicity (Zero Friction)"]
        direction TB
        A1["1. One slash command per stage (/genops-prd)"]
        A2["2. Interactive multiple-choice prompts"]
        A3["3. Deterministic auto-scaffolding to src/"]
        A4["4. Instant pipeline health status"]
        A1 --> A2 --> A3 --> A4
    end

    subgraph TrackB ["Track B: Architectural Precision (Deep Evolution)"]
        direction TB
        B1["1. Domain-scoped cascade targeting (--domain slug)"]
        B2["2. ADR-driven technology & storage swaps"]
        B3["3. Brownfield legacy codebase ingestion"]
        B4["4. Granular DAG context slicing (70-90% token reduction)"]
        B1 --> B2 --> B3 --> B4
    end

    classDef trackA fill:#0f172a,stroke:#00f0ff,stroke-width:2px,color:#f8fafc;
    classDef trackB fill:#1e1e38,stroke:#a855f7,stroke-width:2px,color:#f8fafc;
    class A1,A2,A3,A4 trackA;
    class B1,B2,B3,B4 trackB;
```

---

## 2. The 6 Core Real-World Use Cases

```mermaid
mindmap
  root((GenOps Use Cases))
    Greenfield Multi-Service
      Concept to Scaffold in 15 mins
      Multi-stack Go, Python, React, Rust
    Incremental Feature Addition
      Domain-targeted execution
      Zero drift on stable services
    Architectural Migration
      ADR-driven database/queue swap
      Reactive downstream cascade
    Brownfield Legacy Ingestion
      Auto-generates baseline LLD
      CI/CD anti-drift protection
    Compliance & Certification
      Bidirectional Traceability Matrix
      Immutable cryptographic audit trail
    Non-Software Pipelines
      UI/UX Design Systems
      Scientific Research Pipelines
```

---

### Use Case 1: Greenfield Multi-Service Application
**Scenario:** A team wants to build a new high-throughput event processing platform with Go microservices, Python ML workers, and a React frontend.

```mermaid
flowchart LR
    P["/genops-prd<br/>(ingestion, analytics)"] --> H["/genops-hld<br/>(topology, services)"]
    H --> A["/genops-adr<br/>(Go, Python, React)"]
    A --> L["/genops-lld<br/>(schemas, APIs)"]
    L --> C["/genops-code<br/>(deterministic scaffolds)"]
    
    C --> S1["src/ingestion-service/ (Go)"]
    C --> S2["src/analytics-worker/ (Python)"]
    C --> S3["src/web-dashboard/ (React)"]
```

**Workflow:**
1. **Initialize Project:**
   ```bash
   python .agents/scripts/genops.py init --preset software-spec
   ```
2. **Define Product Requirements:**
   User prompts `/genops-prd`. The agent interviews the user domain by domain (e.g. `ingestion`, `analytics`, `billing`), generating `PRD-001-ingestion.md`, `PRD-002-analytics.md`.
3. **Design Topology & Decisions:**
   User prompts `/genops-hld` and `/genops-adr`. The team documents why Go was chosen for ingestion and Python for ML.
4. **Define Low-Level Contracts & Project Structure:**
   User prompts `/genops-lld`. LLD defines entity schemas, API endpoints, and the `## Project Structure` table.
5. **Deterministic Scaffolding:**
   User prompts `/genops-code`. GenOps deterministically expands `go-service`, `python-fastapi`, and `react-vite` scaffolds into `src/` with entity stubs and `docker-compose.yml`.

---

### Use Case 2: Incremental Feature Addition (Targeted Domain Execution)
**Scenario:** 6 months later, the team needs to add a new `subscriptions` feature without touching or regenerating existing stable services.

```mermaid
flowchart LR
    subgraph Stable ["Untouched Stable Services"]
        P1["PRD-001-ingestion.md"]
        H1["HLD-001-ingestion.md"]
        L1["LLD-001-ingestion.md"]
        S1["src/ingestion-service/"]
        P1 --> H1 --> L1 --> S1
    end

    subgraph New ["Targeted Subscriptions Domain (/genops-* --domain subscriptions)"]
        P2["PRD-003-subscriptions.md"]
        H2["HLD-003-subscriptions.md"]
        L2["LLD-003-subscriptions.md"]
        S2["src/subscriptions-service/"]
        P2 ==> H2 ==> L2 ==> S2
    end

    classDef stableStyle fill:#1e293b,stroke:#64748b,stroke-width:1px,color:#94a3b8;
    classDef newStyle fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    class P1,H1,L1,S1 stableStyle;
    class P2,H2,L2,S2 newStyle;
```

**Workflow:**
1. **Create Domain PRD:**
   ```bash
   # User prompts the agent:
   /genops-prd --domain subscriptions
   ```
   Agent creates only `docs/prd/PRD-003-subscriptions.md`.
2. **Cascade Downstream Only for `subscriptions`:**
   ```bash
   /genops-hld --domain subscriptions
   /genops-lld --domain subscriptions
   /genops-code --domain subscriptions
   ```
3. **Verification:**
   Existing `docs/prd/PRD-001-ingestion.md` and `src/ingestion-service/` remain completely untouched. Only `src/subscriptions-service/` is generated.

---

### Use Case 3: Architectural Migration & Tech Swap (ADR-Driven Evolution)
**Scenario:** The platform grows from 10k to 5M events/day. The team must migrate from embedded SQLite to a distributed PostgreSQL cluster.

```mermaid
flowchart TB
    ADR_OLD["ADR-002-sqlite-storage.md<br/><b>[SUPERSEDED]</b>"] -.->|Replaced by| ADR_NEW["ADR-005-postgres-storage.md<br/><b>[ACCEPTED]</b>"]
    
    ADR_NEW ==>|"Triggers Stale Cascade"| LLD["docs/lld/LLD-001-database.md<br/><b>[STALE → UPDATED]</b>"]
    LLD ==>|"Updates Driver & Schema"| CODE["src/storage/postgres.go<br/><b>[MIGRATED]</b>"]

    classDef oldStyle fill:#450a0a,stroke:#ef4444,stroke-width:1px,color:#f87171;
    classDef newStyle fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef modStyle fill:#1e293b,stroke:#00f0ff,stroke-width:2px,color:#f8fafc;
    class ADR_OLD oldStyle;
    class ADR_NEW newStyle;
    class LLD,CODE modStyle;
```

**Workflow:**
1. **Draft New ADR:**
   User creates `docs/architecture/ADR-005-postgres-storage.md` marking `ADR-002-sqlite-storage.md` as `Superseded`.
2. **Check Reactive Cascading:**
   ```bash
   python .agents/scripts/genops.py status
   ```
   *Output:*
   ```
   Stage   | State   | Upstream   | Downstream
   adr     | approved| consistent | consistent
   lld     | stale   | changed    | at-risk
   code    | stale   | changed    | at-risk
   ```
3. **Apply Targeted Upgrade:**
   User prompts: *"Update LLD and database store stubs for Postgres migration"*.
   Agent loads `ADR-005` and updates `LLD-001` schemas and SQL drivers.
4. **Re-Record Approved State:**
   ```bash
   python .agents/scripts/genops.py record lld --actor lead-architect
   ```

---

### Use Case 4: Brownfield Legacy Codebase Ingestion
**Scenario:** A company has an existing 50,000-line repository with 4 microservices in `src/` and zero documentation.

```mermaid
flowchart LR
    SRC["Existing Legacy Codebase<br/>(src/auth, src/billing, src/api)"] -->|"genops ingest --src src/"| BASE["docs/lld/LLD-001-baseline.md<br/>(Auto-Generated Structure)"]
    BASE -->|"genops record lld"| STATE["docs/.genops-state.json<br/>(Locked State Hash)"]
    STATE -->|"genops drift"| CI["CI/CD Anti-Drift Gate<br/>(Protects all future PRs)"]

    classDef ingBox fill:#1e1e38,stroke:#a855f7,stroke-width:2px,color:#f8fafc;
    class SRC,BASE,STATE,CI ingBox;
```

**Workflow:**
1. **Run Ingestion:**
   ```bash
   python .agents/scripts/genops.py ingest --src src/
   ```
2. **Auto-Generated Baseline:**
   GenOps analyzes the directory tree and generates `docs/lld/LLD-001-baseline.md`.
3. **Record Initial Baseline:**
   ```bash
   python .agents/scripts/genops.py record lld --actor tech-lead
   ```
4. **Managed Evolution:**
   Any future modifications to `src/` are now protected by the CI anti-drift gate:
   ```bash
   python .agents/scripts/genops.py drift
   ```

---

### Use Case 5: Regulated Audit & Compliance Certification (FDA / SOC2 / ISO 26262)
**Scenario:** Compliance officers need proof that every safety requirement in PRD is implemented and tested in code.

```mermaid
flowchart LR
    REQ["PRD-001: US-01<br/>Encrypted Data at Rest"] --> COMP["HLD-001: Component<br/>EncryptionService"]
    COMP --> ADR["ADR-003: Decision<br/>AES-256-GCM"]
    ADR --> ENT["LLD-001: Schema<br/>CipherPayload Struct"]
    ENT --> CODE["src/crypto/vault.go<br/>Vault.Encrypt()"]
    CODE --> TEST["tests/vault_test.go<br/>TestEncryptionIntegrity()"]

    classDef rtmNode fill:#0f172a,stroke:#00f0ff,stroke-width:2px,color:#f8fafc;
    class REQ,COMP,ADR,ENT,CODE,TEST rtmNode;
```

**Workflow:**
1. **Generate Bidirectional RTM:**
   ```bash
   python .agents/scripts/genops.py rtm
   ```
   Outputs complete coverage table: `PRD User Story → HLD Component → ADR → LLD Entity → Code File`.
2. **Generate Executive HTML Audit Dashboard:**
   ```bash
   python .agents/scripts/genops.py report --html docs/audit-report.html
   ```
3. **Deliver Audit Artifacts:**
   Export `docs/audit-report.html` and `docs/.genops-events.jsonl` (cryptographically hashed, timestamped event trail).

---

### Use Case 6: Non-Software Multi-Domain Pipelines
**Scenario:** A UX research team or Academic science group wants structured, cascading specification without code.

```mermaid
flowchart LR
    subgraph Design ["Design Pipeline (init --preset design)"]
        direction LR
        D1["/genops-brief"] --> D2["/genops-wireframes"] --> D3["/genops-mockups"] --> D4["/genops-prototype"]
    end

    subgraph Research ["Research Pipeline (init --preset research)"]
        direction LR
        R1["/genops-lit-review"] --> R2["/genops-hypothesis"] --> R3["/genops-experiment"] --> R4["/genops-report"]
    end

    classDef pipeBox fill:#1e293b,stroke:#3b82f6,stroke-width:1px,color:#f8fafc;
    class D1,D2,D3,D4,R1,R2,R3,R4 pipeBox;
```

---

## 3. Quick Reference: The Essential Commands

| Command | Everyday Usage | Advanced / Upgrade Usage |
|---|---|---|
| `python .agents/scripts/genops.py validate` | Verify project setup is healthy | Check custom scaffold or schema syntax |
| `python .agents/scripts/genops.py status` | Check which stage to run next | Detect exactly which downstream docs are stale |
| `python .agents/scripts/genops.py context --domain <slug>` | Load prompt context for single feature | 80% token reduction in large monorepos |
| `python .agents/scripts/genops.py drift` | Pre-commit sanity check | Automated PR gate in CI/CD pipeline |
| `python .agents/scripts/genops.py rtm` | Trace requirements coverage | SOC2 / ISO compliance audit export |
| `python .agents/scripts/genops.py report` | View visual dashboard | Export static HTML report for stakeholders |
