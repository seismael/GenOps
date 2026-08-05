# GenOps — Agent-Native Specification Pipeline

**Declarative. Cascading. Agent-First.**

GenOps is a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages. Each stage is a native agent skill — no custom code, no CLI tools, no installers. Just files that agents discover and execute.

```
/genops-prd ──cascade──> /genops-hld ──cascade──> /genops-adr ──cascade──> /genops-lld ──cascade──> /genops-code
     │                       │                       │                       │                       │
     v                       v                       v                       v                       v
docs/prd/               docs/hld/           docs/architecture/          docs/lld/               docs/code/
```

## Why GenOps

AI coding agents are powerful but unfocused. They skip planning, mix concerns, and lose context across long sessions. GenOps enforces structure:

- **One stage at a time** — SoC by design. Each `/genops-prd`, `/genops-hld`, etc. handles exactly one layer.
- **Reactive cascading** — Change an upstream doc and all downstream layers detect staleness. The agent knows exactly which files need regeneration.
- **Agent-native** — No code. No install. Skills are SKILL.md files discovered by AGENTS.md. Works with Claude CLI, OpenCode, Gemini CLI.
- **Generic** — Edit `genops.yaml` to define any pipeline. Software spec is one preset. Research, design, or any sequential workflow works.

## Quick Start

Clone GenOps as your project template:

```bash
git clone https://github.com/user/genops.git my-project
cd my-project
```

The agent discovers GenOps automatically from `AGENTS.md` and `.agents/skills/`.

```bash
/genops-init           # Initialize (or validate) the project
/genops-prd            # Start: define product requirements
/genops-hld            # Design system architecture
/genops-adr            # Document architectural decisions
/genops-lld            # Specify low-level design
/genops-code           # Implementation plan
```

## Commands

| Command | Scope | Description |
|---------|-------|-------------|
| `/genops-prd` | Product Requirements | Define vision, user stories, success metrics, scope |
| `/genops-hld` | High-Level Design | Architecture topology, components, data flow, NFRs |
| `/genops-adr` | Architecture Decisions | Trade-off analysis, technology selection (incremental) |
| `/genops-lld` | Low-Level Design | Class diagrams, DB schemas, API contracts, modules |
| `/genops-code` | Implementation | Implementation plan, scaffolding, code generation |
| `/genops` | Pipeline Engine | Orchestrate pipeline, check status, start from any stage |
| `/genops-init` | Initializer | Initialize GenOps in any project, validate setup |
| `/genops-status` | Dashboard | Pipeline health report with per-file stale detection |

## Flow Modes

| Mode | Invocation | Behavior |
|------|-----------|----------|
| **SoC** (default) | `/genops-prd` | One stage at a time. After approval, ask: "Next or save for later?" |
| **Flow** | `/genops-prd --flow` | Complete stage, then auto-invoke the next (one-hop cascade) |
| **Nonstop** | `/genops-prd --nonstop` | Run the full pipeline with approval gates at each stage |
| **From** | `/genops --from hld` | Start from any stage (validates all upstream) |

## Document Organization

Files use domain-split naming: `{STAGE}-{NNN}-{descriptive-slug}.md`

```
docs/
├── prd/
│   ├── PRD-001-product-catalog.md       # Single domain = 1 file
│   ├── PRD-002-shopping-cart.md         # Multi-domain = N files
│   └── PRD-003-checkout-payment.md
├── hld/
│   ├── HLD-001-system-topology.md
│   ├── HLD-002-catalog-service.md
│   └── HLD-004-payment-service.md
├── architecture/
│   ├── ADR-001-go-language.md           # One per decision
│   ├── ADR-002-sqlite-storage.md
│   └── ADR-003-cobra-cli-framework.md
├── lld/
│   ├── LLD-001-catalog-schema.md
│   └── LLD-002-payment-contracts.md
├── code/
│   ├── CODE-001-architecture-summary.md
│   ├── CODE-002-catalog-implementation.md
│   └── CODE-003-payment-implementation.md
└── .genops-state.json                   # Per-file hash tracking
```

