---
name: genops-init
description: Use when initializing GenOps in a project, adding GenOps to an existing project, or updating AGENTS.md after pipeline changes.
---

# GenOps Initializer

One command to make any project GenOps-ready. Discovers, validates, customizes, and connects. Backed by `python .agents/scripts/genops.py`.

## Procedure

### 1. DISCOVER — Find agent entry point

Check in order: `AGENTS.md` → `CLAUDE.md` → `.claude/CLAUDE.md`. First found → use for merge. None found → create `AGENTS.md`.

### 2. DETECT — Scan for GenOps

Look for `<!-- GENOPS:START -->` marker. Results:
- **absent**: Fresh init.
- **outdated**: Marker exists but commands don't match `genops.yaml` stages.
- **connected**: All valid. Report health.

### 3. VALIDATE — Check infrastructure

Run deterministic validation:
```bash
python .agents/scripts/genops.py validate
```

Checks:
- `genops.yaml`: Exists, valid YAML, stages defined, validation_rules
- Skills: `.agents/skills/genops-<id>/SKILL.md` for each stage `id`
- Engine skills: `genops`, `genops-stage`, `genops-status`, `genops-init` present
- Templates: `.agents/templates/<template>` exists with `## Interview` + `## Output` sections
- Context: `.agents/context/CONTEXT.md` present
- State: `docs/.genops-state.json` present (v2.0 schema)

### 4. CUSTOMIZE — Pipeline setup

```
Which pipeline preset?
A) Software spec — prd → hld → adr → lld → code (default)
B) Research — lit-review → hypothesis → experiment → report
C) Design — brief → wireframes → mockups → prototype
D) Custom — define each stage manually
```

If custom → walk through stage-by-stage: name, focus, requires, outputs, template path.
Write selected preset or custom definition to `genops.yaml`.

### 5. SCAFFOLD — Generate missing files

After pipeline is selected, check and create missing components:

**Missing templates:** For each stage with missing template, create one with `## Interview` (sample questions) and `## Output` (sample structure with YAML frontmatter).

**Missing skill files:** For each stage `id` without `.agents/skills/genops-<id>/SKILL.md`, generate a template-driven wrapper:
```markdown
---
name: genops-{id}
description: Use when {focus from genops.yaml}.
---

# {Name}
Generates files into `{outputs}`. Protocol: genops-stage — template-driven. Config: id={id}, requires={requires}, outputs={outputs}, template={template}, next={next}
```

**Missing output directories:** Create empty directories for each stage's outputs.

### 6. GENERATE — Write AGENTS.md block

**Absent**: Create full `AGENTS.md` with GenOps section between `<!-- GENOPS:START/END -->` markers. Include pipeline overview, commands table (auto-generated from genops.yaml stages), flow modes, SoC rules.

**Partial/Merge**: Insert GenOps block between markers. Preserve existing content outside markers.

**Connected**: Read `genops.yaml` → regenerate commands table. Validate all references.

### 7. REPORT — Health summary

```
GenOps Init Report
──────────────────
Entry point    AGENTS.md              ✓ connected
Config         genops.yaml            ✓ {N} stages
Skills         {N}/{N}                ✓ all present
Templates      {N}/{N}                ✓ all have Interview + Output
Presets        3                      ✓ available
State          .genops-state.json     ✓ initialized (v2.0)

Pipeline: genops-{id1} → genops-{id2} → ...

Ready. Run /genops-{first} to start.
```

## Marker Format

```markdown
<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->
... GenOps content ...
<!-- GENOPS:END -->
```

## Presets

Presets in `.agents/presets/`. Each is a complete `genops.yaml`. `--preset` copies to project root.
