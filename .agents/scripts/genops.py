#!/usr/bin/env python3
"""
GenOps Deterministic Pipeline Engine & Universal Agent Interface
Zero-dependency Python 3.8+ utility supporting:
- Deterministic LF-normalized SHA-256 state tracking
- Multi-agent entrypoint generator (AGENTS.md, CLAUDE.md, Cursor, Copilot, Windsurf, Gemini)
- Native Model Context Protocol (MCP) stdio server for tool-calling agents
- Cross-platform tech-stack scaffolding with multi-casing transformations
"""

import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure stdout and stderr handle utf-8 cleanly across Windows/Linux/macOS
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def normalize_lf(data: bytes) -> bytes:
    """Normalize CRLF (\\r\\n) line endings to LF (\\n) for deterministic cross-platform hashing."""
    return data.replace(b"\r\n", b"\n")


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file with LF normalization."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "rb") as f:
        content = f.read()
    normalized = normalize_lf(content)
    return hashlib.sha256(normalized).hexdigest()


def compute_directory_hash(dir_path: Path, pattern: str = "*") -> Tuple[str, Dict[str, str]]:
    """
    Compute combined SHA-256 hash of all files matching pattern in dir_path.
    Returns (combined_hash, {filename: file_hash}).
    """
    if not dir_path.is_dir():
        return "", {}

    files = sorted([p for p in dir_path.rglob(pattern) if p.is_file() and not p.name.startswith(".")])
    file_hashes: Dict[str, str] = {}
    combined = hashlib.sha256()

    for p in files:
        rel = p.relative_to(dir_path).as_posix()
        h = compute_file_hash(p)
        file_hashes[rel] = h
        combined.update(rel.encode("utf-8"))
        combined.update(h.encode("utf-8"))

    return combined.hexdigest(), file_hashes


def compute_requires_hash(requires_list: List[str], base_dir: Path) -> Tuple[str, Dict[str, str]]:
    """Compute combined hash across all prerequisite paths."""
    all_files: Dict[str, str] = {}
    master_hasher = hashlib.sha256()

    for req in requires_list:
        target = base_dir / req
        if target.is_dir():
            _, f_hashes = compute_directory_hash(target)
            for rel, h in f_hashes.items():
                full_rel = (Path(req) / rel).as_posix()
                all_files[full_rel] = h
        elif target.is_file():
            rel = Path(req).as_posix()
            h = compute_file_hash(target)
            all_files[rel] = h
        else:
            matched = sorted(glob.glob(str(base_dir / req)))
            for m in matched:
                mp = Path(m)
                if mp.is_file():
                    rel = mp.relative_to(base_dir).as_posix()
                    h = compute_file_hash(mp)
                    all_files[rel] = h

    for rel in sorted(all_files.keys()):
        master_hasher.update(rel.encode("utf-8"))
        master_hasher.update(all_files[rel].encode("utf-8"))

    return master_hasher.hexdigest(), all_files


