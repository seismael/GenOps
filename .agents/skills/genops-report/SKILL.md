---
name: genops-report
description: Use when writing research papers, compiling findings, or generating figures. Final stage in the Research pipeline.
---

# Report
Terminal stage. Requires Experiment. Generates into `docs/report/`. **Protocol:** genops-stage — template-driven: reads `research/REPORT.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/experiment/ exists. Experiment approved. Template valid.
2. **LOAD** — Read experiment files + template.
3. **DOMAINS** — Match from experiment.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `RPRT-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Terminal: "Pipeline complete."

<HARD-GATE>Do NOT proceed without explicit approval.</HARD-GATE>
