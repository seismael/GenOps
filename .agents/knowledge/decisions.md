---
updated_at: "2026-11-20T14:00:00Z"
commit_sha: "HEAD"
---
# Architectural Decision Log

[[index|← Back to MOC]]

| Decision ID | Date | Area | Decision | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **D-001** | 2026-11-20 | Agent Governance | Unified Zero-Chatter, Token-Economic, First-Principles Rules + RFC-0018 Mutation Exactness | Standardized `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `.cursor/rules/genops.mdc`, `.github/copilot-instructions.md`, `.windsurfrules`, and `CONVENTIONS.md` via `ConfigManager.generate_agent_instructions` |
| **D-002** | 2026-11-20 | Knowledge & Subagents | Bootstrapped `.agents/knowledge/` MOC and `.agents/subagents/` model-tiered personas | Eliminates redundant repository exploration scans and standardizes `pro`/`flash`/`flash_lite` subagent routing |
