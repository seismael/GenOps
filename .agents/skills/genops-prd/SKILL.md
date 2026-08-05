---
name: genops-prd
description: Use when creating product requirements, defining user stories, establishing success metrics, or scoping a new product/feature. First stage in the GenOps pipeline.
---

# Product Requirements (PRD)

First stage. No upstream dependencies. Generates files into `docs/prd/`.

**Protocol:** genops-stage — template-driven: reads `prd/PRD-domain.md.template`.

**Config:** `id: prd`, `requires: []`, `outputs: docs/prd/`, `file_pattern: PRD-{NNN}-{slug}.md`, `template: prd/PRD-domain.md.template`, `next: [hld]`

## Execution

1. **PRE-FLIGHT** — Run genops-stage checks. Verify genops.yaml has stage `prd`, template `prd/PRD-domain.md.template` exists with `## Interview` and `## Output` sections.
2. **LOAD** — Read template. Extract interview questions and output structure. Load CONTEXT.md.
3. **DOMAINS** — "Single product or multiple independent domains?" Single → one file. Multi → one file per domain.
4. **CHECK** — No upstream (first stage). Check if already run.
5. **INTERVIEW** — Ask questions from template's `## Interview` section, ONE at a time. Required first, optional if needed.
6. **GENERATE** — Generate output using template's `## Output` section structure. `PRD-NNN-{slug}.md` per domain. No placeholders.
7. **VALIDATE** — No cross-layer (first stage, no upstream to validate against).
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Populate CONTEXT.md with domain names and key terms.

<HARD-GATE>
Do NOT proceed to /genops-hld without explicit approval at TRANSITION, unless --flow or --nonstop.
</HARD-GATE>
