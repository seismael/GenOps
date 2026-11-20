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
└── (code stage scaffolds src/, not a CODE-*.md doc)
```

For multi-domain projects (e.g., e-commerce: catalog, cart, payments):

```
docs/prd/PRD-001-product-catalog.md
docs/prd/PRD-002-shopping-cart.md
docs/prd/PRD-003-checkout-payment.md
```

The domain slug in the filename IS the agent's navigation system. `grep docs/ payment` finds all files across all layers related to "payment". Versioning is handled by git.

## Engineering & Execution Governance (GenOps Engine & Pipeline)

- **Zero-Chatter & Token Economy**: Lead immediately with actionable outputs, specifications, code diffs, or verification receipts. Omit pleasantries, restatements, and filler. Batch independent tool calls in parallel and cap command outputs at <= 2,500 bytes.
- **Brevity in Prose, Completeness in Implementation**: Token frugality applies strictly to conversational chatter—never to specification depth, code completeness, edge-case coverage, or verification rigor. Zero `TODO`/`TBD` placeholders or partial implementations.
- **First-Principles Root-Cause Engineering**: Resolve defects at their fundamental causal mechanism in `.agents/scripts/genops.py`, `.agents/scaffolds/`, `.agents/templates/`, or `.agents/skills/`. Never bypass or weaken schema validation, lineage rules, anti-drift checks, or compiler verifications.
- **Zero-Dependency Determinism**: The core engine (`.agents/scripts/genops.py`) and installer (`.agents/scripts/install_global.py`) must remain Python 3.8+ standard-library-only, cross-platform (Windows/macOS/Linux), and LF-normalized SHA-256 deterministic.
- **MCP Stdio Purity**: Never write raw `print()` output to `stdout` in any code path reachable by `MCPServer.dispatch()`; `stdout` is reserved exclusively for JSON-RPC 2.0 frames during `genops mcp`.
- **Mutation Exactness (RFC-0018)**: Immediately before editing an existing file, read the exact target line range on disk and use its verbatim bytes as the replacement anchor. Write new files once with final content; never write-then-edit.
- **Workspace Hygiene & Zero Leftovers**: Keep the repository root strictly clean. All tests must execute inside isolated `tempfile.TemporaryDirectory()` contexts and clean up all temporary artifacts upon exit.
- **Verification Gate**: After any engine, template, scaffold, or skill change, run `python .agents/scripts/genops.py doctor` and `python -m unittest discover -s tests -p "test_*.py"` and report exact exit codes.

<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->

## GenOps Cascading Specification Pipeline (Software Specification Pipeline)

This project uses **GenOps**, a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages backed by deterministic LF-normalized SHA-256 tracking.

> When a user invokes `/genops-<stage>` (or requests a pipeline stage), read `.agents/skills/genops-stage/SKILL.md` and `.agents/skills/genops-<stage>/SKILL.md` before executing.

### Available Stage Commands

| Command | Scope | Skill Protocol | Description |
|---|---|---|---|
| `/genops-prd` | Product Requirements | `.agents/skills/genops-prd/SKILL.md` | Product vision, user stories, success metrics, scope boundaries |
| `/genops-hld` | High-Level Design | `.agents/skills/genops-hld/SKILL.md` | System topology, component boundaries, data flow, integration points |
| `/genops-adr` | Architecture Decisions | `.agents/skills/genops-adr/SKILL.md` | Architectural trade-offs, technology selection, design pattern choices |
| `/genops-lld` | Low-Level Design | `.agents/skills/genops-lld/SKILL.md` | Class diagrams, database schemas, API contracts, module structure |
| `/genops-code` | Implementation | `.agents/skills/genops-code/SKILL.md` | Scaffold project from LLD design using scaffold templates |
| `/genops` | Pipeline Engine | `.agents/skills/genops/SKILL.md` | Orchestrate pipeline, check health status |

### Flow Modes

| Mode | Command Example | Description |
|---|---|---|
| **SoC (Default)** | `/genops-prd` | One stage at a time. Solicits human approval before offering next. |
| **Targeted** | `/genops-prd --domain <slug>` | Scopes execution or modification exclusively to specified domain. |
| **Flow** | `/genops-prd --flow` | Completes stage, then automatically cascades to next stage. |
| **Nonstop** | `/genops-prd --nonstop` | Runs full cascade with approval gates at each stage. |
| **Fast-Track** | `/genops-prd --fast` | Generates immediate spec draft from context with inline critic notes. |
| **Incremental** | `/genops --from adr --domain <slug>` | Starts incremental cascade for a single domain. |
| **Status** | `/genops --status` | Shows live pipeline health and stale downstream flags. |

### Separation of Concerns Protocol

Each stage execution adheres strictly to:
1. **Pre-flight**: Verifies prerequisites exist and are approved (`python .agents/scripts/genops.py validate`).
2. **Context**: Loads `.agents/context/CONTEXT.md` first; uses `python .agents/scripts/genops.py context --domain <slug>` when upstream specs exceed 60k chars.
3. **Drafting**: Generates modular `{STAGE}-{NNN}-{slug}.md` documents with standardized YAML frontmatter and zero `TODO`/`TBD` placeholders.
4. **Approval**: Hard gate requiring explicit confirmation before transition.
5. **State Recording**: Updates `docs/.genops-state.json` (v2.0) and appends a hash-chained event to `docs/.genops-events.jsonl` (`python .agents/scripts/genops.py record <stage>`).

### Execution & Architectural Invariants

- **Zero-Chatter & Token Economy**: Lead with actionable output, specs, diffs, or gate receipts. No pleasantries or filler. Batch independent tool calls in parallel and cap command outputs at <= 2,500 bytes.
- **First-Principles Engineering**: Resolve root causes directly; never weaken schemas, lineage rules, anti-drift checks, or compiler verifications to pass a gate.
- **Mutation Exactness (RFC-0018)**: Immediately before editing an existing file, read the exact target range on disk and use its verbatim bytes as the replacement anchor. Write new files once with final content; never write-then-edit.
- **Workspace Hygiene**: Keep the repository root clean. Store temporary probes in `.agents/loop/scratch/` (or isolated `tempfile` directories in tests) and remove transient artifacts upon completion.
- **Verification Gate**: Run `python .agents/scripts/genops.py doctor` and `python -m unittest discover -s tests -p "test_*.py"` after engine or pipeline changes.

<!-- GENOPS:END -->
