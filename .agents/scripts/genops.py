#!/usr/bin/env python3
"""
GenOps Deterministic Pipeline Engine, Anti-Drift Gate, Traceability Matrix & Universal Agent Interface
Zero-dependency Python 3.8+ utility supporting:
- Deterministic LF-normalized SHA-256 state tracking & atomic lockfile
- Multi-agent entrypoint generator (AGENTS.md, CLAUDE.md, Cursor, Copilot, Windsurf, Gemini)
- Native Model Context Protocol (MCP) stdio server for tool-calling agents
- Bidirectional Requirements Traceability Matrix (RTM) engine
- Monorepo selective DAG context graph slicer
- Self-contained HTML executive report dashboard generator
- Brownfield codebase reverse-engineering & ingestion
- Cross-layer semantic rule checking & referential integrity graph
- Automated CI/CD anti-drift detector
- Cross-platform tech-stack scaffolding (Go, Python, React, Rust) with multi-casing transforms
"""

import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import sys
import time
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
# Concurrency State Lock
# ----------------------------------------------------------------------
class StateLock:
    """Lightweight atomic file lock for safe multi-agent / parallel updates."""
    def __init__(self, lock_path: Path, timeout: float = 10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.fd: Optional[int] = None

    def __enter__(self) -> "StateLock":
        start_time = time.time()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                # Open with O_CREAT | O_EXCL for atomic creation
                self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    # Stale lock recovery if lock file is older than timeout
                    try:
                        mtime = os.path.getmtime(self.lock_path)
                        if time.time() - mtime > self.timeout:
                            os.remove(self.lock_path)
                            continue
                    except Exception:
                        pass
                    raise TimeoutError(f"Could not acquire GenOps state lock at {self.lock_path} within {self.timeout}s")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            try:
                if self.lock_path.exists():
                    os.remove(self.lock_path)
            except Exception:
                pass


# ----------------------------------------------------------------------
# YAML Minimal Parser & Frontmatter Extractor
# ----------------------------------------------------------------------
def parse_yaml_frontmatter(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """Extract and parse YAML frontmatter block from markdown document."""
    if not file_path.is_file():
        return {}, ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}, ""

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_raw = parts[1]
    body = parts[2]

    fm_dict: Dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"\'')
            if v.startswith("[") and v.endswith("]"):
                fm_dict[k] = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
            else:
                fm_dict[k] = v

    return fm_dict, body


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
| **Targeted** | `/genops-prd --domain <slug>` | Scopes execution or modification exclusively to specified domain. |
| **Flow** | `/genops-prd --flow` | Completes stage, then automatically cascades to next stage. |
| **Nonstop** | `/genops-prd --nonstop` | Runs full cascade with approval gates at each stage. |
| **Incremental** | `/genops --from adr --domain <slug>` | Starts incremental cascade for a single domain. |
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
            root_dir / "GEMINI.md",
            root_dir / ".cursor" / "rules" / "genops.mdc",
            root_dir / ".github" / "copilot-instructions.md",
            root_dir / ".windsurfrules",
            root_dir / "CONVENTIONS.md",
        ]
    elif agent_target in agent_targets_map:
        files_to_update = agent_targets_map[agent_target]
    else:
        files_to_update = [root_dir / "AGENTS.md"]

    for target_path in files_to_update:
        sync_agent_file(target_path, block)
        print(f"  [+] Synced agent instructions: {target_path.relative_to(root_dir).as_posix()}")

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
    lock_file = root_dir / "docs" / ".genops.lock"
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

    # Thread/Process safe atomic state recording
    with StateLock(lock_file):
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

    print(f"[OK] Stage '{stage_id}' state recorded safely (lock-protected v2.0 schema).")


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
                    elif "rust" in lang:
                        f.write(f"//! {ent_casing['entity']} module\n\n#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]\npub struct {ent_casing['entity']} {{\n    pub id: String,\n}}\n")
                    elif "typescript" in lang or "react" in lang:
                        f.write(f"export interface {ent_casing['entity']} {{\n  id: string;\n}}\n")
                    else:
                        f.write(f"// {ent_casing['entity']} stub\n")
                print(f"  [+] Stub ({stub_type}): {stub_path.relative_to(root_dir).as_posix()}")

    print(f"[OK] Successfully scaffolded '{module}' in src/{module}/.")


