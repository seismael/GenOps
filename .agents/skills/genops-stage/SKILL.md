---
name: genops-stage
description: Use when executing any GenOps pipeline stage. Universal cognitive protocol for all GenOps stage skills.
---

# GenOps Super Stage Protocol (v3.0)

Template-driven cognitive protocol: PRE-FLIGHT → LOAD (Budget Guard) → DOMAINS → CHECK → INTERVIEW (Socratic) → GENERATE → VALIDATE (Red-Team & Critic Pass) → PRESENT → APPROVE → RECORD (Compact) → TRANSITION.

Hot-path protocol enforcing architectural integrity, executable specifications, and deterministic state tracking.

<HARD-GATE>
Do NOT skip APPROVE. Do NOT transition without explicit human approval unless --flow or --nonstop. "It looks fine" is NOT approval.
</HARD-GATE>

## 0. PRE-FLIGHT — Dependency & Health Verification
Halt on first failure. Run `python .agents/scripts/genops.py validate` (or MCP `genops_validate`) if available.
- **Init:** AGENTS.md has `<!-- GENOPS:START -->`. `genops.yaml` exists.
- **Stage:** Current stage `id` defined in `genops.yaml`. Output directory exists.
- **Template:** `.agents/templates/<template>` exists with `## Interview` and `## Output` sections.
- **State:** `docs/.genops-state.json` exists (v2.0 schema).
- **Upstream:** Every path in `requires` exists with ≥1 approved artifact.

## 1. LOAD — Context Assembly & Token Budget Guard
Read stage config from `genops.yaml`. Load all upstream documents from `requires` paths. Read stage template. Load `.agents/context/CONTEXT.md` for active system topology, glossary, and architectural constraints.
- **Token Budget Guard:** If upstream documents exceed 60,000 characters (~15,000 tokens), invoke `python .agents/scripts/genops.py context --domain <slug>` to extract only targeted domain slices, preventing context window saturation.

## 2. DOMAINS — Scope & Naming
Enforce domain-split structure: `{STAGE}-{NNN}-{slug}.md`. Target single domain if `--domain <slug>` is specified; otherwise discover all domains from upstream. Auto-increment sequence prefix `NNN`.

## 3. CHECK — Cryptographic Staleness
Compute live LF-normalized SHA-256 hash of all `requires` paths (`python .agents/scripts/genops.py hash <path>`). Compare to recorded `requires_hash`. If identical and state is `approved`, prompt: "Stage already complete and consistent. Re-run?"

## 4. INTERVIEW — Socratic Architectural Challenger
Ask template questions ONE at a time. Do NOT passively record answers:
- **Challenge Premature Complexity:** If target scale/traffic is low, challenge distributed microservices or complex event buses; suggest simpler modular monoliths.
- **Probe Failure Modes:** Demand explicit strategies for latency, network partitions, and data loss.
- **Surface Trade-offs:** Present concrete trade-offs (e.g., Consistency vs. Availability, Latency vs. Throughput, Operational Cost).

## 5. GENERATE — Executable Specification
Generate `<outputs>/<STAGE>-<NNN>-<slug>.md` adhering strictly to template structure with standardized YAML frontmatter (`id`, `domain`, `stage`, `version`, `status`, `upstream_refs`, `downstream_refs`, `tags`).
- Placeholders (`TODO`, `TBD`) are strictly prohibited.
- Technical specs must include concrete schemas, DDL, OpenAPI/contracts, or Mermaid diagrams.
- For `code` stage: execute `python .agents/scripts/genops.py scaffold`.

## 6. VALIDATE — Adversarial Red-Team & Multi-Perspective Critic Pass
Run declarative `validation_rules` from `genops.yaml` and execute an internal Staff Review:
1. **Adversarial Red-Team Stress-Test:** Generate and document mitigations for Concurrency Deadlocks, Latency Saturation Spikes, and Security/Tenancy Breaches.
2. **Security Critic:** Assess STRIDE vectors, auth boundaries, input validation, and secret handling.
3. **Resilience Critic:** Check timeout policies, retry backoffs, circuit breakers, and idempotency keys.
4. **Observability Critic:** Verify OpenTelemetry tracing spans, health metrics, and audit logging.
5. **Consistency:** Verify all upstream "Needs ADR" items are resolved and mapped downstream.
If critical gaps are found, surface recommendations immediately before presentation.

## 7. PRESENT — Preview & Change-Impact Analysis
Display executive summary of generated artifacts, resolved decisions, and downstream impact map (invoke `python .agents/scripts/genops.py impact <spec>` to highlight affected downstream files and modules).

## 8. APPROVE — Human Hard Gate
Require explicit human confirmation ("approved", "proceed", "yes"). If changes are requested, apply delta modifications only and re-run Step 6 (VALIDATE).

## 9. RECORD — Atomic State & Active Memory Compaction
Execute `python .agents/scripts/genops.py record <stage-id> --actor <user|agent>`.
- Updates `docs/.genops-state.json` and appends immutable event to `docs/.genops-events.jsonl`.
- **Memory Compaction:** Extract new domain models, accepted technologies, and constraints; compact and update `.agents/context/CONTEXT.md`.

## 10. TRANSITION — Handoff
- `--nonstop`: Automatically invoke next stage with `--nonstop`.
- `--flow`: Automatically invoke next stage (SoC default).
- Default: "Stage approved. Run /genops-<next> now or save for later?"
- Terminal (`next: []`): "Pipeline complete. Scaffolding ready in src/."
