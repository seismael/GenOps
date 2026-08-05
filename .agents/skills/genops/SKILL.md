---
name: genops
description: Use when orchestrating the GenOps pipeline, checking status, starting from a specific stage, or running the full cascade.
---

# GenOps Pipeline Engine

Orchestrates pipeline stages defined in `genops.yaml`. Reads config, validates graph, coordinates execution, manages state.

## Pre-Flight Validation

Before ANY action, run these checks. Halt on first failure.

**Init:** AGENTS.md has `<!-- GENOPS:START -->`. genops.yaml exists. "Run /genops-init first." if missing.

**Config:** Read genops.yaml. Verify pipeline + stages exist. Every stage `id` has skill at `.agents/skills/genops-<id>/SKILL.md`. Every `next` ref valid. Every `template` exists with `## Interview` and `## Output` sections.

**State:** `.genops-state.json` readable. Create empty if missing. Warn if pipeline field mismatch from genops.yaml.

## State Management

Each stage: `state`, `last_run`, `requires_hash`, `files` (per-file hashes), `combined_hash`, `output_dir`, `domain_count`.

## Staleness Detection

Compute combined hash of all files in `requires` directories → compare to stored `requires_hash`. Different → upstream changed → mark stage + downstream `stale`. Per-file hashes identify which specific file changed. Output hash mismatch → manual edit warning.

## Status Dashboard (`/genops --status`)

Table: stage | state | last run | upstream | downstream. Highlight stale. Per-file granularity in issue summary.

## Flow Modes

| Invocation | Behavior |
|-----------|----------|
| `/genops-<stage>` | SoC: one stage. After approve → "Run next or save?" |
| `/genops-<stage> --flow` | Stage → auto-start next (one hop) |
| `/genops-<stage> --nonstop` | Stage → full cascade with approval gates |
| `/genops --from <id>` | Start at stage. Validate all upstream. |
| `/genops --nonstop` | Run remaining with --nonstop. |
| `/genops --status` | Pipeline health dashboard. |

## Stage Protocol

All stages follow **genops-stage**: PRE-FLIGHT → LOAD → DOMAINS → CHECK → INTERVIEW → GENERATE → VALIDATE → PRESENT → APPROVE → RECORD → TRANSITION (11 steps). Stage skills read their template's `## Interview` and `## Output` sections to drive execution.

## Transition Logic
- `--nonstop` → next with `--nonstop`
- `--flow` → next (SoC default)
- Default → offer next or save
- Terminal (`next: []`) → "Pipeline complete."
