---
name: genops-brief
description: Use when creating a design brief, defining project goals, or establishing brand guidelines. First stage in the Design pipeline.
---

# Design Brief
First stage. No upstream. Generates into `docs/brief/`. **Protocol:** genops-stage — template-driven: reads `design/BRIEF.md.template`.

### Execution
1. **PRE-FLIGHT** — genops.yaml has stage `brief`, template valid.
2. **LOAD** — Read template.
3. **DOMAINS** — Single or multi-section? One file per domain.
4. **CHECK** — First stage.
5. **INTERVIEW** — Template questions ONE at a time.
6. **GENERATE** — `BRIEF-NNN-{slug}.md` per domain.
7. **VALIDATE** — No cross-layer (first stage).
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed to next stage without explicit approval unless --flow or --nonstop.</HARD-GATE>
