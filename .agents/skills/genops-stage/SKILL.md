---
name: genops-stage
description: Use when executing any GenOps pipeline stage. All GenOps stage skills follow this protocol.
---

# GenOps Stage Protocol

Template-driven protocol: PRE-FLIGHT → LOAD → DOMAINS → CHECK → INTERVIEW → GENERATE → VALIDATE → PRESENT → APPROVE → RECORD → TRANSITION.

The stage skill reads its template from `.agents/templates/<template>`. The template defines both interview questions (`## Interview` section) and output structure (`## Output` section). This protocol works for ANY domain — software, research, design, or custom.

<HARD-GATE>
Do NOT skip APPROVE. Do NOT transition without user approval unless --flow or --nonstop.
</HARD-GATE>

## 0. PRE-FLIGHT — Validate dependencies

Halt on first failure with error + fix command.

**Init check:** AGENTS.md has `<!-- GENOPS:START -->`. genops.yaml exists. "Run /genops-init first." if missing.

**Stage check:** This stage `id` exists in genops.yaml.

**Template check:** `.agents/templates/<template>` exists and has both `## Interview` and `## Output` sections. "Template missing or incomplete. Run /genops-init."

**State check:** `.genops-state.json` readable. Create if missing. "State corrupted. Recover from git or run /genops-init."

**Upstream check:** Each `requires` directory exists with ≥1 matching file. Upstream stage is `approved`. If absent/skipped: "Run /genops-<upstream> first." Stale: warn. Generated: warn.

**Directory check:** Output directory exists.

<HARD-GATE>
Do NOT proceed past PRE-FLIGHT if any required check fails.
</HARD-GATE>

## 1. LOAD
Read stage config from `genops.yaml`. Load all files from `requires` directories. Load template. Extract `## Interview` questions and `## Output` structure. Load `.agents/context/CONTEXT.md`.

## 2. DOMAINS
"Single-domain or multi-domain?" Single → one file per layer. Multi → one file per domain per layer. Match domains from upstream stage files. Auto-increment NNN from existing files in output directory.

## 3. CHECK — Staleness detection
Compute hash of each upstream file. Compare to stored per-file hashes. If changed → identify which file. If same combined hash → "Already complete. Re-run?"

## 4. INTERVIEW — Template-driven
For each domain, read questions from template's `## Interview` section. Ask ONE at a time. Prefer multiple-choice if template provides options. Use upstream docs + CONTEXT.md for context. Required questions first, optional if needed.

## 5. GENERATE — Template-driven (or scaffold-driven for code stage)
For non-code stages: generate output using template's `## Output` section structure. Output: `<outputs>/<STAGE>-<NNN>-<slug>.md`. Show progress: "Generating domain X/Y: <domain>". No TBD, TODO, or placeholder sections.

For code stage: read LLD's `## Project Structure` → Modules table. Load scaffold templates from `.agents/scaffolds/`. Generate actual project files in `src/`. See genops-code SKILL.md for scaffold protocol.

## 6. VALIDATE — Cross-layer checks
If `genops.yaml` defines `validation_rules` for this stage transition, run them. Generic pattern: verify items from upstream stage map to items in generated output. Flag uncovered items. Also verify: no upstream "Needs ADR" or "open question" items remain unresolved. Apply interface/structure consistency checks if defined.

Report gaps: "Validation found N issues. Fix or proceed?"

## 7. PRESENT
Show summary of each generated file + downstream impact map. Mark downstream as "will become stale" if approved.

## 8. APPROVE
Loop until explicit approval ("approved", "proceed", "yes"). Change request: apply only requested, re-PRESENT. Reject: "Re-interview or halt?"

<HARD-GATE>
"It looks fine" is NOT approval.
</HARD-GATE>

## 9. RECORD — Per-file state
Compute hash per output file, combined output hash, combined requires hash. Validate JSON. Update `.genops-state.json`:
```json
"<stage-id>": {"state":"approved","last_run":"<ISO8601>","requires_hash":"<h>","output_dir":"<p>","domain_count":<N>,"files":{"<f>":"<h>"},"combined_hash":"<h>"}
```
Mark downstream `stale`. Append key terms to CONTEXT.md.

## 10. TRANSITION
- `--nonstop` → next stage with `--nonstop`
- `--flow` → next stage (SoC default)
- Default → "Stage done. Run /genops-<next> now or save for later?"
- Multiple `next`: list all options
- `next: []` → "Pipeline complete."

<HARD-GATE>
SoC mode: wait for explicit user choice.
</HARD-GATE>

## State Machine
```
absent → drafting → generated → approved → stale → drafting
absent → skipped
```
