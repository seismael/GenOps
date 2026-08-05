---
name: genops-mockups
description: Use when creating visual mockups, defining design systems, or specifying component styling. Third stage in the Design pipeline.
---

# Mockups
Third stage. Requires Wireframes. Generates into `docs/mockups/`. **Protocol:** genops-stage — template-driven: reads `design/MOCKUPS.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/wireframes/ exists. Wireframes approved. Template valid.
2. **LOAD** — Read wireframe files + template.
3. **DOMAINS** — Match from wireframes.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `MOCK-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed without explicit approval unless --flow or --nonstop.</HARD-GATE>
