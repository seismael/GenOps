---
name: genops-wireframes
description: Use when creating wireframes, user flows, or information architecture. Second stage in the Design pipeline. Requires completed design brief.
---

# Wireframes & IA — Staff Information Architect Persona

Second stage in the Design pipeline. Requires approved brief. Generates structural wireframes into `docs/wireframes/`.

**Cognitive Role:** Staff Information Architect. Navigation purist, user flow optimizer, layout structuring expert.

**Config:** `id: wireframes`, `requires: [docs/brief/]`, `outputs: docs/wireframes/`, `file_pattern: WIRE-{NNN}-{slug}.md`, `template: design/WIREFRAMES.md.template`, `next: [mockups]`

## Execution Protocol

1. **PRE-FLIGHT** — Verify `docs/brief/` exists with ≥1 approved brief. Verify `design/WIREFRAMES.md.template` exists.
2. **LOAD** — Read upstream brief documents and `.agents/context/CONTEXT.md`.
3. **DOMAINS** — Discover domains from upstream brief.
4. **CHECK** — Compute LF-normalized hash of `docs/brief/` via `python .agents/scripts/genops.py hash docs/brief/`.
5. **INTERVIEW (Socratic Information Architect)** — Ask questions ONE at a time: global IA, critical conversion sequence, ASCII layouts.
6. **GENERATE** — Generate `docs/wireframes/WIRE-{NNN}-{slug}.md` with Mermaid sitemaps, user flows, and wireframe layouts.
7. **VALIDATE (Critic Pass)** — Verify 100% of user personas from brief have mapped flows; verify mobile and desktop breakpoints.
8. **PRESENT → APPROVE** — Present wireframes and sitemaps. Enforce hard gate.
9. **RECORD & COMPACT** — Run `python .agents/scripts/genops.py record wireframes --actor user`.
10. **TRANSITION** — Transition to `/genops-mockups`.

<HARD-GATE>
Do NOT proceed to /genops-mockups without explicit human approval at Step 8.
</HARD-GATE>
