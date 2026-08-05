# Contributing to GenOps

GenOps follows its own pipeline. All contributions should flow through the same specification stages that GenOps provides.

## Contribution Workflow

1. **Fork** the repository
2. **Propose** your change as a mini-PRD (`/genops-prd`)
3. **Design** the approach if architectural (`/genops-hld`, `/genops-adr`)
4. **Implement** via skill changes or new pipeline presets
5. **Test** by running a full pipeline evaluation cycle
6. **Submit** a pull request with the PRD/ADR/LLD docs in the PR description

## What to Contribute

- **New pipeline presets** — Add `.agents/presets/<name>.yaml` with matching templates and skill files
- **Skill improvements** — Enhance the protocol, improve interview questions, add validators
- **Templates** — Improve output structure, add section coverage
- **Documentation** — Fix errors, add examples, improve clarity
- **Bug reports** — Open an issue describing the unexpected behavior and steps to reproduce

## Skill Development Guidelines

- Skills must use the `genops-` prefix namespace to avoid collisions
- Follow the genops-stage protocol: PRE-FLIGHT → LOAD → DOMAINS → CHECK → INTERVIEW → GENERATE → PRESENT → APPROVE → RECORD → TRANSITION
- Keep skill files under 100 lines for hot-path efficiency
- YAML frontmatter descriptions must start with "Use when..." and avoid workflow summaries
- Always include `<HARD-GATE>` blocks for enforcement rules

## Testing Your Changes

1. Reset state: clear `docs/.genops-state.json`
2. Run a full pipeline with a demo project
3. Verify all stages generate, state tracks correctly
4. Test staleness: modify an upstream doc, verify cascade
5. Test edge cases: missing upstream, missing state, duplicate runs
6. Run token audit: hot-path must stay under 200 lines

## Code of Conduct

- Be respectful and constructive
- Focus on the problem, not the person
- Assume good intent
- Follow the GenOps SoC principle in discussions: one topic at a time

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
