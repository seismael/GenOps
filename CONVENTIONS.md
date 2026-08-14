# CONVENTIONS Instructions

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