The domain slug in the filename **is** the agent's navigation system. `grep docs/ payment` finds every file across every layer related to "payment".

## Key Features

### Pre-Flight Validation
Every skill validates its dependencies before executing. Missing upstream stage? Corrupt state file? Uninitialized project? The agent halts with a specific error message and the exact command to fix it.

### Per-File Staleness Detection
Change one PRD file and the agent identifies exactly which downstream files are affected. Not binary stale/not-stale — precision targeting.

### Cross-Layer Validation
PRD→HLD: every user story must map to a component. ADR→LLD: every technology decision must appear in the design. Interface consistency between layers is automatically checked.

### Pipeline Presets
```bash
/genops-init --preset software-spec    # prd → hld → adr → lld → code (default)
/genops-init --preset research         # lit-review → hypothesis → experiment → report
/genops-init --preset design           # brief → wireframes → mockups → prototype
/genops-init --preset custom           # Define your own stages interactively
```

### State Machine
Every stage has a well-defined lifecycle: `absent → drafting → generated → approved → stale`. Per-file hashes detect staleness. Combined hashes drive cascade detection.

## Architecture

```
┌──────────────────────────────────────┐
│  genops.yaml       Pipeline Config    │  Declarative stage definition
├──────────────────────────────────────┤
│  AGENTS.md         Entry Point        │  Agent discovers GenOps here
├──────────────────────────────────────┤
│  genops/SKILL.md   Pipeline Engine    │  Orchestrator + state manager
├──────────────────────────────────────┤
│  genops-stage/     Stage Protocol     │  PRE-FLIGHT → LOAD → DOMAINS →
│  SKILL.md                              │  CHECK → INTERVIEW → GENERATE →
│                                         │  PRESENT → APPROVE → RECORD →
│                                         │  TRANSITION
├──────────────────────────────────────┤
│  genops-prd/hld/   Stage Skills       │  5 domain skills (extend protocol)
│  adr/lld/code/                         │
├──────────────────────────────────────┤
│  .agents/templates/  Templates        │  Per-layer structured output formats
├──────────────────────────────────────┤
│  docs/               Generated Docs   │  Domain-split, per-file hash tracked
├──────────────────────────────────────┤
│  .genops-state.json  State Tracker    │  Per-file hashes + combined hashes
└──────────────────────────────────────┘
```

## Adding Your Own Pipeline

Edit `genops.yaml`:

```yaml
pipeline:
  name: "My Pipeline"
  stages:
    - id: research
      name: "Research Phase"
      focus: "Background research and findings"
      requires: []
      outputs: ["docs/research/"]
      file_pattern: "RSCH-{NNN}-{slug}.md"
      template: "research/template.md.template"
      next: [implementation]

    - id: implementation
      name: "Implementation Phase"
      requires: ["docs/research/"]
      outputs: ["docs/impl/"]
      file_pattern: "IMPL-{NNN}-{slug}.md"
      template: "impl/template.md.template"
      next: []
```

Create matching skill files at `.agents/skills/genops-research/SKILL.md` and `.agents/skills/genops-implementation/SKILL.md`. Create templates. Run `/genops-init` to update AGENTS.md.

## Token Efficiency

GenOps is designed for minimal LLM cost:

| Component | Lines | Load Frequency |
|-----------|-------|---------------|
| genops-stage (protocol) | 63 | Every stage invocation |
| genops (engine) | 31 | Orchestration |
| Stage skills | 19-27 avg | Once per stage run |
| **Hot-path total** | **~118 lines** | 41% under 200-line budget |
| Templates | 23-59 | Only during GENERATE step |

## Requirements

- Any AI coding agent that supports AGENTS.md and SKILL.md (Claude CLI, OpenCode, Gemini CLI)
- No runtime dependencies, no package installation, no language runtime

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). GenOps follows the same pipeline it provides: propose changes via PRD, design via ADR, implement via Code plan.
