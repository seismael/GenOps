# GenOps — Cascading Specification Pipeline

This project uses **GenOps**, a separation-of-concerns agent-native pipeline engine that decomposes complex software work into isolated, cascading specification stages. Each stage is a scoped native skill.

## Pipeline Overview

```
/genops-prd ──cascade──> /genops-hld ──cascade──> /genops-adr ──cascade──> /genops-lld ──cascade──> /genops-code
     │                       │                       │                       │                       │
     v                       v                       v                       v                       v
docs/prd/               docs/hld/           docs/architecture/          docs/lld/               docs/code/
```

The pipeline is defined declaratively in `genops.yaml`. Each stage produces files into its output directory.

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

## Available Commands

| Command | Scope | Description |
|---------|-------|-------------|
| `/genops-prd` | Product Requirements | Define vision, user stories, success metrics |
| `/genops-hld` | High-Level Design | Architecture topology, components, data flow |
| `/genops-adr` | Architecture Decisions | Trade-off analysis, technology selection |
| `/genops-lld` | Low-Level Design | Class diagrams, schemas, API contracts |
| `/genops-code` | Implementation | Implementation plan, scaffolding, code generation |
| `/genops` | Pipeline Engine | Orchestrate pipeline, check status |

## Flow Control Modes

| Invocation | Behavior |
|-----------|----------|
| `/genops-prd` | SoC mode: PRD only. After approval → "Run /genops-hld or save for later?" |
| `/genops-prd --flow` | PRD then auto-invoke /genops-hld (one-hop cascade) |
| `/genops-prd --nonstop` | PRD → HLD → ADR → LLD → Code (full cascade, approve at each gate) |
| `/genops-hld` | HLD only. Checks PRD state first (warns if stale) |
| `/genops-hld --flow` | HLD then auto-invoke /genops-adr |
| `/genops --from <stage>` | Start pipeline from any stage |
| `/genops --nonstop` | Run entire pipeline from current position |
| `/genops --status` | Show pipeline health dashboard |

## Separation of Concerns

**Default behavior: one stage at a time.** Each stage:
1. Loads upstream context from required directories
2. Checks staleness (per-file hash comparison)
3. Interviews you with clarifying questions
4. Determines domains — generates one file per domain per layer
5. Presents results for approval
6. Records state with per-file tracking

**Use `--flow`** when you want to proceed one hop forward after approval.
**Use `--nonstop`** to run the full pipeline with approval gates at each stage.

## Reactive Context Engine

When a stage is invoked, it checks all upstream files against stored hashes in `docs/.genops-state.json`. If an upstream file changed, the specific file is identified and downstream layers are flagged stale. The domain slug in the filename enables precise targeting of updates.

Run `/genops --status` to see which stages are stale at any time.

## Adding a New Pipeline

GenOps is generic. Edit `genops.yaml` to define a pipeline for any domain:
- Software specification (built-in)
- Research pipeline (Lit Review → Hypothesis → Experiment → Report)
- Design pipeline (Brief → Wireframes → Mockups → Prototype)
- Any domain with cascading, dependent stages

## Agent-Native Discovery

All skills live in `.agents/skills/` with standard SKILL.md format. The agent discovers them through AGENTS.md and skill descriptions. No code installation required.

<!-- GENOPS:END -->
