---
name: genops-code
description: Use when generating implementation plans, scaffolding project structure, or creating code files from LLD. Final stage. Requires completed LLD.
---

# Implementation (Code)

Terminal stage. Generates files into `docs/code/`.

**Protocol:** genops-stage — template-driven: reads `code/CODE-domain.md.template`.

**Config:** `id: code`, `requires: [docs/lld/]`, `outputs: docs/code/`, `file_pattern: CODE-{NNN}-{slug}.md`, `template: code/CODE-domain.md.template`, `next: []`

## Execution

1. **PRE-FLIGHT** — Docs/lld/ exists with ≥1 LLD file. LLD is `approved`. Template has `## Interview` and `## Output`. Terminal stage — no downstream validation needed.
2. **LOAD** — Read all LLD files. Read template. Extract questions + output.
3. **DOMAINS** — Match domains from LLD files. Generate at minimum: architecture summary + one task doc per domain.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Start with LLD summary. Ask template questions ONE at a time. Output mode: plan, scaffold, or full generation.
6. **GENERATE** — `CODE-001-architecture-summary.md` + `CODE-NNN-{domain}-implementation.md` per domain. Task files use TDD format: test → fail → implement → pass → commit.
7. **VALIDATE** — Run `validation_rules` for lld→code transition.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Terminal: "Pipeline complete." Populate CONTEXT.md with tech stack.

<HARD-GATE>
Full generation: ALWAYS present for review. NEVER commit without approval.
</HARD-GATE>
