# Contributing to GenOps

GenOps follows its own pipeline. All contributions should flow through the same specification stages and quality standards that GenOps provides.

## Contribution Workflow

1. **Fork** the repository
2. **Propose** your change as a specification (`/genops-prd`)
3. **Design** the approach if architectural (`/genops-hld`, `/genops-adr`)
4. **Implement** via skill changes, presets, schemas, or engine improvements
5. **Validate** configuration and schemas via `python .agents/scripts/genops.py validate`
6. **Submit** a pull request with the specification documents in the PR description

## What to Contribute

- **New pipeline presets** — Add `.agents/presets/<name>.yaml` with matching templates, schemas, and skills
- **Scaffold templates** — Add new tech stacks in `.agents/scaffolds/<name>/` with valid `STRUCTURE.yaml`
- **Skill improvements** — Enhance protocol steps, interview questions, or validators
- **Templates** — Improve output structures while retaining standardized YAML frontmatter
- **Engine enhancements** — Extend `.agents/scripts/genops.py` (CLI, hashing, AST analysis, anti-drift gates)
- **Documentation & Examples** — Fix errors, add tutorials, expand multi-domain guides

## Development & Skill Guidelines

- **Namespacing:** Skills must use the `genops-` prefix namespace.
- **Protocol:** Follow `genops-stage`: PRE-FLIGHT → LOAD → DOMAINS → CHECK → INTERVIEW → GENERATE → VALIDATE → PRESENT → APPROVE → RECORD → TRANSITION.
- **Token Efficiency:** Keep skill files concise (<100 lines) for hot-path agent performance.
- **Frontmatter:** YAML frontmatter descriptions must start with "Use when...".
- **Hard Gates:** Always include `<HARD-GATE>` blocks for critical verification and approval gates.
- **Machine-Readable Specs:** All generated templates must include standardized YAML frontmatter headers.

## Testing Your Changes

1. **Run Engine Validation:**
   ```bash
   python .agents/scripts/genops.py validate
   ```
2. **Run Pipeline Simulation:**
   - Execute a demo project across all stages (`PRD → HLD → ADR → LLD → Code`).
   - Verify state recording in `docs/.genops-state.json` (v2.0) and event logging in `docs/.genops-events.jsonl`.
3. **Test Staleness & Reactivity:**
   - Modify an upstream document, run `python .agents/scripts/genops.py status`, and verify downstream stages are flagged stale.
4. **Test Scaffolding:**
   - Run `python .agents/scripts/genops.py scaffold` to verify output directory trees, casing transforms, and entity stubs.

## Code of Conduct

- Be respectful, constructive, and assume good intent.
- Follow the GenOps SoC (Separation of Concerns) principle: address one topic per discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
