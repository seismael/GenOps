---
name: genops-stage
description: Use when executing any GenOps pipeline stage. Universal cognitive protocol for all GenOps stage skills.
---

# GenOps Super Stage Protocol (v3.0)

Template-driven cognitive protocol: 1. PRE-FLIGHT → 2. LOAD (Budget Guard) → 3. DOMAINS → 4. CHECK → 5. INTERVIEW (Adaptive Socratic) → 6. GENERATE → 7. VALIDATE (Red-Team & Critic Pass) → 8. PRESENT & APPROVE → 9. RECORD & COMPACT → 10. TRANSITION.

Hot-path protocol enforcing architectural integrity, executable specifications, and deterministic state tracking.

<HARD-GATE>
Do NOT skip Step 8 (APPROVE). Do NOT transition without explicit human confirmation unless `--flow` or `--nonstop`. Never treat unconfirmed guesses as approval.
</HARD-GATE>

## 1. PRE-FLIGHT — Dependency & Health Verification
Halt on first failure. Run `python .agents/scripts/genops.py validate` (or MCP `genops_validate`) if available.
- **Init:** AGENTS.md has `<!-- GENOPS:START -->`. `genops.yaml` exists.
- **Stage:** Current stage `id` defined in `genops.yaml`. Output directory exists.
- **Template:** `.agents/templates/<template>` exists with `## Interview` and `## Output` sections.
- **State:** `docs/.genops-state.json` exists (v2.0 schema).
- **Upstream:** Every path in `requires` exists with ≥1 approved artifact.

## 2. LOAD — Context Assembly & Token Budget Guard
Read stage config from `genops.yaml`. Load all upstream documents from `requires` paths. Read stage template. Load `.agents/context/CONTEXT.md` for active system topology, glossary, and architectural constraints.
- **Token Budget Guard:** If upstream documents exceed 60,000 characters (~15,000 tokens), invoke `python .agents/scripts/genops.py context --domain <slug>` to extract only targeted domain slices, preventing context window saturation.

## 3. DOMAINS — Scope & Naming
Enforce domain-split structure: `{STAGE}-{NNN}-{slug}.md`. Target single domain if `--domain <slug>` is specified; otherwise discover all domains from upstream. Auto-increment sequence prefix `NNN`.

## 4. CHECK — Cryptographic Staleness
Compute live LF-normalized SHA-256 hash of all `requires` paths (`python .agents/scripts/genops.py hash <path>`). Compare to recorded `requires_hash`. If identical and state is `approved`, prompt: "Stage already complete and consistent. Re-run?"

## 5. INTERVIEW — Adaptive Socratic Architectural Challenger
Optimize user time while preserving architectural rigor:
- **Context Pre-Extraction:** Before asking questions, extract every requirement/answer already supplied in the user's prompt and upstream specs; present inferred items briefly for confirmation rather than re-asking known facts.
- **Fast-Track Mode (`--fast`):** If the user passes `--fast` or asks for an immediate draft, synthesize a full draft using context-derived defaults and flag Socratic red-team items inline at Step 8.
- **Focused Questioning:** Ask remaining gaps ONE at a time with progress indicators (`[Question k/N]`) and a concrete `(Recommended)` default:
  - **Challenge Premature Complexity:** If target scale/traffic is low, challenge distributed microservices or complex event buses; suggest simpler modular monoliths.
  - **Probe Failure Modes:** Demand explicit strategies for latency, network partitions, and data loss.
  - **Surface Trade-offs:** Present concrete trade-offs (Consistency vs. Availability, Latency vs. Throughput, Operational Cost).

## 6. GENERATE — Executable Specification
Generate `<outputs>/<STAGE>-<NNN>-<slug>.md` adhering strictly to template structure with standardized YAML frontmatter (`id`, `domain`, `stage`, `version`, `status: draft`, `created_at`, `updated_at`, `upstream_refs`, `downstream_refs`, `tags`).
- Placeholders (`TODO`, `TBD`) are strictly prohibited.
- Technical specs must include concrete schemas, DDL, OpenAPI 3.1 / RFC 9457 contracts, or Mermaid diagrams.
- For `code` stage: execute `python .agents/scripts/genops.py scaffold`.

## 7. VALIDATE — Adversarial Red-Team & Multi-Perspective Critic Pass
Run declarative `validation_rules` via `python .agents/scripts/genops.py check-rules` and execute an internal Staff Review:
1. **Adversarial Red-Team Stress-Test:** Generate and document mitigations for Concurrency Deadlocks, Latency Saturation Spikes, and Security/Tenancy Breaches.
2. **Security Critic:** Assess STRIDE vectors, auth boundaries, input validation, and secret handling.
3. **Resilience Critic:** Check timeout policies, retry backoffs, circuit breakers, and idempotency keys.
4. **Observability Critic:** Verify OpenTelemetry tracing spans (`traceparent`), health metrics (`/healthz`), and audit logging.
5. **Consistency:** Verify all upstream "Needs ADR" items are resolved and mapped downstream.
If critical gaps are found, surface recommendations immediately before presentation.

## 8. PRESENT & APPROVE — Preview, Change-Impact & Human Hard Gate
Display executive summary of generated artifacts, resolved decisions, and downstream impact map (`python .agents/scripts/genops.py impact <spec>`).
Present clear structured confirmation options:
1. **Approve & Record Stage** (`approved`, `proceed`, `yes`, `lgtm` when explicitly confirming this gate)
2. **Request Modifications** (apply delta modifications only and re-run Step 7)
3. **Save Draft for Later** (keep `status: draft` without cascading)

## 9. RECORD & COMPACT — Atomic State & Active Memory Compaction
Execute `python .agents/scripts/genops.py record <stage-id> --actor <user|agent>`.
- Automatically promotes `status: draft` frontmatter in stage outputs to `approved` (`accepted` for ADRs), updates `docs/.genops-state.json`, appends a hash-chained event to `docs/.genops-events.jsonl`, and compacts `.agents/context/CONTEXT.md`.

## 10. TRANSITION — Handoff
- `--nonstop`: Automatically invoke next stage with `--nonstop`.
- `--flow`: Automatically invoke next stage (SoC default).
- Default: "Stage approved. Run /genops-<next> now or save for later?"
- Terminal (`next: []`): "Pipeline complete. Scaffolding ready in src/."
