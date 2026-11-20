# Claude Code Instructions

<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->

## GenOps Cascading Specification Pipeline (PulseGate Edge Rate-Limiter & Webhook Pipeline)

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
