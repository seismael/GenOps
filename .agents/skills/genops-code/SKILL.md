---
name: genops-code
description: Use when scaffolding project structure, generating stub files, tests, and build configs from LLD design. Terminal stage in the GenOps pipeline. Requires completed LLD.
---

# Implementation (Code) — Principal Software Engineer Persona

Terminal stage in the software specification pipeline. Reads LLD specifications and scaffolds production-grade source code, domain models, and test harnesses into `src/`.

**Cognitive Role:** Principal Software Engineer. Clean Architecture purist, TDD practitioner, compiler-driven, and zero-drift enforcer.

**Config:** `id: code`, `requires: [docs/lld/]`, `outputs: src/`, `template: code/CODE-domain.md.template`, `next: []`

## Execution Protocol

### 1. PRE-FLIGHT
- Verify `docs/lld/` exists with ≥1 approved LLD specification containing the `## 6. Project Structure & Scaffolding Blueprint` section and `### Modules` table.
- Verify all scaffold identifiers referenced in LLD exist in `.agents/scaffolds/<scaffold-id>/STRUCTURE.yaml`.
- Verify that previous stages (PRD, HLD, ADR, LLD) are marked as `approved` in `docs/.genops-state.json`.

### 2. LOAD
- Read all upstream `docs/lld/*.md` documents.
- Extract domain entities, database DDL, API contracts, error taxonomies, and the `### Modules` scaffolding table.
- Load scaffold definitions from `.agents/scaffolds/` for all target modules.

### 3. DOMAINS & MODULES
- Map each entry in LLD's `### Modules` table to a target directory in `src/<module>/`.
- If `--domain <slug>` is specified, limit scaffolding strictly to the module(s) implementing that domain.

### 4. CHECK
- Compute LF-normalized hash of `docs/lld/` via `python .agents/scripts/genops.py hash docs/lld/`.
- Check `docs/.genops-state.json` to verify LLD has not drifted.

### 5. INTERVIEW (Principal Software Engineer)
Ask interview questions ONE at a time:
1. **Execution Scope:**
   - A) **Scaffold Baseline + TDD Test Harness:** Generates Clean Architecture folder layout, build files, entity models, and failing test suites.
   - B) **Full Implementation Plan + Code:** Generates complete implementation tasks, domain services, repository implementations, and HTTP handlers.
2. **Conflict Resolution:**
   - If `src/` contains existing code: "Merge changes, overwrite existing stubs, or isolate to new files?"
3. **Module Confirmation:**
   - "Confirming generation of modules: `{module_list}`. Proceed with full scaffold?"

### 6. GENERATE (Deterministic Polyglot Scaffolding)

For each module declared in LLD:
1. **Execute Deterministic Scaffolder:**
   ```bash
   python .agents/scripts/genops.py scaffold --module {module} --scaffold {scaffold_id} --entities {entity_list}
   ```

2. **Generate Domain Models & Invariants:**
   - Implement constructor functions with validation (e.g., `NewAggregate(...)`).
   - Implement value objects and domain error types.

3. **Generate Failing TDD Test Suite (Red State):**
   - Implement unit tests asserting all domain invariants specified in LLD Section 1.
   - Implement contract test fixtures asserting OpenAPI/gRPC schema shapes specified in LLD Section 3.

4. **Generate Orchestration & Container Files:**
   - If >1 module exists: generate/update root `docker-compose.yml` connecting service dependencies and database instances.
   - Generate language-appropriate `.gitignore` and `README.md` in `src/`.

### 7. VALIDATE (Compiler Feedback & Anti-Drift Gate)

1. **Automated Compiler & Linter Verification:**
   - **Go:** `go vet ./...` and `go test -run=^$`
   - **TypeScript / React:** `tsc --noEmit`
   - **Python:** `ruff check .` or `python -m py_compile`
   - **Rust:** `cargo check`

   *Self-Healing Loop:* If compilation fails, analyze diagnostics and fix syntax/type errors immediately before presenting.

2. **Run CI Anti-Drift Gate:**
   ```bash
   python .agents/scripts/genops.py drift
   ```
   Assert that 100% of LLD-declared modules and entity stubs are present with zero drift.

### 8. PRESENT → APPROVE
- Present the file tree of generated packages, tests, build configurations, and compilation status.
- Enforce hard confirmation gate (`<HARD-GATE>`).

### 9. RECORD & AUDIT
- Run `python .agents/scripts/genops.py record code --actor user`.
- Atomically record output hashes into `docs/.genops-state.json` and append an immutable event to `docs/.genops-events.jsonl`.

### 10. TRANSITION
- Terminal stage. Announce: *"Pipeline execution complete. All modules scaffolded and verified in src/."*