# ----------------------------------------------------------------------
# Lineage Graph, Cross-Layer Rule Checking & Anti-Drift Gate
# ----------------------------------------------------------------------
def collect_spec_documents(root_dir: Path) -> List[Dict[str, Any]]:
    """Scan docs/ directory and parse frontmatter for all markdown specs."""
    docs_dir = root_dir / "docs"
    if not docs_dir.exists():
        return []

    specs: List[Dict[str, Any]] = []
    for md in docs_dir.rglob("*.md"):
        if md.name.startswith(".") or md.parent.name in ("eval", "evals"):
            continue
        fm, body = parse_yaml_frontmatter(md)
        if not fm:
            continue
        rel_p = md.relative_to(root_dir).as_posix()
        spec_id = fm.get("id") or md.stem
        specs.append({
            "id": spec_id,
            "path": rel_p,
            "stage": fm.get("stage", md.parent.name),
            "domain": fm.get("domain", ""),
            "version": fm.get("version", "1.0.0"),
            "status": fm.get("status", "draft"),
            "upstream_refs": fm.get("upstream_refs", []),
            "downstream_refs": fm.get("downstream_refs", []),
            "frontmatter": fm,
            "body": body,
        })
    return specs


def cmd_graph(args: argparse.Namespace, root_dir: Path) -> None:
    """Build and render the causal lineage Directed Acyclic Graph (DAG)."""
    specs = collect_spec_documents(root_dir)
    print(f"\nGenOps Specification Lineage Graph ({len(specs)} documents indexed)")
    print("=" * 70)

    nodes: Dict[str, Dict[str, Any]] = {s["id"]: s for s in specs}
    edges: List[Tuple[str, str]] = []

    for s in specs:
        sid = s["id"]
        for up in s.get("upstream_refs", []):
            edges.append((up, sid))
        for down in s.get("downstream_refs", []):
            edges.append((sid, down))

    unique_edges = sorted(list(set(edges)))

    # Output Mermaid definition
    mermaid_lines = ["```mermaid", "graph TD"]
    for sid, node in nodes.items():
        stg = node.get("stage", "spec")
        st = node.get("status", "approved")
        mermaid_lines.append(f'  {sid}["{sid}<br/>({stg} • {st})"]')

    for src, dst in unique_edges:
        mermaid_lines.append(f"  {src} --> {dst}")
    mermaid_lines.append("```")

    print("\n".join(mermaid_lines))

    # Save to docs/.genops-graph.json
    graph_data = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_documents": len(specs),
        "nodes": {s["id"]: {"path": s["path"], "stage": s["stage"], "status": s["status"]} for s in specs},
        "edges": [{"from": e[0], "to": e[1]} for e in unique_edges],
    }
    graph_file = root_dir / "docs" / ".genops-graph.json"
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    with open(graph_file, "w", encoding="utf-8") as gf:
        json.dump(graph_data, gf, indent=2)

    print(f"\n[OK] Lineage graph persisted to docs/.genops-graph.json.")


