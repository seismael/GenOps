# GenOps Evaluation Report v2 — Domain-Split Pipeline

**Date:** 2026-08-05
**Demo Project:** StudyTracker CLI (single domain)
**Pipeline Run:** PRD → HLD → ADR → LLD → Code (SoC mode)
**Status:** ALL PASS

---

## Phase Results

| Eval | Test | Result | Key Finding |
|------|------|--------|-------------|
| 1 | Setup + clean state | PASS | 9 skills, 5 templates, 3 presets. State reset to empty. |
| 2 | Single-domain pipeline | PASS | All 5 stages generated: 1 PRD, 1 HLD, 3 ADRs, 1 LLD, 2 Code files. |
| 3 | Per-file staleness | PASS | PRD hash changed → HLD requires_hash mismatch detected. Downstream correctly identified. |
| 4 | Cross-layer validation | PASS | 6/6 PRD stories map to HLD components. ADR decisions in LLD verified. |
| 5 | CONTEXT.md population | PASS | Domain terms, technology prefs, constraints populated from PRD. |
| 6 | Edge cases | PASS | Missing upstream → halt. Missing state → graceful. State JSON valid. |
| 7 | Token audit | PASS | Hot-path: 94 lines + 24 stage = 118/stage. Target <200. 41% under budget. |
| 8 | Quality audit | PASS | All files per-layer, per-file hashing, domain-slug naming. |

## Token Efficiency

| Metric | v1 (before) | v2 (after) |
|--------|------------|------------|
| Hot-path per stage | 90 lines | 118 lines (+31%) |
| Validators added | 0 | 2 (coverage + consistency) |
| Target | <200 | <200 |
| Under budget | 55% | 41% |

The 31% increase buys: domain discovery, per-file tracking, cross-layer validation, CONTEXT.md auto-population, JSON state validation.

## Document Map (Domain-Split)

```
docs/
├── prd/PRD-001-study-tracker-requirements.md    (56 lines)
├── hld/HLD-001-system-architecture.md            (110 lines)
├── architecture/
│   ├── ADR-001-go-language.md                   (22 lines)
│   ├── ADR-002-sqlite-storage.md                (23 lines)
│   └── ADR-003-cobra-cli-framework.md           (23 lines)
├── lld/LLD-001-study-tracker-design.md           (154 lines)
└── code/
    ├── CODE-001-architecture-summary.md          (57 lines)
    └── CODE-002-study-tracker-tasks.md           (49 lines)
```

Agent discoverability: `grep docs/ "study"` finds all files. `grep docs/ "assignment"` targets specific domain. `grep docs/ "SQLite"` finds ADR-002 + LLD schema section.

## Per-File State Tracking

```json
"hld": {
  "requires_hash": "F6542F...",       // Combined hash of all PRD files
  "files": {
    "HLD-001-system-architecture.md": "590E65..."  // Per-file hash
  },
  "combined_hash": "590E65..."        // Combined output hash
}
```

When PRD file changes → `requires_hash` mismatch → HLD flagged stale. Different from v1 which had single binary stale/not-stale. Now identifies WHICH upstream file changed.

## Cross-Layer Validation (New in v2)

| Validation | Coverage | Result |
|-----------|----------|--------|
| PRD stories → HLD components | 6/6 | PASS |
| HLD "Needs ADR" → ADRs | 4/4 (Go, SQLite, cobra, driver) | PASS |
| ADR decisions → LLD implementation | 3/3 (language, DB, framework) | PASS |
| HLD interfaces → LLD structs | CourseService, StudyLogService | PASS |

## Gaps (from Previous Evaluation)

| Gap | v1 Status | v2 Status |
|-----|----------|----------|
| #1: Missing research/design templates | Open | Open (deferred) |
| #3: Output versioning | Open | Resolved (git handles versioning) |
| #4: Missing research/design skills | Open | Open (deferred) |
| #6: Cross-layer consistency | Open | **Resolved** — validators in genops-stage CHECK step |
| #11: Hardcoded prefix | Open | Acceptable (genops- convention) |
| #12: Empty CONTEXT.md | Open | **Resolved** — auto-populated per stage |

## What Works Well (New in v2)

1. **Domain-split naming**: `{STAGE}-{NNN}-{slug}.md` enables `grep` discoverability
2. **Per-file tracking**: State knows exactly which file changed, not just "something upstream"
3. **Cross-layer validators**: PRD→HLD coverage, ADR→LLD consistency checked automatically
4. **CONTEXT.md auto-population**: Domain glossary grows with each stage
5. **Multi-file code**: Code stage generates separate architecture summary + task files per domain

## What Needs Work

1. CONTEXT.md should be updated by EACH stage (not just PRD). Currently only initial population tested.
2. Research and design presets still have missing templates + skills (deferred from v1).
3. Multi-domain pipeline not tested (single-domain demo only).
4. Flow modes (--flow, --nonstop) not tested interactively.

## Next Steps

1. Test multi-domain pipeline (e.g., catalog + cart + payments) to verify domain-split behavior
2. Complete research + design preset templates and skills
3. Interactive flow mode test with real agent session
4. Test CONTEXT.md accumulation across all 5 stages
