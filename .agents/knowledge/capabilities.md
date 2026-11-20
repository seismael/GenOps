---
updated_at: "2026-11-20T14:00:00Z"
commit_sha: "HEAD"
---
# Project Capabilities & Tooling Registry

[[index|← Back to MOC]]

## CLI & MCP Surfaces (`.agents/scripts/genops.py`)

| Command / MCP Tool | Invoke | Purpose |
| :--- | :--- | :--- |
| `init` | `python .agents/scripts/genops.py init [--preset <name>] [--agent <target>]` | Sync `GENOPS:START/END` instructions across agent files |
| `validate` / `genops_validate` | `python .agents/scripts/genops.py validate` | Validate `genops.yaml`, presets, templates, scaffolds, state |
| `doctor` | `python .agents/scripts/genops.py doctor` | Run `validate`, `check-rules`, `drift`, and `verify` in one pass |
| `status` / `genops_status` | `python .agents/scripts/genops.py status` | Live pipeline health and transitive staleness table |
| `hash` / `genops_hash` | `python .agents/scripts/genops.py hash <path>` | Compute LF-normalized SHA-256 file or Merkle directory digest |
| `record` / `genops_record` | `python .agents/scripts/genops.py record <stage> --actor <actor>` | Record approved stage hashes and compact `CONTEXT.md` |
| `scaffold` / `genops_scaffold` | `python .agents/scripts/genops.py scaffold --module <m> --scaffold <s> --entities <e>` | Generate Clean/Hexagonal module from `.agents/scaffolds/` |
| `drift` / `genops_drift` | `python .agents/scripts/genops.py drift` | Verify LLD entities match `src/` implementation stubs |
| `check-rules` / `genops_check_rules` | `python .agents/scripts/genops.py check-rules` | Verify bidirectional `upstream_refs` / `downstream_refs` DAG |
| `rtm` / `genops_rtm` | `python .agents/scripts/genops.py rtm` | Build Requirements Traceability Matrix from PRD to downstream specs |
| `impact` | `python .agents/scripts/genops.py impact <spec>` | Simulate blast radius across downstream specs and source files |
| `context` / `genops_context` | `python .agents/scripts/genops.py context --domain <slug>` | Extract domain-sliced specifications for token budget guarding |
| `verify` / `genops_verify` | `python .agents/scripts/genops.py verify` | Run polyglot compiler/linter checks across `src/` |

## Verification Lanes

| Lane | Command | Scope |
| :--- | :--- | :--- |
| **Unit Tests** | `python -B -m unittest discover -s tests -p "test_*.py"` | 47+ unit & integration tests |
| **Governance Gate** | `python -B .agents/scripts/genops.py doctor` | Full schema, rule, drift, and compiler check |
| **KB Validator** | `python -B "C:/Users/ahmad pc/.gemini/config/skills/knowledge/scripts/validate_knowledge.py" .agents/knowledge` | Knowledge base MOC & byte ceiling check |
