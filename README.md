# GenOps — Agent-Native Specification Pipeline

**Declarative. Cascading. Agent-First.**

GenOps is a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages. Each stage is a native agent skill — no custom code, no CLI tools, no installers. Just files that agents discover and execute.

```
/genops-prd ──cascade──> /genops-hld ──cascade──> /genops-adr ──cascade──> /genops-lld ──cascade──> /genops-code
     │                       │                       │                       │                       │
     v                       v                       v                       v                       v
docs/prd/               docs/hld/           docs/architecture/          docs/lld/               src/**/*
```

The terminal stage (`/genops-code`) reads LLD's project structure and scaffolds actual source files using predefined scaffold templates — not documentation about code, but the code itself.

## Why GenOps

AI coding agents are powerful but unfocused. They skip planning, mix concerns, and lose context across long sessions. GenOps enforces structure:

- **One stage at a time** — SoC by design. Each stage handles exactly one layer.
- **Reactive cascading** — Change an upstream doc and all downstream layers detect staleness with per-file precision.
- **Agent-native** — No code. No install. Skills are SKILL.md files discovered by AGENTS.md. Works with Claude CLI, OpenCode, Gemini CLI.
- **Template-driven** — Interview questions and output structure live in templates. Add a pipeline by adding templates, not skills.
- **Scaffold system** — `/genops-code` generates actual project files from LLD design. Go services, React apps, Python APIs — deterministic, tech-stack-aware scaffolding.

## Quick Start

```bash
git clone https://github.com/seismael/genops.git my-project
cd my-project
```

The agent discovers GenOps automatically from `AGENTS.md` and `.agents/skills/`.

```bash
/genops-init           # Initialize (or validate) the project
/genops-prd            # Define product requirements
/genops-hld            # Design system architecture
/genops-adr            # Document architectural decisions
/genops-lld            # Specify low-level design (includes project structure)
/genops-code           # Scaffold actual project from LLD → src/
```

## Commands

| Command | Scope | Description |
|---------|-------|-------------|
| `/genops-prd` | Product Requirements | Define vision, user stories, success metrics, scope |
| `/genops-hld` | High-Level Design | Architecture topology, components, data flow, NFRs |
| `/genops-adr` | Architecture Decisions | Trade-off analysis, technology selection (incremental) |
| `/genops-lld` | Low-Level Design | Entities, schemas, API contracts, **project structure** |
| `/genops-code` | Implementation | Scaffold project from LLD using scaffold templates |
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

Design documents use domain-split naming: `{STAGE}-{NNN}-{descriptive-slug}.md`

```
docs/
├── prd/
│   ├── PRD-001-product-catalog.md       # Single domain = 1 file
│   └── PRD-002-shopping-cart.md         # Multi-domain = N files
├── hld/
│   ├── HLD-001-system-topology.md
│   └── HLD-002-catalog-service.md
├── architecture/
│   ├── ADR-001-go-language.md           # One per decision
│   └── ADR-002-sqlite-storage.md
├── lld/
│   ├── LLD-001-catalog-schema.md        # Defines project structure
│   └── LLD-002-payment-contracts.md
└── .genops-state.json                   # Per-file hash tracking
```

## Project Output

`/genops-code` reads LLD's `## Project Structure` and scaffolds real source files:

```
src/
├── services/                     # Microservices (one per LLD module)
│   ├── user-service/             # Scaffolded from: go-service template
│   │   ├── cmd/main.go
│   │   ├── internal/{handler,service,store}/
│   │   ├── go.mod
│   │   ├── Dockerfile
│   │   └── tests/
│   └── payment-service/          # Same scaffold, different module
├── web/                          # Scaffolded from: react-vite template
│   ├── src/{components,pages,hooks}/
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml
└── README.md
```

Available scaffolds: `go-service`, `react-vite`, `python-fastapi`, `go-library`. See `.agents/scaffolds/`.

## Key Features

### Scaffold Template System
LLD defines modules with scaffold references (`go-service`, `react-vite`, etc.). `/genops-code` loads the scaffold's STRUCTURE.yaml + build templates, generates deterministic project files with entity stubs, tests, and cross-module config. Add a new tech stack by adding a scaffold directory — no skill changes needed.

### Pre-Flight Validation
Every skill validates its dependencies before executing. Missing upstream? Corrupt state? Uninitialized? The agent halts with the exact command to fix it.

### Per-File Staleness Detection
Change one PRD file and the agent identifies exactly which downstream files are affected — precision targeting, not binary stale/not-stale.

### Cross-Layer Validation
PRD→HLD: every user story maps to a component. ADR→LLD: every technology decision appears in the design. Code: every LLD entity has a source file stub.

### Pipeline Presets
```bash
/genops-init --preset software-spec    # prd → hld → adr → lld → code (default)
/genops-init --preset research         # lit-review → hypothesis → experiment → report
/genops-init --preset design           # brief → wireframes → mockups → prototype
/genops-init --preset custom           # Define your own stages interactively
```

### State Machine
Every stage: `absent → drafting → generated → approved → stale`. Per-file hashes detect staleness. Combined hashes drive cascade detection.

## Architecture

```
┌──────────────────────────────────────┐
│  genops.yaml       Pipeline Config    │  Declarative stage definition
├──────────────────────────────────────┤
│  AGENTS.md         Entry Point        │  Agent discovers GenOps here
├──────────────────────────────────────┤
│  genops/SKILL.md   Engine             │  Orchestrator + state manager
├──────────────────────────────────────┤
│  genops-stage/     Stage Protocol     │  11-step template-driven protocol
├──────────────────────────────────────┤
│  genops-{prd,hld,  Stage Skills      │  Thin wrappers (read template → execute)
│   adr,lld,code}/                       │
├──────────────────────────────────────┤
│  .agents/templates/ Templates         │  Interview questions + output structure
├──────────────────────────────────────┤
│  .agents/scaffolds/ Scaffolds         │  Build templates per tech stack
├──────────────────────────────────────┤
│  docs/             Design Docs        │  Domain-split, per-file hash tracked
├──────────────────────────────────────┤
│  src/              Project Output     │  Scaffolded from LLD by /genops-code
└──────────────────────────────────────┘
```

## Adding a Scaffold

1. Create `.agents/scaffolds/<name>/STRUCTURE.yaml`
2. Add build templates (go.mod, package.json, etc.)
3. Reference in LLD's `## Project Structure`

```yaml
# .agents/scaffolds/rust-actix/STRUCTURE.yaml
name: "Rust Actix Service"
language: "Rust"
framework: "Actix Web"
directories: [src/, src/handlers/, src/models/, tests/]
templates:
  Cargo.toml.template: "{module}/Cargo.toml"
  main.rs.template: "{module}/src/main.rs"
entity_stubs:
  handler: "src/handlers/{entity_lower}.rs"
  model: "src/models/{entity_lower}.rs"
```

## Token Efficiency

| Component | Lines | Load Frequency |
|-----------|-------|---------------|
| genops-stage (protocol) | 61 | Every stage invocation |
| genops (engine) | 33 | Orchestration |
| Stage skills | 16-20 avg | Once per stage |
| **Hot-path total** | **~114 lines** | 43% under 200-line budget |
| Templates | 23-59 | Only during GENERATE |
| Scaffolds | Per-module | Only during code stage GENERATE |

## Requirements

- Any AI coding agent that supports AGENTS.md and SKILL.md (Claude CLI, OpenCode, Gemini CLI)
- No runtime dependencies, no package installation

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). GenOps follows its own pipeline: propose via PRD, design via ADR, implement via Code.
