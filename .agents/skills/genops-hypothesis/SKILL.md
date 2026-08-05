---
name: genops-hypothesis
description: Use when formulating hypotheses, defining variables, or designing experiments. Second stage in the Research pipeline.
---

# Hypothesis
Second stage. Requires Lit Review. Generates into `docs/hypothesis/`. **Protocol:** genops-stage — template-driven: reads `research/HYPOTHESIS.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/research/ exists. Lit-review approved. Template has `## Interview` + `## Output`.
2. **LOAD** — Read lit review files + template.
3. **DOMAINS** — Match from lit review.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `HYPOTH-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules if defined.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed to next stage without explicit approval unless --flow or --nonstop.</HARD-GATE>
