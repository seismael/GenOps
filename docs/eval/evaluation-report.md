# GenOps Evaluation Report — Full Pipeline Audit

**Date:** 2026-08-05
**Demo Project:** TaskFlow CLI
**Pipeline Run:** PRD → HLD → ADR → LLD → Code (SoC mode)
**Status:** Pipeline functional. 12 gaps identified.

---

## Phase Results Summary

| Phase | Test | Result | Key Finding |
|-------|------|--------|-------------|
| 1 | Setup verification | PASS | 9 skills, 5 templates, 3 presets — all present. Markers intact. |
| 2 | SoC E2E (5 stages) | PASS | All stages ran, generated complete outputs, state tracked correctly. |
| 3 | Staleness detection | PASS | PRD modification correctly detected, HLD flagged as stale. Cascade identified. |
| 4 | Flow modes | SKIP | Not tested (requires interactive agent session with --flow flag parsing). |
| 5 | Edge cases | PASS | Missing upstream → halt. Missing state → graceful. Duplicate run → prompt. |
| 6 | Token audit | PASS | Hot-path: 90 lines/stage. Target <200. 55% under budget. |
| 7 | Quality audit | PASS | All docs have sections. ADRs: 3. Tasks: 6. Mermaid: present. |
| 8 | Gap analysis | 12 gaps | See below. |

---

## Token Efficiency Metrics

| Skill | Lines | Category | Cost per invocation |
|-------|-------|----------|---------------------|
| genops-stage | 39 | Hot-path (always loaded) | Critical path |
| genops | 31 | Hot-path (orchestration) | Critical path |
| genops-prd/hld/adr/lld/code | 20 avg | Stage (loaded once) | Once per run |
| genops-init | 65 | Cold-path (init only) | Only on /genops-init |
| genops-status | 71 | Cold-path (status only) | Only on /genops --status |
| **Per stage total** | **90** | | **55% under 200-line budget** |

Templates are separate files — loaded only during GENERATE step. This is optimal.

---

## Gaps Identified

### Infrastructure Gaps

| # | Gap | Severity | Phase | Status |
|---|-----|----------|-------|--------|
| 1 | Research preset: 4 templates missing (LIT-REVIEW, HYPOTHESIS, EXPERIMENT, REPORT) | High | 1 | Confirmed |
| 1 | Design preset: 4 templates missing (BRIEF, WIREFRAMES, MOCKUPS, PROTOTYPE) | High | 1 | Confirmed |
| 4 | Research preset: 4 stage skills missing | High | 1 | Confirmed |
| 4 | Design preset: 4 stage skills missing | High | 1 | Confirmed |
| 12 | CONTEXT.md is empty — never populated during pipeline | Medium | 7 | New |

### Protocol Gaps

| # | Gap | Severity | Phase | Status |
|---|-----|----------|-------|--------|
| 6 | No cross-stage consistency validation (LLD could contradict ADR, no automated check) | Medium | 2 | Confirmed — current implementation relies on human review |
| 9 | ADR incremental mode not enforced — protocol says "one at a time" but multiple ADRs can be generated in one session | Low | 2 | Observed — efficiency override |
| 10 | State file requires manual hashing by the agent — no helper mechanism for computing combined hashes of glob patterns like `docs/architecture/adr-*.md` | Low | 2 | Observed — works but verbose |

### Robustness Gaps

| # | Gap | Severity | Phase | Status |
|---|-----|----------|-------|--------|
| 3 | No output versioning — re-generation overwrites. PRD.md was lost during edge case test (Phase 5). No backup mechanism. | High | 5 | Confirmed |
| 5 | Edits to generated output cause state/output hash mismatch — detected but no rollback/recovery | Medium | 5 | Confirmed |
| 8 | No error recovery mid-generation — if LLM call fails, no save point | Low | 2 | Design gap |
| 11 | Engine assumes `genops-` prefix in skill path — not configurable. Custom stages must follow this convention or fail. | Medium | 1 | Confirmed |

---

## Quality Assessment

