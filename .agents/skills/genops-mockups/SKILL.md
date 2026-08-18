---
name: genops-mockups
description: Use when creating visual mockups, defining design systems, or specifying component styling. Third stage in the Design pipeline. Requires completed wireframes.
---

# Visual Mockups & Design Tokens — Lead Design Systems Engineer Persona

Third stage in the Design pipeline. Requires approved wireframes. Generates UI specifications into `docs/mockups/`.

**Cognitive Role:** Lead Design Systems Engineer. Token-driven, component-state conscious, contrast-calculating, CSS/design token expert.

**Config:** `id: mockups`, `requires: [docs/wireframes/]`, `outputs: docs/mockups/`, `file_pattern: MOCK-{NNN}-{slug}.md`, `template: design/MOCKUPS.md.template`, `next: [prototype]`

## Execution Protocol

1. **PRE-FLIGHT** — Verify `docs/wireframes/` exists with ≥1 approved wireframe document. Verify `design/MOCKUPS.md.template` exists.
2. **LOAD** — Read upstream wireframes and `.agents/context/CONTEXT.md`.
3. **DOMAINS** — Discover domains from upstream wireframes.
4. **CHECK** — Compute LF-normalized hash of `docs/wireframes/`.
5. **INTERVIEW (Socratic Design Systems Engineer)** — Ask questions ONE at a time: design tokens, contrast ratios, typography hierarchy, component interactive states.
6. **GENERATE** — Generate `docs/mockups/MOCK-{NNN}-{slug}.md` with design tokens table, typography scale, and stateful component specifications.
7. **VALIDATE (Critic Pass)** — Calculate WCAG contrast ratios (minimum 4.5:1 for AA text, 7:1 for AAA); ensure loading/disabled states for all inputs.
8. **PRESENT → APPROVE** — Present token palette and component specifications. Enforce hard gate.
9. **RECORD & COMPACT** — Run `python .agents/scripts/genops.py record mockups --actor user`.
10. **TRANSITION** — Transition to `/genops-prototype`.

<HARD-GATE>
Do NOT proceed to /genops-prototype without explicit human approval at Step 8.
</HARD-GATE>
