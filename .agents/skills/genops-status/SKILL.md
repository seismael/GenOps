---
name: genops-status
description: Use when checking the current state of the GenOps pipeline, identifying stale downstream documents, or seeing which stages need re-generation.
---

# GenOps Status Dashboard

Reads `genops.yaml` and `docs/.genops-state.json` to produce a deterministic pipeline health report. Backed by `python .agents/scripts/genops.py status`.

## Pre-Flight Validation

Before ANY display, run these checks:

**GenOps Initialized:**
- Verify `genops.yaml` exists. If missing: "GenOps not initialized. Run /genops-init first."
- Verify `AGENTS.md` contains `<!-- GENOPS:START -->`. If missing: "AGENTS.md missing GenOps markers. Run /genops-init."

**State Availability:**
- Verify `docs/.genops-state.json` is readable. If missing: "No pipeline state found. Run /genops-prd to start."
- If state JSON is corrupt: "State file corrupted. Run /genops-init to repair."

## Execution

Execute status dashboard:
```bash
python .agents/scripts/genops.py status
```

Presents formatted table:
- **State**: from `.genops-state.json` (approved/stale/drafting/generated/absent/skipped)
- **Last Run**: timestamp from state v2
- **Upstream**: LF-normalized hash comparison → "consistent" / "changed" / "blocked" / "N/A"
- **Downstream**: "consistent" / "at-risk" / "blocked" / "N/A"

Lists specific staleness issues with per-file granularity and recommended next step.
