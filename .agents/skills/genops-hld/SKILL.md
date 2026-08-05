---
name: genops-hld
description: Use when designing system topology, component boundaries, data flow, and integration points. Second stage. Requires completed PRD.
---

# High-Level Design (HLD)

Second stage. Generates files into `docs/hld/`.

**Protocol:** genops-stage — template-driven: reads `hld/HLD-domain.md.template`.

**Config:** `id: hld`, `requires: [docs/prd/]`, `outputs: docs/hld/`, `file_pattern: HLD-{NNN}-{slug}.md`, `template: hld/HLD-domain.md.template`, `next: [adr]`

## Execution

1. **PRE-FLIGHT** — Docs/prd/ exists with ≥1 PRD file. PRD is `approved`. Template `hld/HLD-domain.md.template` has `## Interview` and `## Output`.
2. **LOAD** — Read all PRD files. Read template. Extract interview + output structure.
3. **DOMAINS** — Match domains from PRD files. Single → one HLD. Multi → one per domain + system topology overview.
4. **CHECK** — Per-file staleness against stored PRD hashes.
5. **INTERVIEW** — Ask template's `## Interview` questions ONE at a time, starting with PRD summary.
6. **GENERATE** — `HLD-NNN-{slug}.md` per domain using template's `## Output`.
7. **VALIDATE** — Run `validation_rules` from genops.yaml for prd→hld transition.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Populate CONTEXT.md with component names.

<HARD-GATE>
Do NOT proceed to /genops-adr without explicit approval at TRANSITION, unless --flow or --nonstop.
</HARD-GATE>
