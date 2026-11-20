---
updated_at: "2026-11-20T14:00:00Z"
commit_sha: "HEAD"
---
# Architecture & System Topology

[[index|← Back to MOC]]

## 1. Tech Stack & Runtime Constraints
- **Language & Floor**: Python 3.8+ standard library only (`zero third-party pip dependencies`).
- **Cross-Platform**: Windows, macOS, and Linux compatible with LF-normalized hashing.
- **Protocol Surfaces**: CLI (`genops.py`), JSON-RPC 2.0 stdio MCP Server (`genops.py mcp`), and 17 native Markdown agent skills (`.agents/skills/`).

## 2. Subsystem Breakdown

| Subsystem | Path | Responsibility |
| :--- | :--- | :--- |
| **Core Engine** | `.agents/scripts/genops.py` | 8-domain deterministic engine (hashing, schema validation, YAML/MD AST parsing, state lock, lineage graph, anti-drift, RTM, MCP server, CLI) |
| **Global Installer** | `.agents/scripts/install_global.py` | Bundles `.agents/` to `~/.genops/`, writes self-healing launchers (`cmd`/`ps1`/`sh`), registers MCP across hosts |
| **Pipeline Presets** | `genops.yaml`, `.agents/presets/*.yaml` | Declarative pipeline definitions (`software-spec`, `research`, `design`) |
| **JSON Schemas** | `.agents/schemas/*.schema.json` | Draft-07 schemas for `genops.yaml`, `STRUCTURE.yaml`, and `.genops-state.json` |
| **Stage Skills** | `.agents/skills/genops*/SKILL.md` | 17 modular skills governed by `genops-stage` 11-step protocol |
| **Spec Templates** | `.agents/templates/**/*.template` | 12 Socratic interview + YAML-frontmatter output templates |
| **Code Scaffolds** | `.agents/scaffolds/*/` | 6 polyglot Clean/Hexagonal scaffolds (`fastapi-service`, `go-service`, `go-library`, `ts-node-service`, `react-vite`, `rust-service`) |
| **Golden Examples** | `examples/url-shortener*` | Reference single-service (Python/FastAPI) and clustered (Go) specifications + code |