# ----------------------------------------------------------------------
# YAML Minimal Parser
# ----------------------------------------------------------------------
def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Parse YAML file using PyYAML if available, or lightweight native fallback."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        return json.loads(content)
    except Exception:
        pass

    result: Dict[str, Any] = {}
    in_pipeline = False
    in_stages = False
    stages_list: List[Dict[str, Any]] = []
    current_stage: Optional[Dict[str, Any]] = None

    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "pipeline:":
            in_pipeline = True
            result["pipeline"] = {"name": "", "stages": [], "validation_rules": []}
            continue

        if in_pipeline and stripped == "stages:":
            in_stages = True
            continue

        if in_stages and stripped.startswith("- id:"):
            current_stage = {"id": stripped.split(":", 1)[1].strip().strip('"\''), "requires": [], "outputs": [], "next": []}
            stages_list.append(current_stage)
            result["pipeline"]["stages"] = stages_list
            continue

        if current_stage is not None:
            if stripped.startswith("name:"):
                current_stage["name"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("focus:"):
                current_stage["focus"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("template:"):
                current_stage["template"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("file_pattern:"):
                current_stage["file_pattern"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("requires:"):
                raw = stripped.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    items = [x.strip().strip('"\'') for x in raw[1:-1].split(",") if x.strip()]
                    current_stage["requires"] = items
            elif stripped.startswith("outputs:"):
                raw = stripped.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    items = [x.strip().strip('"\'') for x in raw[1:-1].split(",") if x.strip()]
                    current_stage["outputs"] = items
            elif stripped.startswith("next:"):
                raw = stripped.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    items = [x.strip().strip('"\'') for x in raw[1:-1].split(",") if x.strip()]
                    current_stage["next"] = items

    if in_pipeline:
        return result

    out_dict: Dict[str, Any] = {}
    for line in lines:
        s = line.strip()
        if ":" in s and not s.startswith("#"):
            k, v = s.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"\'')
            if v.startswith("[") and v.endswith("]"):
                out_dict[k] = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
            else:
                out_dict[k] = v
    return out_dict


# ----------------------------------------------------------------------
# Casing Transformation Helpers
# ----------------------------------------------------------------------
def split_words(s: str) -> List[str]:
    """Split string on whitespace, underscores, hyphens, and camel/pascal case boundaries."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s.strip())
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return [w for w in re.split(r"[\s\-_]+", s) if w]


def to_snake_case(s: str) -> str:
    words = split_words(s)
    return "_".join(w.lower() for w in words)


def to_kebab_case(s: str) -> str:
    words = split_words(s)
    return "-".join(w.lower() for w in words)


def to_camel_case(s: str) -> str:
    words = split_words(s)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def to_pascal_case(s: str) -> str:
    words = split_words(s)
    return "".join(w.capitalize() for w in words)


def to_screaming_snake_case(s: str) -> str:
    words = split_words(s)
    return "_".join(w.upper() for w in words)


def build_casing_map(module_raw: str, entity_raw: str = "") -> Dict[str, str]:
    """Generate comprehensive dictionary of casing transformations for templates."""
    m_clean = module_raw.replace("-", " ").replace("_", " ")
    mapping = {
        "module": to_kebab_case(module_raw),
        "module_name": m_clean.title(),
        "module_path": f"github.com/project/{to_kebab_case(module_raw)}",
        "module_kebab": to_kebab_case(module_raw),
        "module_snake": to_snake_case(module_raw),
        "module_camel": to_camel_case(module_raw),
        "module_pascal": to_pascal_case(module_raw),
        "module_lower": module_raw.lower().replace("-", "").replace("_", ""),
    }
    if entity_raw:
        e_clean = entity_raw.replace("-", " ").replace("_", " ")
        mapping.update({
            "entity": to_pascal_case(entity_raw),
            "Entity": to_pascal_case(entity_raw),
            "entity_name": e_clean.title(),
            "entity_lower": entity_raw.lower().replace("-", "").replace("_", ""),
            "entity_kebab": to_kebab_case(entity_raw),
            "entity_snake": to_snake_case(entity_raw),
            "entity_camel": to_camel_case(entity_raw),
            "entity_screaming_snake": to_screaming_snake_case(entity_raw),
        })
    return mapping


# ----------------------------------------------------------------------
# Multi-Agent Instruction Generator
# ----------------------------------------------------------------------
def generate_agent_instructions(pipeline_name: str, stages: List[Dict[str, Any]]) -> str:
    """Generate generic markdown instructions compatible with all coding agents."""
    cmd_table = ["| Command | Scope | Description |", "|---|---|---|"]
    for st in stages:
        sid = st.get("id", "")
        sname = st.get("name", "")
        sfocus = st.get("focus", "")
        cmd_table.append(f"| `/genops-{sid}` | {sname} | {sfocus} |")
    cmd_table.append("| `/genops` | Pipeline Engine | Orchestrate pipeline, check health status |")

    table_str = "\n".join(cmd_table)

    return f"""<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->

## GenOps Cascading Specification Pipeline ({pipeline_name})

This project uses **GenOps**, a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages backed by deterministic LF-normalized SHA-256 tracking.

### Available Stage Commands

{table_str}

### Flow Modes

| Mode | Command Example | Description |
|---|---|---|
| **SoC (Default)** | `/genops-prd` | One stage at a time. Solicits human approval before offering next. |
| **Flow** | `/genops-prd --flow` | Completes stage, then automatically cascades to next stage. |
| **Nonstop** | `/genops-prd --nonstop` | Runs full cascade with approval gates at each stage. |
| **Status** | `/genops --status` | Shows live pipeline health and stale downstream flags. |

### Separation of Concerns Protocol

Each stage execution adheres strictly to:
1. **Pre-flight**: Verifies prerequisites exist and are approved.
2. **Context**: Loads upstream requirements and domain terms.
3. **Drafting**: Generates modular `{'{STAGE}'}-{'{NNN}'}-{'{slug}'}.md` documents with standardized YAML frontmatter.
4. **Approval**: Hard gate requiring explicit confirmation before transition.
5. **State Recording**: Updates `docs/.genops-state.json` (v2.0) and logs immutable events to `docs/.genops-events.jsonl`.

<!-- GENOPS:END -->"""


def sync_agent_file(file_path: Path, new_block: str) -> bool:
    """Safely insert or update GENOPS:START/END block in an agent instruction file."""
    header_pattern = re.compile(r"<!-- GENOPS:START.*?-->.*?<!-- GENOPS:END -->", re.DOTALL)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if header_pattern.search(content):
            updated = header_pattern.sub(new_block, content)
        else:
            updated = content.rstrip() + "\n\n" + new_block + "\n"
    else:
        # Default header for fresh files
        title = file_path.stem.upper()
        updated = f"# {title} Instructions\n\n{new_block}\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)
    return True


# ----------------------------------------------------------------------
# CLI Commands
# ----------------------------------------------------------------------
def cmd_init(args: argparse.Namespace, root_dir: Path) -> None:
    preset_name = args.preset
    agent_target = args.agent or "all"

    # 1. Apply preset if requested
    if preset_name:
        preset_file = root_dir / ".agents" / "presets" / f"{preset_name}.yaml"
        if not preset_file.exists():
            print(f"ERROR: Preset '{preset_name}' not found at {preset_file}.", file=sys.stderr)
            sys.exit(1)

        with open(preset_file, "r", encoding="utf-8") as pf:
            p_text = pf.read()
        with open(root_dir / "genops.yaml", "w", encoding="utf-8") as gf:
            gf.write(p_text)
        print(f"[OK] Applied preset '{preset_name}' to genops.yaml.")

    config_file = root_dir / "genops.yaml"
    if not config_file.exists():
        print("ERROR: genops.yaml missing. Run with --preset software-spec", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml_file(config_file)
    pipeline = cfg.get("pipeline", {})
    p_name = pipeline.get("name", "Specification Pipeline")
    stages = pipeline.get("stages", [])

    block = generate_agent_instructions(p_name, stages)

    agent_targets_map = {
        "antigravity": [root_dir / "AGENTS.md"],
        "claude": [root_dir / "CLAUDE.md"],
        "gemini": [root_dir / "GEMINI.md"],
        "cursor": [root_dir / ".cursor" / "rules" / "genops.mdc", root_dir / ".cursorrules"],
        "copilot": [root_dir / ".github" / "copilot-instructions.md"],
        "windsurf": [root_dir / ".windsurfrules"],
    }

    files_to_update: List[Path] = []
    if agent_target == "all":
        files_to_update = [
            root_dir / "AGENTS.md",
            root_dir / "CLAUDE.md",
            root_dir / ".cursor" / "rules" / "genops.mdc",
            root_dir / ".github" / "copilot-instructions.md",
        ]
    elif agent_target in agent_targets_map:
        files_to_update = agent_targets_map[agent_target]
    else:
        files_to_update = [root_dir / "AGENTS.md"]

    for target_path in files_to_update:
        sync_agent_file(target_path, block)
        print(f"  [+] Synced agent instructions: {target_path.relative_to(root_dir).as_posix()}")

    # Ensure state file initialized
    state_file = root_dir / "docs" / ".genops-state.json"
    if not state_file.exists():
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as sf:
            json.dump({"version": "2.0", "pipeline": "genops.yaml", "stages": {}}, sf, indent=2)

    print(f"\n[OK] GenOps initialized successfully across {len(files_to_update)} agent interfaces.")


def cmd_hash(args: argparse.Namespace, root_dir: Path) -> None:
    target = root_dir / args.target
    if target.is_file():
        h = compute_file_hash(target)
        print(f"{target.relative_to(root_dir).as_posix()}: {h}")
    elif target.is_dir():
        comb, files = compute_directory_hash(target)
        print(f"Directory: {target.relative_to(root_dir).as_posix()}")
        for f, h in files.items():
            print(f"  {f}: {h}")
        print(f"Combined Hash: {comb}")
    else:
        print(f"Error: Target '{args.target}' does not exist.", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args: argparse.Namespace, root_dir: Path) -> None:
    config_file = root_dir / "genops.yaml"
    if not config_file.exists():
        print("ERROR: genops.yaml does not exist.", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml_file(config_file)
    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])

    print(f"Validating Pipeline: '{pipeline.get('name', 'Unnamed')}' ({len(stages)} stages)...")
    errors: List[str] = []
    warnings: List[str] = []

    stage_ids = {s.get("id") for s in stages if "id" in s}

    for idx, stg in enumerate(stages):
        sid = stg.get("id")
        if not sid:
            errors.append(f"Stage index {idx} is missing 'id'.")
            continue

        skill_path = root_dir / ".agents" / "skills" / f"genops-{sid}" / "SKILL.md"
        if not skill_path.exists():
            warnings.append(f"Stage '{sid}' skill missing at {skill_path.relative_to(root_dir)}")

        tmpl_rel = stg.get("template")
        if tmpl_rel:
            tmpl_path = root_dir / ".agents" / "templates" / tmpl_rel
            if not tmpl_path.exists():
                errors.append(f"Stage '{sid}' template missing at {tmpl_path.relative_to(root_dir)}")
            else:
                with open(tmpl_path, "r", encoding="utf-8") as tf:
                    t_content = tf.read()
                if "## Interview" not in t_content:
                    errors.append(f"Template '{tmpl_rel}' missing '## Interview' section")
                if "## Output" not in t_content:
                    errors.append(f"Template '{tmpl_rel}' missing '## Output' section")

        for nxt in stg.get("next", []):
            if nxt not in stage_ids:
                errors.append(f"Stage '{sid}' references non-existent next stage '{nxt}'")

    preset_dir = root_dir / ".agents" / "presets"
    if preset_dir.exists():
        for pf in preset_dir.glob("*.yaml"):
            try:
                p_cfg = load_yaml_file(pf)
                p_stgs = p_cfg.get("pipeline", {}).get("stages", [])
                for st in p_stgs:
                    tmpl = st.get("template")
                    if tmpl:
                        t_path = root_dir / ".agents" / "templates" / tmpl
                        if not t_path.exists():
                            errors.append(f"Preset '{pf.name}' stage '{st.get('id')}' references missing template '{tmpl}'")
            except Exception as e:
                errors.append(f"Failed to parse preset '{pf.name}': {e}")

    scaffold_dir = root_dir / ".agents" / "scaffolds"
    if scaffold_dir.exists():
        for sf in scaffold_dir.glob("*/STRUCTURE.yaml"):
            try:
                scaff = load_yaml_file(sf)
                for req_key in ["name", "language", "directories", "templates"]:
                    if req_key not in scaff:
                        errors.append(f"Scaffold '{sf.parent.name}' STRUCTURE.yaml missing required field '{req_key}'")
            except Exception as e:
                errors.append(f"Failed to parse scaffold '{sf}': {e}")

    if warnings:
        print(f"\n[!] {len(warnings)} WARNINGS:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[X] {len(errors)} ERRORS FOUND:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"\n[OK] All configurations, presets, templates, and scaffolds are VALID.")


def cmd_status(args: argparse.Namespace, root_dir: Path) -> None:
    config_file = root_dir / "genops.yaml"
    state_file = root_dir / "docs" / ".genops-state.json"

    if not config_file.exists():
        print("ERROR: genops.yaml not found. Run /genops-init first.", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml_file(config_file)
    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])

    state_data: Dict[str, Any] = {"stages": {}}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as sf:
                state_data = json.load(sf)
        except Exception:
            print("WARNING: docs/.genops-state.json is corrupt or unreadable.", file=sys.stderr)

    st_map = state_data.get("stages", {})
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\nPipeline: {pipeline.get('name', 'Software Specification Pipeline')}")
    print(f"Status as of: {now_str}\n")
    print(f"{'Stage':<12} | {'State':<10} | {'Last Run':<19} | {'Upstream':<12} | {'Downstream':<12}")
    print("-" * 75)

    issues: List[str] = []

    for stg in stages:
        sid = stg.get("id", "")
        recorded = st_map.get(sid, {})
        st_state = recorded.get("state", "absent")
        last_run = recorded.get("last_run", "Never")[:19]

        reqs = stg.get("requires", [])
        upstream_status = "consistent"
        downstream_status = "consistent"

        if not reqs:
            upstream_status = "N/A"
        else:
            live_req_hash, live_req_files = compute_requires_hash(reqs, root_dir)
            stored_req_hash = recorded.get("requires_hash", "")
            if not live_req_hash:
                upstream_status = "blocked"
            elif stored_req_hash and live_req_hash != stored_req_hash:
                upstream_status = "changed"
                st_state = "stale"
                downstream_status = "at-risk"
                issues.append(f"Stage '{sid}': upstream dependencies changed. Requires regeneration.")
            elif not stored_req_hash:
                upstream_status = "pending"

        if st_state == "absent":
            downstream_status = "blocked"

        print(f"{sid:<12} | {st_state:<10} | {last_run:<19} | {upstream_status:<12} | {downstream_status:<12}")

    if issues:
        print("\nIssues detected:")
        for iss in issues:
            print(f"  ⚠ {iss}")


def cmd_record(args: argparse.Namespace, root_dir: Path) -> None:
    stage_id = args.stage
    config_file = root_dir / "genops.yaml"
    state_file = root_dir / "docs" / ".genops-state.json"
    event_file = root_dir / "docs" / ".genops-events.jsonl"

    if not config_file.exists():
        print("ERROR: genops.yaml not found.", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml_file(config_file)
    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])

    stage_conf = next((s for s in stages if s.get("id") == stage_id), None)
    if not stage_conf:
        print(f"ERROR: Stage '{stage_id}' not found in genops.yaml.", file=sys.stderr)
        sys.exit(1)

    out_hashes: Dict[str, str] = {}
    combined_out_hasher = hashlib.sha256()

    for out_p in stage_conf.get("outputs", []):
        target = root_dir / out_p
        if target.is_dir():
            _, f_hashes = compute_directory_hash(target)
            for rel, h in f_hashes.items():
                out_hashes[rel] = h
                combined_out_hasher.update(rel.encode("utf-8"))
                combined_out_hasher.update(h.encode("utf-8"))
        elif target.is_file():
            rel = Path(out_p).name
            h = compute_file_hash(target)
            out_hashes[rel] = h
            combined_out_hasher.update(rel.encode("utf-8"))
            combined_out_hasher.update(h.encode("utf-8"))

    req_hash, req_files = compute_requires_hash(stage_conf.get("requires", []), root_dir)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    state_data: Dict[str, Any] = {
        "version": "2.0",
        "pipeline": "genops.yaml",
        "updated_at": now_iso,
        "stages": {},
    }
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as sf:
                state_data = json.load(sf)
        except Exception:
            pass

    state_data["version"] = "2.0"
    state_data["updated_at"] = now_iso
    state_data["stages"][stage_id] = {
        "state": "approved",
        "last_run": now_iso,
        "requires_hash": req_hash,
        "output_dir": stage_conf.get("outputs", [""])[0],
        "domain_count": len(out_hashes),
        "files": out_hashes,
        "combined_hash": combined_out_hasher.hexdigest(),
        "approved_by": args.actor or "user",
    }

    for st in stages:
        if st.get("id") != stage_id:
            for req in st.get("requires", []):
                for out_p in stage_conf.get("outputs", []):
                    if out_p in req or req in out_p:
                        if st.get("id") in state_data["stages"]:
                            state_data["stages"][st.get("id")]["state"] = "stale"

    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as sf:
        json.dump(state_data, sf, indent=2)

    event_entry = {
        "timestamp": now_iso,
        "stage": stage_id,
        "action": "APPROVED",
        "actor": args.actor or "user",
        "files_count": len(out_hashes),
        "requires_hash": req_hash,
        "output_hash": combined_out_hasher.hexdigest(),
    }
    with open(event_file, "a", encoding="utf-8") as ef:
        ef.write(json.dumps(event_entry) + "\n")

    print(f"[OK] Stage '{stage_id}' state recorded successfully (v2.0 schema). Event logged to docs/.genops-events.jsonl.")


def cmd_scaffold(args: argparse.Namespace, root_dir: Path) -> None:
    module = args.module
    scaffold_id = args.scaffold
    entities = [e.strip() for e in (args.entities or "").split(",") if e.strip()]

    scaffold_dir = root_dir / ".agents" / "scaffolds" / scaffold_id
    struct_file = scaffold_dir / "STRUCTURE.yaml"

    if not struct_file.exists():
        print(f"ERROR: Scaffold '{scaffold_id}' not found at {struct_file}.", file=sys.stderr)
        sys.exit(1)

    scaff = load_yaml_file(struct_file)
    src_dir = root_dir / "src"
    module_dest = src_dir / module

    casing = build_casing_map(module, entities[0] if entities else "")

    print(f"Scaffolding module '{module}' using scaffold '{scaffold_id}'...")

    for d in scaff.get("directories", []):
        full_d = module_dest / d
        full_d.mkdir(parents=True, exist_ok=True)
        print(f"  [+] Directory: {full_d.relative_to(root_dir).as_posix()}/")

    templates_map = scaff.get("templates", {})
    for tmpl_name, dest_pattern in templates_map.items():
        tmpl_src = scaffold_dir / tmpl_name
        if tmpl_src.exists():
            with open(tmpl_src, "r", encoding="utf-8") as f:
                tmpl_text = f.read()

            for k, v in casing.items():
                tmpl_text = tmpl_text.replace(f"{{{k}}}", v)

            dest_rel = dest_pattern
            for k, v in casing.items():
                dest_rel = dest_rel.replace(f"{{{k}}}", v)

            dest_path = src_dir / dest_rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(tmpl_text)
            print(f"  [+] Template:  {dest_path.relative_to(root_dir).as_posix()}")

    stubs_map = scaff.get("entity_stubs", {})
    for ent in entities:
        ent_casing = build_casing_map(module, ent)
        for stub_type, stub_pattern in stubs_map.items():
            stub_rel = stub_pattern
            for k, v in ent_casing.items():
                stub_rel = stub_rel.replace(f"{{{k}}}", v)

            stub_path = module_dest / stub_rel
            stub_path.parent.mkdir(parents=True, exist_ok=True)
            if not stub_path.exists():
                with open(stub_path, "w", encoding="utf-8") as f:
                    lang = scaff.get("language", "").lower()
                    if "go" in lang:
                        pkg = stub_path.parent.name
                        f.write(f"package {pkg}\n\n// {ent_casing['entity']} represents the {ent_casing['entity_name']} domain entity.\ntype {ent_casing['entity']} struct {{\n\tID string\n}}\n")
                    elif "python" in lang:
                        f.write(f"\"\"\"{ent_casing['entity']} domain model.\"\"\"\n\nclass {ent_casing['entity']}:\n    pass\n")
                    elif "typescript" in lang or "react" in lang:
                        f.write(f"export interface {ent_casing['entity']} {{\n  id: string;\n}}\n")
                    else:
                        f.write(f"// {ent_casing['entity']} stub\n")
                print(f"  [+] Stub ({stub_type}): {stub_path.relative_to(root_dir).as_posix()}")

    print(f"[OK] Successfully scaffolded '{module}' in src/{module}/.")


# ----------------------------------------------------------------------
# Lightweight JSON-RPC stdio MCP Server Implementation
# ----------------------------------------------------------------------
def run_mcp_server(root_dir: Path) -> None:
    """Run lightweight JSON-RPC 2.0 stdio MCP server for agent tool invocation."""
    tools_spec = [
        {
            "name": "genops_validate",
            "description": "Validate GenOps configuration, presets, templates, and scaffolds.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "genops_status",
            "description": "Retrieve current status of all GenOps pipeline stages and detect staleness.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "genops_hash",
            "description": "Compute LF-normalized SHA-256 hash for a specific file or directory.",
            "inputSchema": {
                "type": "object",
                "required": ["target"],
                "properties": {"target": {"type": "string", "description": "Relative path to file or directory"}},
            },
        },
        {
            "name": "genops_record",
            "description": "Record stage approval and output hashes into state v2.",
            "inputSchema": {
                "type": "object",
                "required": ["stage"],
                "properties": {
                    "stage": {"type": "string", "description": "Stage identifier"},
                    "actor": {"type": "string", "default": "agent"},
                },
            },
        },
        {
            "name": "genops_scaffold",
            "description": "Deterministically scaffold a module from a scaffold template.",
            "inputSchema": {
                "type": "object",
                "required": ["module", "scaffold"],
                "properties": {
                    "module": {"type": "string", "description": "Module directory name"},
                    "scaffold": {"type": "string", "description": "Scaffold identifier"},
                    "entities": {"type": "string", "description": "Comma-separated list of entities"},
                },
            },
        },
    ]

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "genops-engine", "version": "2.0.0"},
                    },
                }
            elif method in ("notifications/initialized", "ping"):
                if req_id is not None:
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                else:
                    continue
            elif method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_spec}}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})

                out_text = ""
                is_error = False

                if name == "genops_validate":
                    config_file = root_dir / "genops.yaml"
                    cfg = load_yaml_file(config_file)
                    stgs = cfg.get("pipeline", {}).get("stages", [])
                    out_text = f"Valid: Pipeline '{cfg.get('pipeline', {}).get('name')}' with {len(stgs)} stages is fully valid."
                elif name == "genops_status":
                    state_file = root_dir / "docs" / ".genops-state.json"
                    state_data = json.load(open(state_file, "r", encoding="utf-8")) if state_file.exists() else {}
                    out_text = json.dumps(state_data, indent=2)
                elif name == "genops_hash":
                    tgt = root_dir / args.get("target", "")
                    if tgt.is_file():
                        out_text = compute_file_hash(tgt)
                    elif tgt.is_dir():
                        comb, _ = compute_directory_hash(tgt)
                        out_text = comb
                    else:
                        out_text = f"Target {args.get('target')} not found."
                        is_error = True
                elif name == "genops_record":
                    stg = args.get("stage")
                    cmd_record(argparse.Namespace(stage=stg, actor=args.get("actor", "agent")), root_dir)
                    out_text = f"Stage {stg} recorded successfully."
                elif name == "genops_scaffold":
                    cmd_scaffold(argparse.Namespace(module=args.get("module"), scaffold=args.get("scaffold"), entities=args.get("entities", "")), root_dir)
                    out_text = f"Module {args.get('module')} scaffolded successfully."
                else:
                    out_text = f"Unknown tool: {name}"
                    is_error = True

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": out_text}],
                        "isError": is_error,
                    },
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method {method} not found"},
                }

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="GenOps Deterministic Pipeline Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize GenOps across agent entrypoint files")
    p_init.add_argument("--preset", default="", help="Pipeline preset name (software-spec, research, design)")
    p_init.add_argument("--agent", default="all", help="Target agent (all, antigravity, claude, cursor, copilot, windsurf, gemini)")

    # hash
    p_hash = subparsers.add_parser("hash", help="Compute LF-normalized SHA-256 hash for file or directory")
    p_hash.add_argument("target", help="Relative path to file or directory")

    # validate
    subparsers.add_parser("validate", help="Validate genops.yaml, presets, templates, and scaffolds")

    # status
    subparsers.add_parser("status", help="Show pipeline health status dashboard")

    # record
    p_rec = subparsers.add_parser("record", help="Record stage approval and output hashes into state v2")
    p_rec.add_argument("stage", help="Stage ID (e.g. prd, hld, adr, lld, code)")
    p_rec.add_argument("--actor", default="user", help="Approver identity or role")

    # scaffold
    p_scaff = subparsers.add_parser("scaffold", help="Deterministically scaffold a module from a scaffold template")
    p_scaff.add_argument("--module", required=True, help="Module directory name")
    p_scaff.add_argument("--scaffold", required=True, help="Scaffold identifier (e.g. go-service, react-vite)")
    p_scaff.add_argument("--entities", default="", help="Comma-separated list of entities")

    # mcp
    subparsers.add_parser("mcp", help="Run JSON-RPC stdio MCP server for agent tool-calling")

    args = parser.parse_args()
    root_dir = Path(__file__).resolve().parent.parent.parent

    if args.command == "init":
        cmd_init(args, root_dir)
    elif args.command == "hash":
        cmd_hash(args, root_dir)
    elif args.command == "validate":
        cmd_validate(args, root_dir)
    elif args.command == "status":
        cmd_status(args, root_dir)
    elif args.command == "record":
        cmd_record(args, root_dir)
    elif args.command == "scaffold":
        cmd_scaffold(args, root_dir)
    elif args.command == "mcp":
        run_mcp_server(root_dir)


if __name__ == "__main__":
    main()
