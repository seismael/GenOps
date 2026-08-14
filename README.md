# GenOps — Agent-Native Specification Pipeline

**Declarative. Cascading. Agent-First.**

GenOps is a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages. Each stage is a native agent skill backed by a deterministic, zero-dependency engine (`.agents/scripts/genops.py`) and a Model Context Protocol (MCP) server.

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
- **Universal Agent-Native** — Works out of the box with Claude Code, Cursor, Antigravity, GitHub Copilot, Windsurf, OpenCode, and Gemini.
- **Template-driven with YAML Frontmatter** — Every design doc includes machine-readable metadata headers for deterministic indexing and graph traversal.
- **Scaffold system** — `/genops-code` generates actual project files from LLD design. Go services, React apps, Python APIs — deterministic, tech-stack-aware scaffolding with multi-casing transforms.
- **Model Context Protocol (MCP) Server** — Native tool-calling integration for any MCP-compatible environment.

## Quick Start

```bash
git clone https://github.com/seismael/genops.git my-project
cd my-project
```

Initialize for your coding agent:

```bash
# Sync all agent instruction files (AGENTS.md, CLAUDE.md, Cursor rules, Copilot)
python .agents/scripts/genops.py init --agent all
```

Execute the pipeline:

```bash
/genops-prd            # Define product requirements
/genops-hld            # Design system architecture
/genops-adr            # Document architectural decisions
/genops-lld            # Specify low-level design (includes project structure)
/genops-code           # Scaffold actual project from LLD → src/
```

## Universal Agent Compatibility

GenOps is 100% agent-agnostic and supports multiple integration modalities:

| Agent / Platform | Integration Entrypoint | Setup Command |
|---|---|---|
| **Antigravity / Gemini CLI** | `AGENTS.md` / `GEMINI.md` | `python .agents/scripts/genops.py init --agent antigravity` |
| **Anthropic Claude Code CLI** | `CLAUDE.md` | `python .agents/scripts/genops.py init --agent claude` |
| **Cursor IDE** | `.cursor/rules/genops.mdc` / `.cursorrules` | `python .agents/scripts/genops.py init --agent cursor` |
| **GitHub Copilot** | `.github/copilot-instructions.md` | `python .agents/scripts/genops.py init --agent copilot` |
| **Windsurf Cascade** | `.windsurfrules` | `python .agents/scripts/genops.py init --agent windsurf` |
| **MCP Tool-Calling (Any IDE)** | `.agents/mcp.json` (`genops mcp`) | Add `.agents/mcp.json` to IDE MCP settings |

### Model Context Protocol (MCP) Integration

Any agent environment supporting MCP can expose GenOps tools directly:

```json
{
  "mcpServers": {
    "genops": {
      "command": "python",
      "args": [".agents/scripts/genops.py", "mcp"]
    }
  }
}
```

Exposed MCP tools:
- `genops_validate`: Validates configuration, presets, templates, and scaffolds.
- `genops_status`: Retrieves live pipeline health and staleness graph.
- `genops_hash`: Computes cross-platform LF-normalized SHA-256 hashes.
- `genops_record`: Atomically records stage state and appends to audit log.
- `genops_scaffold`: Expands LLD module stubs and templates into `src/`.

## Commands

| Command | Scope | Description |
|---------|-------|-------------|
| `/genops-prd` | Product Requirements | Define vision, user stories, success metrics, scope |
| `/genops-hld` | High-Level Design | Architecture topology, components, data flow, NFRs |
| `/genops-adr` | Architecture Decisions | Trade-off analysis, technology selection (incremental) |
| `/genops-lld` | Low-Level Design | Entities, schemas, API contracts, **project structure** |
| `/genops-code` | Implementation | Scaffold project from LLD using scaffold templates |
| `/genops` | Pipeline Engine | Orchestrate pipeline, check status, start from any stage |
| `/genops-init` | Initializer | Initialize GenOps across agent entrypoint files |
| `/genops-status` | Dashboard | Pipeline health report with per-file stale detection |

## Flow Modes

| Mode | Invocation | Behavior |
|------|-----------|----------|
| **SoC** (default) | `/genops-prd` | One stage at a time. After approval, ask: "Next or save for later?" |
| **Flow** | `/genops-prd --flow` | Complete stage, then auto-invoke the next (one-hop cascade) |
| **Nonstop** | `/genops-prd --nonstop` | Run the full pipeline with approval gates at each stage |
| **From** | `/genops --from hld` | Start from any stage (validates all upstream) |

## Document Organization

Design documents use domain-split naming: `{STAGE}-{NNN}-{descriptive-slug}.md` with standardized YAML frontmatter headers.

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
├── .genops-state.json                   # State v2.0 per-file LF-hash tracking
└── .genops-events.jsonl                 # Append-only immutable audit trail
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
Every skill validates its dependencies before executing via `python .agents/scripts/genops.py validate`. Missing upstream? Corrupt state? Uninitialized? The agent halts with the exact command to fix it.

### Per-File Staleness Detection
Change one PRD file and the agent identifies exactly which downstream files are affected — precision targeting, not binary stale/not-stale.

### Cross-Layer Validation
PRD→HLD: every user story maps to a component. ADR→LLD: every technology decision appears in the design. Code: every LLD entity has a source file stub.

### Pipeline Presets
```bash
python .agents/scripts/genops.py init --preset software-spec    # prd → hld → adr → lld → code (default)
python .agents/scripts/genops.py init --preset research         # lit-review → hypothesis → experiment → report
python .agents/scripts/genops.py init --preset design           # brief → wireframes → mockups → prototype
```

### State Machine v2.0
Every stage: `absent → drafting → generated → approved → stale`. Per-file LF-normalized hashes detect staleness. Combined hashes drive cascade detection. State tracked in `docs/.genops-state.json` and logged to `docs/.genops-events.jsonl`.

## Architecture

```
┌──────────────────────────────────────┐
│  genops.yaml       Pipeline Config    │  Declarative stage definition + schema
├──────────────────────────────────────┤
│  AGENTS.md/CLAUDE  Entry Points       │  Universal multi-agent instructions
├──────────────────────────────────────┤
│  genops.py         CLI & MCP Server   │  LF-hashing, validation, scaffolding, MCP
├──────────────────────────────────────┤
│  genops/SKILL.md   Engine             │  Orchestrator + state manager
├──────────────────────────────────────┤
│  genops-stage/     Stage Protocol     │  11-step template-driven protocol
├──────────────────────────────────────┤
│  genops-{prd,hld,  Stage Skills      │  Thin wrappers (read template → execute)
│   adr,lld,code}/                       │
├──────────────────────────────────────┤
│  .agents/templates/ Templates         │  YAML frontmatter + interview + output
├──────────────────────────────────────┤
│  .agents/scaffolds/ Scaffolds         │  Build templates per tech stack
├──────────────────────────────────────┤
│  docs/             Design Docs        │  Domain-split, per-file hash tracked
├──────────────────────────────────────┤
│  src/              Project Output     │  Scaffolded from LLD by /genops-code
└──────────────────────────────────────┘
```

## Requirements

- Any AI coding agent (Claude Code, Cursor, Antigravity, GitHub Copilot, Windsurf, OpenCode)
- Python 3.8+ (standard library only, zero external pip dependencies)

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). GenOps follows its own pipeline: propose via PRD, design via ADR, implement via Code.