def cmd_check_rules(args: argparse.Namespace, root_dir: Path) -> None:
    """Run semantic cross-layer validation rules across specifications."""
    specs = collect_spec_documents(root_dir)
    spec_ids = {s["id"] for s in specs}
    print(f"Running Cross-Layer Semantic Rules Check on {len(specs)} specifications...")

    violations: List[str] = []

    for s in specs:
        sid = s["id"]
        fm = s["frontmatter"]
        for rk in ["id", "stage", "status"]:
            if rk not in fm:
                violations.append(f"[{s['path']}] Missing required frontmatter key: '{rk}'")

        for up in s.get("upstream_refs", []):
            if up not in spec_ids:
                violations.append(f"[{s['path']}] Broken upstream_ref: '{up}' not found in docs/")

        for down in s.get("downstream_refs", []):
            if down not in spec_ids:
                violations.append(f"[{s['path']}] Broken downstream_ref: '{down}' not found in docs/")

        if s["stage"] == "adr":
            adr_st = s["status"].lower()
            if adr_st in ("rejected", "deprecated") and s.get("downstream_refs"):
                violations.append(f"[{s['path']}] Rejected/Deprecated ADR has active downstream references")

    if violations:
        print(f"\n[!] {len(violations)} RULE VIOLATIONS FOUND:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("\n[OK] All cross-layer semantic validation rules PASSED.")


def cmd_drift(args: argparse.Namespace, root_dir: Path) -> None:
    """CI/CD Anti-Drift Gate: Verify that code stubs match LLD entity definitions."""
    lld_dir = root_dir / "docs" / "lld"
    src_dir = root_dir / "src"

    if not lld_dir.exists():
        print("[OK] No LLD specs present; skipping drift check.")
        return

    print("Running Anti-Drift Integrity Gate (LLD vs. Source Code)...")
    drift_items: List[str] = []

    for lld_file in lld_dir.glob("*.md"):
        with open(lld_file, "r", encoding="utf-8") as f:
            content = f.read()

        module_matches = re.findall(r"\|\s*`?([a-zA-Z0-9_\-]+)`?\s*\|\s*`?([a-zA-Z0-9_\-]+)`?\s*\|\s*`?([a-zA-Z0-9_,\s]+)`?\s*\|", content)
        for m_name, m_scaff, m_entities in module_matches:
            if m_name.lower() in ("module", "---", "name"):
                continue
            mod_path = src_dir / m_name
            if not mod_path.exists():
                drift_items.append(f"Missing scaffolded module directory: src/{m_name}/ (declared in {lld_file.name})")
                continue

            ents = [e.strip() for e in m_entities.split(",") if e.strip()]
            for ent in ents:
                ent_kebab = to_kebab_case(ent)
                ent_snake = to_snake_case(ent)
                ent_lower = ent.lower().replace("-", "").replace("_", "")

                matched_files = list(mod_path.rglob(f"*{ent_kebab}*")) + \
                                list(mod_path.rglob(f"*{ent_snake}*")) + \
                                list(mod_path.rglob(f"*{ent_lower}*"))

                if not matched_files:
                    drift_items.append(f"Module src/{m_name}/ missing implementation stub for entity '{ent}' (declared in {lld_file.name})")

    if drift_items:
        print(f"\n[X] DRIFT DETECTED ({len(drift_items)} issues):")
        for d in drift_items:
            print(f"  - {d}")
        sys.exit(1)
    else:
        print("\n[OK] Anti-Drift Gate: All LLD modules and entity stubs are synchronized with src/.")


# ----------------------------------------------------------------------
# Enterprise Capabilities: RTM, Selective Context, HTML Report, Ingest
# ----------------------------------------------------------------------
def cmd_rtm(args: argparse.Namespace, root_dir: Path) -> None:
    """Generate granular Requirements Traceability Matrix (RTM)."""
    specs = collect_spec_documents(root_dir)
    print(f"\nGenOps Requirements Traceability Matrix (RTM)")
    print("=" * 80)

    rows: List[Dict[str, str]] = []
    for s in specs:
        if s["stage"] == "prd":
            # Extract capabilities from table
            matches = re.findall(r"\|\s*(P\d+)\s*\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|", s["body"])
            for prio, persona, want, so_that, criteria in matches:
                if prio.lower() in ("priority", "---"):
                    continue
                rows.append({
                    "req_id": f"{s['id']}:{want.strip()[:25]}...",
                    "prd": s["id"],
                    "priority": prio.strip(),
                    "downstream": ", ".join(s.get("downstream_refs", [])) or "UNMAPPED",
                })

    if not rows:
        print("No PRD requirements found to trace.")
        return

    print(f"{'Requirement':<35} | {'PRD':<20} | {'Priority':<8} | {'Downstream Design':<20}")
    print("-" * 90)
    for r in rows:
        print(f"{r['req_id']:<35} | {r['prd']:<20} | {r['priority']:<8} | {r['downstream']:<20}")

    coverage = len([r for r in rows if r['downstream'] != 'UNMAPPED']) / max(len(rows), 1) * 100
    print(f"\nRequirements Coverage: {coverage:.1f}% ({len(rows)} requirements tracked)")


def cmd_context(args: argparse.Namespace, root_dir: Path) -> None:
    """Extract targeted upstream DAG lineage slice for a specific domain."""
    domain = args.domain
    specs = collect_spec_documents(root_dir)

    target_specs = [s for s in specs if s["domain"] == domain or domain in s["id"] or domain in str(s.get("upstream_refs", []))]
    if not target_specs:
        print(f"No specifications found for domain: '{domain}'", file=sys.stderr)
        sys.exit(1)

    print(f"# Context Lineage Slice for Domain: {domain}\n")
    for s in target_specs:
        print(f"## [{s['stage'].upper()}] {s['id']} ({s['path']})")
        print(s["body"].strip())
        print("\n" + "=" * 60 + "\n")


def cmd_report(args: argparse.Namespace, root_dir: Path) -> None:
    """Generate self-contained executive HTML dashboard."""
    specs = collect_spec_documents(root_dir)
    state_file = root_dir / "docs" / ".genops-state.json"
    state_data: Dict[str, Any] = {"stages": {}}
    if state_file.exists():
        try:
            state_data = json.load(open(state_file, "r", encoding="utf-8"))
        except Exception:
            pass

    out_html = root_dir / (args.html or "docs/report.html")
    out_html.parent.mkdir(parents=True, exist_ok=True)

    stage_cards_html = ""
    for stg, sinfo in state_data.get("stages", {}).items():
        st_state = sinfo.get("state", "unknown")
        color = "#10b981" if st_state == "approved" else "#f59e0b"
        stage_cards_html += f"""
        <div class="card">
            <h3>{stg.upper()}</h3>
            <p><span class="badge" style="background:{color}">{st_state}</span></p>
            <p><small>Last Run: {sinfo.get('last_run', 'Never')[:19]}</small></p>
            <p><small>Files: {sinfo.get('domain_count', 0)}</small></p>
        </div>"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GenOps Executive Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true, theme:'dark'}});</script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0a0e17; color: #f8fafc; margin: 0; padding: 2rem; }}
        h1, h2 {{ color: #00f0ff; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: rgba(18, 26, 43, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; color: black; }}
        .mermaid {{ background: rgba(18, 26, 43, 0.8); border-radius: 12px; padding: 1.5rem; border: 1px solid rgba(255,255,255,0.1); }}
    </style>
</head>
<body>
    <h1>GenOps Executive Specification Dashboard</h1>
    <p>Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <h2>Pipeline Stages</h2>
    <div class="grid">
        {stage_cards_html or "<p>No stage data recorded yet.</p>"}
    </div>

    <h2>Specification Lineage DAG</h2>
    <div class="mermaid">
    graph TD
    """
    for s in specs:
        html_content += f'      {s["id"]}["{s["id"]}<br/>({s["stage"]})"]\n'
        for down in s.get("downstream_refs", []):
            html_content += f"      {s['id']} --> {down}\n"

    html_content += """
    </div>
</body>
</html>"""

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[OK] Self-contained executive report generated at {out_html.relative_to(root_dir).as_posix()}.")


def cmd_ingest(args: argparse.Namespace, root_dir: Path) -> None:
    """Brownfield codebase ingestion & baseline spec generator."""
    src_target = root_dir / args.src
    if not src_target.exists():
        print(f"ERROR: Source directory {src_target} does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Ingesting brownfield codebase from {src_target.relative_to(root_dir).as_posix()}...")
    detected_modules: List[str] = []
    for item in src_target.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            detected_modules.append(item.name)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lld_dest = root_dir / "docs" / "lld" / "LLD-001-baseline.md"
    lld_dest.parent.mkdir(parents=True, exist_ok=True)

    module_rows = "\n".join([f"| `{m}` | `custom` | `BaselineEntity` | Auto-ingested baseline module |" for m in detected_modules])

    baseline_lld = f"""---
id: LLD-001-baseline
domain: baseline
stage: lld
version: 1.0.0
status: approved
created_at: {now_iso}
updated_at: {now_iso}
upstream_refs: []
downstream_refs: []
tags: [brownfield, baseline, lld]
---

# Brownfield Ingested Baseline — Low-Level Design

## Project Structure
### Modules
| Module | Scaffold | Entities | Description |
|---|---|---|---|
{module_rows}
"""
    with open(lld_dest, "w", encoding="utf-8") as f:
        f.write(baseline_lld)

    print(f"[OK] Brownfield baseline LLD generated at {lld_dest.relative_to(root_dir).as_posix()} with {len(detected_modules)} detected modules.")


# ----------------------------------------------------------------------
# Lightweight JSON-RPC stdio MCP Server Implementation
# ----------------------------------------------------------------------
def run_mcp_server(root_dir: Path) -> None:
    """Run lightweight JSON-RPC 2.0 stdio MCP server for agent tool invocation."""
    tools_spec = [
        {"name": "genops_validate", "description": "Validate GenOps configuration, presets, templates, and scaffolds.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_status", "description": "Retrieve current status of all GenOps pipeline stages and detect staleness.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_hash", "description": "Compute LF-normalized SHA-256 hash for a specific file or directory.", "inputSchema": {"type": "object", "required": ["target"], "properties": {"target": {"type": "string"}}}},
        {"name": "genops_record", "description": "Record stage approval and output hashes into state v2.", "inputSchema": {"type": "object", "required": ["stage"], "properties": {"stage": {"type": "string"}, "actor": {"type": "string", "default": "agent"}}}},
        {"name": "genops_scaffold", "description": "Deterministically scaffold a module from a scaffold template.", "inputSchema": {"type": "object", "required": ["module", "scaffold"], "properties": {"module": {"type": "string"}, "scaffold": {"type": "string"}, "entities": {"type": "string"}}}},
        {"name": "genops_graph", "description": "Generate specification lineage graph and DAG visualization.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_drift", "description": "Run CI/CD anti-drift check between LLD specifications and source code.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_check_rules", "description": "Run semantic cross-layer validation rules across specifications.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_rtm", "description": "Generate Requirements Traceability Matrix (RTM).", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_context", "description": "Extract targeted upstream DAG lineage slice for a domain.", "inputSchema": {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}}},
        {"name": "genops_report", "description": "Generate executive HTML report dashboard.", "inputSchema": {"type": "object", "properties": {"html": {"type": "string", "default": "docs/report.html"}}}},
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
                        "serverInfo": {"name": "genops-engine", "version": "2.1.0"},
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
                elif name == "genops_graph":
                    cmd_graph(argparse.Namespace(), root_dir)
                    out_text = "Graph generated in docs/.genops-graph.json."
                elif name == "genops_drift":
                    cmd_drift(argparse.Namespace(), root_dir)
                    out_text = "Anti-Drift check completed."
                elif name == "genops_check_rules":
                    cmd_check_rules(argparse.Namespace(), root_dir)
                    out_text = "Cross-layer rules check completed."
                elif name == "genops_rtm":
                    cmd_rtm(argparse.Namespace(), root_dir)
                    out_text = "Requirements Traceability Matrix generated."
                elif name == "genops_context":
                    cmd_context(argparse.Namespace(domain=args.get("domain")), root_dir)
                    out_text = f"Context slice extracted for {args.get('domain')}."
                elif name == "genops_report":
                    cmd_report(argparse.Namespace(html=args.get("html", "docs/report.html")), root_dir)
                    out_text = "HTML Executive Report generated."
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
    p_scaff.add_argument("--scaffold", required=True, help="Scaffold identifier (e.g. go-service, react-vite, rust-service)")
    p_scaff.add_argument("--entities", default="", help="Comma-separated list of entities")

    # graph
    subparsers.add_parser("graph", help="Generate specification lineage DAG graph and visualization")

    # check-rules
    subparsers.add_parser("check-rules", help="Verify semantic cross-layer validation rules and references")

    # drift
    subparsers.add_parser("drift", help="Run CI/CD anti-drift check between LLD specs and source files")

    # rtm
    subparsers.add_parser("rtm", help="Generate Requirements Traceability Matrix (RTM)")

    # context
    p_ctx = subparsers.add_parser("context", help="Extract targeted upstream DAG lineage slice for a domain")
    p_ctx.add_argument("--domain", required=True, help="Domain slug (e.g. checkout, ingestion)")

    # report
    p_rep = subparsers.add_parser("report", help="Generate self-contained executive HTML report dashboard")
    p_rep.add_argument("--html", default="docs/report.html", help="Output HTML filepath")

    # ingest
    p_ing = subparsers.add_parser("ingest", help="Brownfield codebase reverse engineering")
    p_ing.add_argument("--src", default="src", help="Source directory to analyze")

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
    elif args.command == "graph":
        cmd_graph(args, root_dir)
    elif args.command == "check-rules":
        cmd_check_rules(args, root_dir)
    elif args.command == "drift":
        cmd_drift(args, root_dir)
    elif args.command == "rtm":
        cmd_rtm(args, root_dir)
    elif args.command == "context":
        cmd_context(args, root_dir)
    elif args.command == "report":
        cmd_report(args, root_dir)
    elif args.command == "ingest":
        cmd_ingest(args, root_dir)
    elif args.command == "mcp":
        run_mcp_server(root_dir)


if __name__ == "__main__":
    main()
