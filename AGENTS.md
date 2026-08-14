# GenOps — Cascading Specification Pipeline

This project uses **GenOps**, a separation-of-concerns agent-native pipeline engine that decomposes complex software work into isolated, cascading specification stages. Each stage is a scoped native skill backed by a deterministic CLI helper.

## Pipeline Overview

```
/genops-prd ──cascade──> /genops-hld ──cascade──> /genops-adr ──cascade──> /genops-lld ──cascade──> /genops-code
     │                       │                       │                       │                       │
     v                       v                       v                       v                       v
docs/prd/               docs/hld/           docs/architecture/          docs/lld/               src/**/*
```

The pipeline is defined declaratively in `genops.yaml`. Each stage produces files into its output directory with standardized YAML frontmatter headers.

## Document Organization

Files use **domain-split** naming: `{STAGE}-{NNN}-{descriptive-slug}.md`

```
docs/
├── prd/PRD-001-taskflow-requirements.md     ← Single domain = 1 file
├── hld/HLD-001-system-architecture.md       ← Single domain = 1 file
├── architecture/
│   ├── ADR-001-go-language.md               ← One per decision
│   ├── ADR-002-sqlite-storage.md
│   └── ADR-003-cobra-cli-framework.md
├── lld/LLD-001-taskflow-design.md           ← Single domain = 1 file
└── code/
    ├── CODE-001-core-domain.md              ← Multiple files per domain
    ├── CODE-002-storage-layer.md
    └── CODE-003-cli-commands.md
```

For multi-domain projects (e.g., e-commerce: catalog, cart, payments):

```
docs/prd/PRD-001-product-catalog.md
docs/prd/PRD-002-shopping-cart.md
docs/prd/PRD-003-checkout-payment.md
```

The domain slug in the filename IS the agent's navigation system. `grep docs/ payment` finds all files across all layers related to "payment". Versioning is handled by git.

<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->

## GenOps Cascading Specification Pipeline (Software Specification Pipeline)

This project uses **GenOps**, a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages backed by deterministic LF-normalized SHA-256 tracking.

### Available Stage Commands

| Command | Scope | Description |
|---|---|---|
| `/genops-prd` | Product Requirements | Product vision, user stories, success metrics, scope boundaries |
| `/genops-hld` | High-Level Design | System topology, component boundaries, data flow, integration points |
| `/genops-adr` | Architecture Decisions | Architectural trade-offs, technology selection, design pattern choices |
| `/genops-lld` | Low-Level Design | Class diagrams, database schemas, API contracts, module structure |
| `/genops-code` | Implementation | Scaffold project from LLD design using scaffold templates |
| `/genops` | Pipeline Engine | Orchestrate pipeline, check health status |

### Flow Modes

| Mode | Command Example | Description |
|---|---|---|
| **SoC (Default)** | `/genops-prd` | One stage at a time. Solicits human approval before offering next. |
| **Targeted** | `/genops-prd --domain <slug>` | Scopes execution or modification exclusively to specified domain. |
| **Flow** | `/genops-prd --flow` | Completes stage, then automatically cascades to next stage. |
| **Nonstop** | `/genops-prd --nonstop` | Runs full cascade with approval gates at each stage. |
| **Incremental** | `/genops --from adr --domain <slug>` | Starts incremental cascade for a single domain. |
| **Status** | `/genops --status` | Shows live pipeline health and stale downstream flags. |

### Separation of Concerns Protocol

Each stage execution adheres strictly to:
1. **Pre-flight**: Verifies prerequisites exist and are approved.
2. **Context**: Loads upstream requirements and domain terms.
3. **Drafting**: Generates modular `{STAGE}-{NNN}-{slug}.md` documents with standardized YAML frontmatter.
4. **Approval**: Hard gate requiring explicit confirmation before transition.
5. **State Recording**: Updates `docs/.genops-state.json` (v2.0) and logs immutable events to `docs/.genops-events.jsonl`.

<!-- GENOPS:END -->
