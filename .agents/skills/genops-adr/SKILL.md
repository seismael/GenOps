---
name: genops-adr
description: Use when making architectural decisions with trade-off analysis, technology selection, and design pattern choices. Third stage. Requires completed HLD.
---

# Architecture Decision Records (ADR)

Third stage. Generates ONE ADR at a time into `docs/architecture/`.

**Protocol:** genops-stage — template-driven: reads `adr/ADR.md.template`.

**Config:** `id: adr`, `requires: [docs/hld/]`, `outputs: docs/architecture/`, `file_pattern: ADR-{NNN}-{slug}.md`, `template: adr/ADR.md.template`, `next: [lld]`

## Execution

1. **PRE-FLIGHT** — Docs/hld/ exists with ≥1 HLD file. HLD is `approved`. Template `adr/ADR.md.template` has `## Interview` and `## Output`. Scan HLD for "Needs ADR" items.
2. **LOAD** — Read all HLD files. Read template. Extract interview + output structure.
3. **CHECK** — Per-file staleness against stored HLD hashes.
4. **INTERVIEW** — ONE decision at a time using template's `## Interview`. Suggest HLD "Needs ADR" items first. After each: "Another decision or move to /genops-lld?" Auto-increment NNN.
5. **GENERATE** — `ADR-NNN-{slug}.md` per decision using template's `## Output`.
6. **VALIDATE** — Run `validation_rules` for hld→adr transition. All "Needs ADR" items resolved?
7. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Populate CONTEXT.md with technology decisions.

<HARD-GATE>
Do NOT proceed to /genops-lld without explicit approval at TRANSITION, unless --flow or --nonstop.
</HARD-GATE>
