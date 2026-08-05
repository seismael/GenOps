---
name: genops-lit-review
description: Use when conducting a literature review, surveying prior art, or identifying research gaps. First stage in the Research pipeline.
---

# Literature Review
First stage. No upstream dependencies. Generates into `docs/research/`. **Protocol:** genops-stage — template-driven: reads `research/LIT-REVIEW.md.template`.

### Execution
1. **PRE-FLIGHT** — genops.yaml has stage `lit-review`, template exists with `## Interview` + `## Output`.
2. **LOAD** — Read template, extract questions and output structure.
3. **DOMAINS** — Single topic or multiple research areas? One file per domain.
4. **CHECK** — First stage, no upstream.
5. **INTERVIEW** — Template's questions ONE at a time. Required first.
6. **GENERATE** — `LIT-REVIEW-NNN-{slug}.md` per domain.
7. **VALIDATE** — No cross-layer (first stage).
8. **PRESENT → APPROVE → RECORD → TRANSITION** — Per genops-stage.

<HARD-GATE>Do NOT proceed to next stage without explicit approval unless --flow or --nonstop.</HARD-GATE>
