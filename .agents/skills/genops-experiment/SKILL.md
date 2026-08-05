---
name: genops-experiment
description: Use when running experiments, collecting data, or analyzing results. Third stage in the Research pipeline.
---

# Experiment
Third stage. Requires Hypothesis. Generates into `docs/experiment/`. **Protocol:** genops-stage — template-driven: reads `research/EXPERIMENT.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/hypothesis/ exists. Hypothesis approved. Template valid.
2. **LOAD** — Read hypothesis files + template.
3. **DOMAINS** — Match from hypothesis.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `EXPR-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed to next stage without explicit approval unless --flow or --nonstop.</HARD-GATE>
