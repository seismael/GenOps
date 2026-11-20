---
updated_at: "2026-11-20T14:00:00Z"
commit_sha: "HEAD"
---
# Known Defects & Architectural Anti-Patterns

[[index|← Back to MOC]]

Full end-to-end platform findings (`AUD-001` through `AUD-065`) are cataloged in `AUDIT.md` at the repository root.

## High-Priority Engine Watchlist
- **AUD-001 / AUD-002 (MCP Parity)**: `MCPServer` `genops_status` and `genops_validate` must share live staleness and full validation logic with CLI `cmd_status` and `_collect_validation`.
- **AUD-003 / AUD-004 / AUD-005 (Example & Template Sync)**: Keep `PRD-domain.md.template` user story extraction, `LLD` `downstream_refs`, and multi-struct Go entity drift checks synchronized with `examples/url-shortener*`.
- **AUD-010 / AUD-039 (Scaffolds & MCP Stdout)**: Avoid raw `print()` inside `ScaffoldingService.scaffold_module` (corrupts MCP stdio stream) and ensure `go-service`, `react-vite`, and `rust-service` entity stubs compile cleanly under `go test` / `npm run build` / `cargo test`.
