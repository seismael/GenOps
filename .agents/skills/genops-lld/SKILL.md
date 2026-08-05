---
name: genops-lld
description: Use when defining class diagrams, database schemas, API contracts, and module interfaces. Fourth stage. Requires completed HLD and ADRs.
---

# Low-Level Design (LLD)

Fourth stage. Generates files into `docs/lld/`.

**Protocol:** genops-stage — template-driven: reads `lld/LLD-domain.md.template`.

**Config:** `id: lld`, `requires: [docs/hld/, docs/architecture/]`, `outputs: docs/lld/`, `file_pattern: LLD-{NNN}-{slug}.md`, `template: lld/LLD-domain.md.template`, `next: [code]`

## Execution

1. **PRE-FLIGHT** — Docs/hld/ + docs/architecture/ exist with files. HLD and ADR are `approved`. Template has `## Interview` and `## Output`. Scan HLD for unresolved items → verify all have ADRs.
2. **LOAD** — Read all HLD + ADR files. Read template. Extract questions + output.
3. **DOMAINS** — Match domains from upstream files.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Start by listing ADR decisions, confirm they still stand. Then ask template questions ONE at a time.
6. **GENERATE** — `LLD-NNN-{slug}.md` per domain using template. Include mermaid ERD.
7. **VALIDATE** — Run `validation_rules` for adr→lld and hld→lld transitions.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Populate CONTEXT.md with entity names.

<HARD-GATE>
Do NOT proceed to /genops-code without explicit approval at TRANSITION, unless --flow or --nonstop.
</HARD-GATE>
