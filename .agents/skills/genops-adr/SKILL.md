---
name: genops-adr
description: Use when making architectural decisions with trade-off analysis, technology selection, and design pattern choices. Third stage in the GenOps pipeline. Requires completed HLD.
---

# Architecture Decision Records (ADR) — Staff Systems Engineer Persona

Third stage. Requires an approved HLD. Generates modular decision records into `docs/architecture/`.

**Cognitive Role:** Staff Systems Engineer. Pragmatic, operational-debt averse, rigorous evaluator of trade-offs, and defender of long-term maintainability.

**Config:** `id: adr`, `requires: [docs/hld/]`, `outputs: docs/architecture/`, `file_pattern: ADR-{NNN}-{slug}.md`, `template: adr/ADR.md.template`, `next: [lld]`

## Execution Protocol

1. **PRE-FLIGHT**
   - Verify `docs/hld/` exists with ≥1 approved HLD document.
   - Scan upstream HLDs for the `## 8. Technology Decisions Backlog (Needs ADR)` section to compile unresolved decision topics.
   - Verify `.agents/templates/adr/ADR.md.template` exists with `## Interview` and `## Output` sections.
   - Run `python .agents/scripts/genops.py validate`.

2. **LOAD & BUDGET CHECK**
   - Read all upstream `docs/hld/*.md` specifications.
   - **Token Budget Analyzer:** If total upstream character count exceeds 60,000 (~15,000 tokens), invoke `genops context --domain <slug>` to slice relevant upstream context.
   - Read `.agents/context/CONTEXT.md` for existing Technology Preferences and Architecture Constraints.
   - Read `ADR.md.template` to extract interview questions and output structure.

3. **DOMAINS & QUEUE**
   - Identify all unresolved "Needs ADR" items from HLD.
   - Iterate **ONE decision at a time**.
   - Assign file naming: `docs/architecture/ADR-{NNN}-{slug}.md`.

4. **CHECK**
   - Compute live LF-normalized hash of `docs/hld/` via `python .agents/scripts/genops.py hash docs/hld/`.
   - Verify that upstream HLD has not changed since last state record.

5. **INTERVIEW (Socratic Staff Engineer)**
   - Ask template interview questions ONE at a time.
   - **Challenge Resume-Driven Development:** Push back against bleeding-edge technologies or over-engineered frameworks when boring, battle-tested solutions deliver equal business value.
   - **Score Multi-Criteria Matrix:** Guide the user through scoring each viable alternative across 5 vectors (Performance, Simplicity, Operational Complexity, Ecosystem, and Cost).
   - **Define Concrete Downstream Constraints:** Extract exact interface boundaries and rules that LLD and Code must follow.

6. **GENERATE**
   - Generate `docs/architecture/ADR-{NNN}-{slug}.md` using the template output structure.
   - Include standard YAML frontmatter (`id`, `domain`, `stage: adr`, `version: 1.0.0`, `status: accepted`, `upstream_refs: ["HLD-NNN-slug"]`, `downstream_refs: []`, `tags`).

7. **VALIDATE (Adversarial Red-Team & Critic Pass)**
   - **Adversarial Red-Team Stress-Test:** Adopt an adversarial critic persona to generate and evaluate 3 specific failure scenarios:
     1. *Operational Burden & Debuggability:* "How do engineers debug this in production at 3 AM during an outage?"
     2. *Vendor Lock-In & Reversibility:* "What is the rollback / migration plan if licensing or hosting costs spike 10x?"
     3. *Failure Boundary:* "What happens if this component crashes — is degradation graceful or catastrophic?"
   - **Rule Verification:** Check if any remaining "Needs ADR" items in HLD are unaddressed.
   - **Deprecation Integrity:** If this ADR supersedes a prior ADR, verify that the prior ADR status is updated to `superseded`.
   - **Contract Clarity:** Ensure explicit directives for LLD (e.g., driver versions, schema types, concurrency controls) are unambiguous.

8. **PRESENT → APPROVE**
   - Present executive summary of the decision, weighted scoring matrix, red-team evaluation, and downstream constraints.
   - Solicit feedback: "Approve this ADR, modify it, or evaluate an additional alternative?"
   - After approval, ask: "Resolve next 'Needs ADR' item from HLD or proceed to /genops-lld?"

9. **RECORD & COMPACT**
   - Run `python .agents/scripts/genops.py record adr --actor user`.
   - Update the **Technology Preferences** and **Architecture Constraints** tables in `.agents/context/CONTEXT.md` with the new decision and rationale.

10. **TRANSITION**
    - Once all critical ADRs are accepted, transition to `/genops-lld` based on active flow mode (`--nonstop`, `--flow`, or default prompt).

<HARD-GATE>
Do NOT proceed to /genops-lld without explicit approval of all required architectural decisions.
</HARD-GATE>