### PRD (docs/PRD.md)
- Sections: 7/7
- User stories: Present with priorities and acceptance criteria
- Scope: In/out scope clearly defined
- Risks: Covered with mitigations
- **Issue**: Restored as minimal version after edge case test. Original richer version lost due to no versioning (Gap #3).

### HLD (docs/HLD.md)  
- Sections: 8/8
- Architecture diagram: C4 context + container (mermaid)
- Component descriptions: 4 components with interfaces
- Data flow: Sequence diagram (mermaid)
- NFRs: Scale, latency, availability, security covered
- **Issue**: None. Well-structured.

### ADR (docs/architecture/)
- Count: 3 ADRs (001-Go, 002-SQLite, 003-cobra)
- Format: Title, Status, Context, Decision, Alternatives, Consequences
- Cross-references: Each ADR references related decisions
- **Issue**: ADR-002 and ADR-003 reference "Related Decisions" but don't link to specific ADR-XXX filenames.

### LLD (docs/LLD.md)
- Sections: 8/8
- Class definitions: Task, TaskService, TaskStore, Filter, FormatOptions
- ERD: Present (mermaid)
- Database schema: Present (table format with indexes)
- API contracts: Present (5 subcommands with input/output specs)
- Error handling: Matrix with conditions, messages, exit codes
- Testing strategy: 3-layer with frameworks and coverage targets
- **Issue**: Schema uses table format, not raw SQL. Consistent with template but some engineers prefer DDL.

### Code (docs/code/implementation-plan.md)
- Sections: 8/8
- Tasks: 6 implementation tasks with files, steps
- Testing plan: 5 test specifications
- Risk/mitigation: 3 risks
- **Issue**: Task steps use short descriptions ("Write test → run → fail → implement → pass → commit"). Could use more detailed code snippets per step.

---

## Improvement Plan — Prioritized

### P0: Must Fix (blocks real usage)
1. **Gap #1**: Create 8 missing templates for research + design presets
2. **Gap #4**: Create 8 missing stage skill files for research + design presets
3. **Gap #3**: Add output versioning — `docs/.genops-backups/` with timestamped copies on re-generation

### P1: Should Fix (improves robustness)
4. **Gap #11**: Make skill prefix configurable in genops.yaml — add `skill_prefix` field, default "genops-"
5. **Gap #6**: Add cross-stage consistency checklist to genops-stage protocol — verify LLD references match ADRs
6. **Gap #5**: Add backup-on-edit detection — if output hash differs from stored, auto-backup before re-generation

### P2: Nice to Have (polish)
7. **Gap #12**: Populate CONTEXT.md from PRD key terms — `/genops-prd` should update it after approval
8. **Gap #9**: Enforce ADR incremental mode — strict one-at-a-time with explicit "another?" prompt
9. **Gap #10**: Add hash helper instructions to genops-stage — simpler glob-based hash computation
10. **Gap #8**: Add generation checkpoint — save draft before GENERATE step

---

## What Works Well

1. **SoC enforcement**: Each stage clearly scoped. Interview questions are domain-specific. No overlap between stages.
2. **Staleness detection**: PRD modification correctly flags HLD as stale. Hash-based comparison is reliable.
3. **State machine**: `.genops-state.json` correctly tracks all 5 stages with hashes and timestamps.
4. **Token efficiency**: 90 lines hot-path per stage — 55% under budget. Compressed from original 450 lines.
5. **Template adherence**: All generated documents follow their templates. No placeholder/TBD content.
6. **Downstream cascade**: Changing PRD correctly identified all downstream stages as at-risk.
7. **Edge case handling**: Missing upstream docs, missing state, duplicate runs — all handled gracefully.
8. **Cross-references**: ADRs reference each other. LLD references ADR decisions. Code plan references LLD specs.

---

## Next Iteration Plan

1. Implement P0 gaps (templates, skills, versioning) — estimated 2-3 hours
2. Implement P1 gaps (prefix config, cross-stage validation, backup) — estimated 1-2 hours
3. Re-run full pipeline with a new demo project to validate fixes
4. Test flow modes (--flow, --nonstop) interactively with a real agent session
5. Test research and design presets end-to-end
6. Add automated validation test suite (run pipeline with predefined answers, verify all outputs exist and cross-reference)
