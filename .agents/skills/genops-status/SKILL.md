---
name: genops-status
description: Use when checking the current state of the GenOps pipeline, identifying stale downstream documents, or seeing which stages need re-generation.
---

# GenOps Status Dashboard

Reads `genops.yaml` and `docs/.genops-state.json` to produce a pipeline health report.

## Pre-Flight Validation

Before ANY display, run these checks:

**GenOps Initialized:**
- Verify `genops.yaml` exists. If missing: "GenOps not initialized. Run /genops-init first."
- Verify `AGENTS.md` contains `<!-- GENOPS:START -->`. If missing: "AGENTS.md missing GenOps markers. Run /genops-init."

**State Availability:**
- Verify `docs/.genops-state.json` is readable. If missing: "No pipeline state found. This pipeline has not been initialized. Run /genops-prd to start." Halt — no state means nothing to report.
- If state JSON is corrupt: "State file corrupted. Backup: `.genops-state.json.bak`. Run /genops-init to repair." Halt.

**Config Match:**
- Compare `pipeline` field in state to `genops.yaml`. If mismatch: "Warning: state file was generated with a different pipeline config. Results may be inaccurate."

## Status Table

After validation passes, present:

```
Pipeline: <name>
Status as of: <current datetime>

┌───────┬───────────┬──────────────────┬─────────────┬──────────────┐
│ Stage │ State     │ Last Run         │ Upstream    │ Downstream   │
├───────┼───────────┼──────────────────┼─────────────┼──────────────┤
│ ...   │ ...       │ ...              │ ...         │ ...          │
└───────┴───────────┴──────────────────┴─────────────┴──────────────┘
```

For each stage from `genops.yaml`, compute:
- **State**: from `.genops-state.json` (approved/stale/drafting/generated/absent/skipped)
- **Last Run**: timestamp from state
- **Upstream**: compare current `requires_hash` → "consistent" / "changed" / "blocked" / "N/A"
- **Downstream**: "consistent" / "at-risk" / "blocked" / "N/A"

After table, list specific staleness issues with per-file granularity:

```
Issues detected:
  ⚠ hld: upstream 'prd' changed (PRD-001-study-tracker-requirements.md hash mismatch).
  → adr, lld, code marked stale.

Recommendation: Run /genops-hld --flow to cascade updates.
```
