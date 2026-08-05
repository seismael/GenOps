---
name: genops-prototype
description: Use when building interactive prototypes, defining interactions, or planning user testing. Final stage in the Design pipeline.
---

# Prototype
Terminal stage. Requires Mockups. Generates into `docs/prototype/`. **Protocol:** genops-stage — template-driven: reads `design/PROTOTYPE.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/mockups/ exists. Mockups approved. Template valid.
2. **LOAD** — Read mockup files + template.
3. **DOMAINS** — Match from mockups.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `PROTO-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage. Terminal: "Pipeline complete."

<HARD-GATE>Do NOT proceed without explicit approval.</HARD-GATE>
