---
name: genops
description: Use when orchestrating the GenOps pipeline, checking status, starting from a specific stage, or running the full cascade.
---

# GenOps Pipeline Engine

Orchestrates pipeline stages defined in `genops.yaml`. Reads config, validates graph, coordinates execution, manages state. Backed by deterministic CLI helper `.agents/scripts/genops.py`.

## Pre-Flight Validation

Before ANY action, run these checks. Halt on first failure.

**Init:** AGENTS.md has `<!-- GENOPS:START -->`. genops.yaml exists. "Run /genops-init first." if missing.

**Config:** Validate via `python .agents/scripts/genops.py validate`. Verify pipeline + stages exist. Every stage `id` has skill at `.agents/skills/genops-<id>/SKILL.md`. Every `next` ref valid. Every `template` exists with `## Interview` and `## Output` sections.

**State:** `docs/.genops-state.json` readable (v2.0 schema). Create if missing. Warn if pipeline field mismatch from genops.yaml.

## State Management

Each stage: `state`, `last_run`, `requires_hash`, `files` (per-file LF-normalized SHA-256), `combined_hash`, `output_dir`, `domain_count`, `approved_by`. Append-only event history logged in `docs/.genops-events.jsonl`.

## Staleness Detection

Compute combined LF-normalized hash of all files in `requires` directories (`python .agents/scripts/genops.py hash <dir>`) → compare to stored `requires_hash`. Different → upstream changed → mark stage + downstream `stale`. Per-file hashes identify which specific file changed.

## Status Dashboard (`/genops --status`)

Run `python .agents/scripts/genops.py status`. Outputs table: stage | state | last run | upstream | downstream. Highlight stale.

## Flow Modes

| Invocation | Behavior |
|-----------|----------|
| `/genops-<stage>` | SoC: one stage. After approve → "Run next or save?" |
| `/genops-<stage> --domain <slug>` | Targeted: Execute or modify only specified domain |
| `/genops-<stage> --flow` | Stage → auto-start next (one hop) |
| `/genops-<stage> --nonstop` | Stage → full cascade with approval gates |
| `/genops --from <id>` | Start at stage. Validate all upstream. |
| `/genops --from <id> --domain <slug>` | Incremental cascade for single domain. |
| `/genops --nonstop` | Run remaining with --nonstop. |
| `/genops --status` | Pipeline health dashboard. |

## Stage Protocol

All stages follow **genops-stage**: PRE-FLIGHT → LOAD → DOMAINS → CHECK → INTERVIEW → GENERATE → VALIDATE → PRESENT → APPROVE → RECORD → TRANSITION (11 steps). Non-code stages generate documents with YAML frontmatter from templates. Code stage uses scaffold templates via `python .agents/scripts/genops.py scaffold`.

## Transition Logic
- `--nonstop` → next with `--nonstop`
- `--flow` → next (SoC default)
- Default → offer next or save
- Terminal (`next: []`) → "Pipeline complete."
