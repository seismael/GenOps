---
name: genops-wireframes
description: Use when creating wireframes, user flows, or information architecture. Second stage in the Design pipeline.
---

# Wireframes
Second stage. Requires Brief. Generates into `docs/wireframes/`. **Protocol:** genops-stage — template-driven: reads `design/WIREFRAMES.md.template`.

### Execution
1. **PRE-FLIGHT** — Docs/brief/ exists. Brief approved. Template valid.
2. **LOAD** — Read brief files + template.
3. **DOMAINS** — Match from brief.
4. **CHECK** — Per-file staleness.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `WIRE-NNN-{slug}.md` per domain.
7. **VALIDATE** — Run validation_rules.
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed without explicit approval unless --flow or --nonstop.</HARD-GATE>
