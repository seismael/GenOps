# Changelog

All notable changes to GenOps are documented in this file.

## [3.1.2] — 2026-08-21

### Fixed
- **MCP server broke after deleting a Python install.** `install_global.py` previously baked `sys.executable` (an absolute path to whichever Python ran the installer) into every agent's MCP config. Deleting/upgrading that Python made the `genops` MCP server fail with CPython's `Could not find platform independent libraries <prefix>` error.
- The installer also referenced itself (`install_global.py`) instead of the engine (`genops.py`), so CLI wrappers and the MCP args pointed at the wrong script.
- **MCP server failed to start outside a GenOps project.** The server now starts regardless of CWD, resolves the project root per request (client workspace roots → working directory), and returns a clear error instead of crashing when no project is found.

### Changed
- `install_global.py` now bundles the engine + assets into a stable home (`~/.genops/`), independent of the source repo.
- MCP servers and CLI wrappers now launch through a **self-healing launcher** (`~/.genops/bin/genops`) that re-resolves and validates a working Python interpreter on every launch (`python3` → `python` → `py -3`), so removing or upgrading the system Python no longer breaks GenOps.
- MCP registrations now use the agent-appropriate config shape (`type: stdio` for Claude Code/OpenCode, `disabled`/`autoApprove` for Cline) and an absolute launcher path.
- Added `tests/test_install_global.py` covering launcher templates, MCP entry shapes, and the engine self-test.

## [3.1.1] — 2026-08-20

### Fixed (from end-to-end dogfooding)
- `status` staleness now propagates **transitively** downstream — a PRD change flags HLD→ADR→LLD→code stale, not just the direct child.
- `verify` now distinguishes *verified* from *skipped (toolchain not installed)*, and no longer reports "passed cleanly" when nothing was actually checked.
- Frontmatter/YAML parsing now tolerates a UTF-8 byte-order mark, so Windows `Set-Content`/`Out-File` no longer silently breaks the document index.
- `impact` lists downstream specs in cascade order (HLD→ADR→LLD) instead of graph-traversal order.
- `status` timestamps are now consistent UTC.
- Removed the unused `code/CODE-domain.md.template` (~1.4k tokens of dead weight); the code stage scaffolds `src/`.

## [3.1.0] — 2026-08-20

### Added
- `genops doctor` — one-command health check running all four governance gates (validate, check-rules, drift, verify).
- `genops demo` — scaffolds a throwaway module and verifies it, proving the pipeline end-to-end in one command.
- `genops --version` (and `__version__` in the engine, surfaced via MCP `serverInfo`).
- `CHANGELOG.md`.

### Changed
- **Deterministic hashing** now excludes `__pycache__/`, `*.pyc`, virtualenvs, `node_modules`, and build output (`dist/`, `build/`, `target/`) — restoring true cross-platform determinism.
- **`default_files`** in scaffold `STRUCTURE.yaml` are now actually generated (previously declared-but-ignored).
- **`verify`** now covers Go build, Rust `cargo check`, TypeScript `tsc --noEmit`, and optional `ruff`; skips gracefully when a toolchain is absent.
- **Frontmatter parser** now supports indented multi-line lists and fails loudly on unsupported YAML (block scalars, anchors/aliases/tags) instead of silently corrupting the document index.
- **Zero-dependency YAML parser** now raises a clear error on unsupported constructs; `validate` warns on unsupported JSON-Schema keywords.
- **Brownfield ingestion** now skips `__pycache__` and build directories.
- **`impact`** traversal now honors both `upstream_refs` and `downstream_refs` and uses an O(n) queue.
- **Root discovery** errors out cleanly when no `genops.yaml`/`.git` is found (instead of silently using the drive root).
- **`install_global.py`** rewritten to be portable (self-locating script, `Path.home()`-relative config, `sys.executable` for MCP, JSON backup).
- **State** field renamed `domain_count` → `file_count` (accurate semantics); report HTML is now escaped.
- **Examples** are tracked in git and documented as the golden path; the Python example has a full FastAPI layer, 26 passing tests, SSRF hardening, and fixes for duplicate-shorten, cache correctness, and SQLite DDL drift.

### Fixed
- Research pipeline path mismatch (`docs/lit-review/` → `docs/research/`).
- `go-library` scaffold emitting invalid Go (`package {module_name}` → `package {module_lower}`).
- Scaffold Dockerfiles that required non-generated `go.sum`/`package-lock.json`.
- `.githooks/pre-commit` was non-executable (now `100755`).
- Committed stale state, bytecode (`.pyc`), and `TEMP.md` removed; `.gitignore` hardened.

## [3.0.0] — earlier
- Initial "Super Skills" milestone: Socratic elicitation, dual-pass critic, executable specs (OpenAPI/DDL), polyglot scaffolds, compiler-in-the-loop verify, living-memory compaction.
