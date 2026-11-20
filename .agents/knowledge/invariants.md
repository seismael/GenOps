---
updated_at: "2026-11-20T14:00:00Z"
commit_sha: "HEAD"
---
# System Invariants & Non-Negotiable Rules

[[index|← Back to MOC]]

## 1. Engine & Protocol Invariants
- **[INV-01] Zero External Dependencies**: `.agents/scripts/genops.py` and `.agents/scripts/install_global.py` must import only Python 3.8+ standard library modules (optional `yaml` import must always have a working stdlib fallback).
- **[INV-02] LF-Normalized Cryptographic Determinism**: All file and directory SHA-256 digests (`DeterministicHasher`) must normalize `\r\n` and `\r` to `\n` and skip volatile caches (`__pycache__`, `.git`, `node_modules`) so hashes match across OS platforms.
- **[INV-03] MCP Stdio Stream Purity**: During `genops mcp`, `sys.stdout` carries exclusively JSON-RPC 2.0 messages. No service called by `MCPServer.dispatch()` may print human text to `stdout`.
- **[INV-04] Path Traversal Isolation**: Every path resolved from user, template, scaffold, or MCP arguments must pass `ScaffoldingService.is_safe_subpath` before read/write.
- **[INV-05] Separation of Concerns & Hard Approval Gate**: Every pipeline stage enforces `PRE-FLIGHT -> LOAD -> DOMAINS -> CHECK -> INTERVIEW -> GENERATE -> VALIDATE -> PRESENT -> APPROVE -> RECORD -> TRANSITION` with zero `TODO`/`TBD` placeholders.
- **[INV-06] Workspace & Test Hygiene**: Tests must execute inside `tempfile.TemporaryDirectory` without leaking stray folders into the workspace or parent directories.
