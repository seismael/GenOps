---
name: genops-code
description: Use when scaffolding project structure, generating stub files, tests, and build configs from LLD design. Terminal stage. Requires completed LLD.
---

# Implementation (Code)

Terminal stage. Reads LLD's `## Project Structure` section and scaffolds actual project files into `src/`. Uses scaffold templates from `.agents/scaffolds/` for deterministic, tech-stack-aware generation.

**Protocol:** genops-stage — reads LLD project structure, not a markdown template.

**Config:** `id: code`, `requires: [docs/lld/]`, `outputs: src/`, `next: []`

## Execution

### 1. PRE-FLIGHT
- `docs/lld/` exists with ≥1 LLD file. LLD is `approved`.
- LLD file contains `## Project Structure` section with `### Modules` table. If missing: "LLD missing Project Structure. Run /genops-lld and define modules with scaffold references."
- Every scaffold referenced in Modules table exists at `.agents/scaffolds/<scaffold>/STRUCTURE.yaml`. If missing: "Scaffold `<name>` not found. Available: `<list>`. Add it or use a different scaffold."

### 2. LOAD
- Read all LLD files. Extract `## Project Structure` → Modules table, Custom Overrides, Cross-Module Config.
- For each module, load its scaffold's `STRUCTURE.yaml`, templates, and entity stubs mapping.
- Load LLD `## Entities & Interfaces` section for entity definitions.

### 3. DOMAINS
Modules from LLD = one scaffold directory each. Single module → single project. Multiple modules → multi-project structure.

### 4. CHECK
Per-file staleness against LLD hashes.

### 5. INTERVIEW — Ask ONE at a time
1. **Output Mode** — "A) Scaffold stubs + build files B) Full implementation"
2. **Overwrite** — "`src/` already has files. Overwrite, merge, or skip existing modules?"
3. **Confirm modules** — "Scaffolding N modules: `<list>`. Which to generate? A) All B) Select"

### 6. GENERATE — Scaffold the project

For each module in LLD's Modules table:

**a. Create directories** from scaffold's `STRUCTURE.yaml` → `directories` list. Prepend `src/{module}/`.

**b. Generate build files** from scaffold's `templates` mapping. For each template file, read the template, fill variables:
- `{module}` → module name
- `{module_path}` → `github.com/project/{module}` (Go) or equivalent
- `{module_name}` → module name, humanized
- `{entity}` → each entity (PascalCase)
- `{entity_lower}` → each entity (lowercase)
Write filled template to the output path.

**c. Generate entity stubs** from scaffold's `entity_stubs` mapping. Per entity listed in LLD module: generate stub file with interface/type definition from LLD Entities section.

**d. Generate default files** from scaffold's `default_files` list (files always generated regardless of entities).

**e. Apply custom overrides** from LLD's Custom Overrides section. Merge or replace scaffold-generated structure.

**f. Generate cross-module config:**
- If >1 module: `src/docker-compose.yml` with all services
- `src/.gitignore` (language-appropriate)
- `src/README.md` (project overview from PRD)

Show progress: "Scaffolding module X/Y: {module} ({scaffold})"

### 7. VALIDATE
- Every LLD entity has at least one stub file generated
- Every module has build files
- Every scaffold template variable was resolved (no unreplaced `{...}`)
- Cross-module Docker config is valid YAML

### 8. PRESENT → APPROVE → RECORD → TRANSITION

Show tree of generated files per module. Terminal stage: "Pipeline complete. Project scaffolded at `src/`."

<HARD-GATE>
Full generation: ALWAYS present for review. NEVER commit without approval. Scaffolded code must build before commit.
</HARD-GATE>
