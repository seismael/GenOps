#!/usr/bin/env python3
"""
GenOps Deterministic Pipeline Engine, Anti-Drift Gate, Traceability Matrix & Universal Agent Interface
Zero-dependency Python 3.8+ utility supporting:
- Deterministic LF-normalized SHA-256 state tracking & atomic lockfile
- Multi-agent entrypoint generator (AGENTS.md, CLAUDE.md, Cursor, Copilot, Windsurf, Gemini)
- Native Model Context Protocol (MCP) stdio server for tool-calling agents
- Embedded Zero-Dependency JSON Schema Validator (Draft-07 subset)
- Granular Merkle DAG state tracking & Change-Impact Simulator (genops impact)
- Living Memory Compaction Engine (.agents/context/CONTEXT.md)
- Bidirectional Requirements Traceability Matrix (RTM) engine
- Monorepo selective DAG context graph slicer
- Self-contained HTML executive report dashboard generator
- Brownfield codebase reverse-engineering & ingestion
- Cross-layer semantic rule checking & referential integrity graph
- Automated CI/CD anti-drift detector
- Cross-platform tech-stack scaffolding (Go, Python, React, Rust, Node) with multi-casing transforms
- Compiler-in-the-loop verification (genops verify)
"""

from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

__version__ = "3.1.0"

# Ensure stdout and stderr handle utf-8 cleanly across Windows/Linux/macOS
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ==============================================================================
# Domain I: Cryptographic & Deterministic State Engine
# ==============================================================================

class DeterministicHasher:
    """Handles cross-platform cryptographic hashing with mandatory LF normalization."""

    # Directories and artifacts that must never be part of a deterministic hash.
    EXCLUDED_DIR_NAMES = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox",
        "dist", "build", "target", ".next",
    }
    EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

    @classmethod
    def _should_skip(cls, path: Path) -> bool:
        """Skip bytecode/build artifacts and virtual environments for cross-platform determinism."""
        if path.suffix.lower() in cls.EXCLUDED_SUFFIXES:
            return True
        return any(part in cls.EXCLUDED_DIR_NAMES for part in path.parts)

    @staticmethod
    def normalize_lf(data: bytes) -> bytes:
        """Normalize CRLF (\\r\\n) line endings to LF (\\n) for deterministic cross-platform hashing."""
        return data.replace(b"\r\n", b"\n")

    @classmethod
    def hash_file(cls, path: Path) -> str:
        """Compute SHA-256 hash of a file with LF normalization."""
        if not path.is_file():
            raise FileNotFoundError(f"File not found for hashing: {path}")
        with open(path, "rb") as f:
            content = f.read()
        normalized = cls.normalize_lf(content)
        return hashlib.sha256(normalized).hexdigest()

    @classmethod
    def hash_directory(cls, dir_path: Path, pattern: str = "*") -> Tuple[str, Dict[str, str]]:
        """
        Compute combined SHA-256 hash of all matching files in dir_path.
        Returns (combined_hash, {relative_filename: file_hash}).
        """
        if not dir_path.is_dir():
            return "", {}

        files = sorted([p for p in dir_path.rglob(pattern)
                        if p.is_file() and not p.name.startswith(".") and not cls._should_skip(p)])
        file_hashes: Dict[str, str] = {}
        combined = hashlib.sha256()

        for p in files:
            rel = p.relative_to(dir_path).as_posix()
            h = cls.hash_file(p)
            file_hashes[rel] = h
            combined.update(rel.encode("utf-8"))
            combined.update(h.encode("utf-8"))

        return combined.hexdigest(), file_hashes

    @classmethod
    def hash_requirements(cls, requires_list: List[str], base_dir: Path) -> Tuple[str, Dict[str, str]]:
        """Compute combined hash across all prerequisite directories and glob patterns."""
        all_files: Dict[str, str] = {}
        master_hasher = hashlib.sha256()

        for req in requires_list:
            target = base_dir / req
            if target.is_dir():
                _, f_hashes = cls.hash_directory(target)
                for rel, h in f_hashes.items():
                    full_rel = (Path(req) / rel).as_posix()
                    all_files[full_rel] = h
            elif target.is_file():
                rel = Path(req).as_posix()
                all_files[rel] = cls.hash_file(target)
            else:
                matched = sorted(glob.glob(str(base_dir / req)))
                for m in matched:
                    mp = Path(m)
                    if mp.is_file():
                        rel = mp.relative_to(base_dir).as_posix()
                        all_files[rel] = cls.hash_file(mp)

        for rel in sorted(all_files.keys()):
            master_hasher.update(rel.encode("utf-8"))
            master_hasher.update(all_files[rel].encode("utf-8"))

        return master_hasher.hexdigest(), all_files


class MerkleTree:
    """Computes fine-grained Merkle DAG nodes and selective invalidation hashes."""

    @staticmethod
    def compute_root(file_hashes: Dict[str, str]) -> str:
        """Calculate a Merkle root digest from an arbitrary map of {filepath: file_sha256}."""
        if not file_hashes:
            return ""
        hasher = hashlib.sha256()
        for k in sorted(file_hashes.keys()):
            hasher.update(k.encode("utf-8"))
            hasher.update(file_hashes[k].encode("utf-8"))
        return hasher.hexdigest()


class StateLock:
    """Lightweight atomic file lock for safe multi-agent / parallel execution."""

    def __init__(self, lock_path: Path, timeout: float = 10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.fd: Optional[int] = None

    def __enter__(self) -> StateLock:
        start_time = time.time()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    # Stale lock recovery
                    try:
                        mtime = os.path.getmtime(self.lock_path)
                        if time.time() - mtime > self.timeout:
                            os.remove(self.lock_path)
                            continue
                    except OSError:
                        pass
                    raise TimeoutError(f"Could not acquire GenOps state lock at {self.lock_path} within {self.timeout}s")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                if self.lock_path.exists():
                    os.remove(self.lock_path)
            except OSError:
                pass


# ==============================================================================
# Domain II: Zero-Dependency JSON Schema Validator (Draft-07 Subset)
# ==============================================================================

class JsonSchemaValidator:
    """
    Lightweight, zero-dependency JSON Schema Draft-07 validator.
    Supports: type, required, properties, additionalProperties, enum, pattern,
              items, minItems, minimum, maximum.
    """

    @classmethod
    def validate(cls, data: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
        """Recursively validate a data payload against a JSON schema. Returns list of error messages."""
        errors: List[str] = []
        if not isinstance(schema, dict):
            return errors

        # 1. Type Validation
        target_type = schema.get("type")
        if target_type:
            type_errors = cls._validate_type(data, target_type, path)
            if type_errors:
                return type_errors  # Type mismatch halts deeper inspection of this node

        # 2. Enum Validation
        if "enum" in schema and data not in schema["enum"]:
            errors.append(f"{path}: value {json.dumps(data)} is not one of allowed enum {schema['enum']}")

        # 3. Numeric Constraints
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            if "minimum" in schema and data < schema["minimum"]:
                errors.append(f"{path}: value {data} is less than minimum {schema['minimum']}")
            if "maximum" in schema and data > schema["maximum"]:
                errors.append(f"{path}: value {data} is greater than maximum {schema['maximum']}")

        # 4. String Constraints
        if isinstance(data, str):
            if "pattern" in schema:
                pattern = schema["pattern"]
                try:
                    if not re.search(pattern, data):
                        errors.append(f"{path}: string '{data}' does not match required regex pattern '{pattern}'")
                except re.error as e:
                    errors.append(f"{path}: invalid regex pattern '{pattern}' in schema: {e}")

        # 5. Array Constraints
        if isinstance(data, list):
            if "minItems" in schema and len(data) < schema["minItems"]:
                errors.append(f"{path}: array has {len(data)} items, less than minItems {schema['minItems']}")
            items_schema = schema.get("items")
            if items_schema and isinstance(items_schema, dict):
                for idx, item in enumerate(data):
                    errors.extend(cls.validate(item, items_schema, f"{path}[{idx}]"))

        # 6. Object Constraints
        if isinstance(data, dict):
            # Required fields
            for req in schema.get("required", []):
                if req not in data:
                    errors.append(f"{path}: missing required property '{req}'")

            # Properties validation
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    errors.extend(cls.validate(data[prop_name], prop_schema, f"{path}.{prop_name}"))

            # AdditionalProperties validation
            additional_props = schema.get("additionalProperties")
            if additional_props is False:
                allowed_keys = set(properties.keys())
                for key in data.keys():
                    if key not in allowed_keys and not key.startswith("$"):
                        errors.append(f"{path}: unexpected additional property '{key}' (additionalProperties is false)")
            elif isinstance(additional_props, dict):
                for key, val in data.items():
                    if key not in properties and not key.startswith("$"):
                        errors.extend(cls.validate(val, additional_props, f"{path}.{key}"))

        return errors

    @staticmethod
    def _validate_type(data: Any, expected_type: Union[str, List[str]], path: str) -> List[str]:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "null": type(None),
        }
        types_to_check = [expected_type] if isinstance(expected_type, str) else expected_type

        is_valid = False
        for t in types_to_check:
            py_type = type_map.get(t)
            if py_type is None:
                continue
            if t == "integer":
                # bool is a subclass of int in Python, exclude it
                if isinstance(data, int) and not isinstance(data, bool):
                    is_valid = True
                    break
            elif t == "number":
                if isinstance(data, (int, float)) and not isinstance(data, bool):
                    is_valid = True
                    break
            elif isinstance(data, py_type):
                is_valid = True
                break

        if not is_valid:
            actual = "null" if data is None else type(data).__name__
            return [f"{path}: expected type '{expected_type}', got '{actual}'"]
        return []


# ==============================================================================
# Domain III: Document Parsing & AST Tokenization
# ==============================================================================

@dataclass
class SpecDocument:
    """Represents an indexed GenOps specification document."""
    id: str
    path: str
    stage: str
    domain: str
    version: str
    status: str
    upstream_refs: List[str] = field(default_factory=list)
    downstream_refs: List[str] = field(default_factory=list)
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    body: str = ""


class MarkdownTable:
    """AST-resilient Markdown table parser."""

    @staticmethod
    def parse_tables(markdown_text: str) -> List[List[Dict[str, str]]]:
        """Parse all markdown tables in a document into a list of row dictionaries."""
        tables: List[List[Dict[str, str]]] = []
        lines = markdown_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|") and line.endswith("|"):
                header_line = line
                if i + 1 < len(lines):
                    divider_line = lines[i + 1].strip()
                    if divider_line.startswith("|") and "-" in divider_line:
                        headers = [c.strip().strip("`") for c in header_line.split("|")[1:-1]]
                        table_rows: List[Dict[str, str]] = []
                        i += 2
                        while i < len(lines):
                            row_line = lines[i].strip()
                            if not (row_line.startswith("|") and row_line.endswith("|")):
                                break
                            cells = [c.strip() for c in row_line.split("|")[1:-1]]
                            row_dict: Dict[str, str] = {}
                            for col_idx, h in enumerate(headers):
                                val = cells[col_idx] if col_idx < len(cells) else ""
                                row_dict[h] = val
                            table_rows.append(row_dict)
                            i += 1
                        if table_rows:
                            tables.append(table_rows)
                        continue
            i += 1
        return tables


class MarkdownParser:
    """Parses frontmatter and content from GenOps Markdown documents."""

    @staticmethod
    def _parse_frontmatter_value(v: str) -> Any:
        """Parse a single frontmatter scalar or inline [a, b] list."""
        v = v.strip().strip('"\'')
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [x.strip().strip('"\'') for x in inner.split(",") if x.strip()]
        return v

    @staticmethod
    def parse_frontmatter(file_path: Path) -> Tuple[Dict[str, Any], str]:
        """Extract and parse YAML frontmatter block from markdown document.

        Supports simple ``key: value`` pairs, inline ``[a, b]`` lists, and
        indented multi-line lists. Raises ValueError on unsupported constructs
        (block scalars, anchors/aliases/tags, malformed lines) instead of
        silently corrupting the document index.
        """
        if not file_path.is_file():
            return {}, ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return {}, ""

        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        fm_lines = parts[1].splitlines()
        body = parts[2]
        fm_dict: Dict[str, Any] = {}

        i = 0
        while i < len(fm_lines):
            line = fm_lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            if line.startswith("- "):
                raise ValueError(f"{file_path.name}: unexpected list item in frontmatter: '{line}'")
            if ":" not in line:
                raise ValueError(f"{file_path.name}: malformed frontmatter line (no ':'): '{line}'")

            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()

            if v in ("|", ">") or v.startswith(("| ", "> ")):
                raise ValueError(f"{file_path.name}: unsupported YAML block scalar for key '{k}' (multi-line scalars are not supported)")
            if v.startswith(("&", "*", "!")):
                raise ValueError(f"{file_path.name}: unsupported YAML construct for key '{k}' (anchors/aliases/tags are not supported)")

            if v:
                fm_dict[k] = MarkdownParser._parse_frontmatter_value(v)
                i += 1
            else:
                # Empty value — this may be an indented multi-line list.
                items: List[Any] = []
                j = i + 1
                while j < len(fm_lines):
                    sub = fm_lines[j].strip()
                    if not sub:
                        j += 1
                        continue
                    if sub.startswith("- "):
                        items.append(MarkdownParser._parse_frontmatter_value(sub[2:].strip()))
                        j += 1
                        continue
                    break
                if items:
                    fm_dict[k] = items
                    i = j
                else:
                    raise ValueError(f"{file_path.name}: key '{k}' has no value in frontmatter")

        return fm_dict, body

    @classmethod
    def collect_specs(cls, root_dir: Path) -> List[SpecDocument]:
        """Scan docs/ directory and parse frontmatter for all markdown specs."""
        docs_dir = root_dir / "docs"
        if not docs_dir.exists():
            return []

        specs: List[SpecDocument] = []
        for md in docs_dir.rglob("*.md"):
            if md.name.startswith(".") or md.parent.name in ("eval", "evals"):
                continue
            try:
                fm, body = cls.parse_frontmatter(md)
            except ValueError as e:
                print(f"[WARN] Skipping unparseable frontmatter in {md.relative_to(root_dir).as_posix()}: {e}", file=sys.stderr)
                continue
            if not fm:
                continue

            rel_p = md.relative_to(root_dir).as_posix()
            spec_id = fm.get("id") or md.stem
            specs.append(SpecDocument(
                id=spec_id,
                path=rel_p,
                stage=fm.get("stage", md.parent.name),
                domain=fm.get("domain", ""),
                version=fm.get("version", "1.0.0"),
                status=fm.get("status", "draft"),
                upstream_refs=fm.get("upstream_refs", []),
                downstream_refs=fm.get("downstream_refs", []),
                frontmatter=fm,
                body=body,
            ))
        return specs


# ==============================================================================
# Domain IV: Configuration, Living Memory & Change-Impact Simulator
# ==============================================================================

class SimpleYamlParser:
    """Lightweight zero-dependency indentation-based YAML parser supporting mappings, sequences, and scalars."""

    @classmethod
    def parse(cls, text: str) -> Any:
        lines: List[Tuple[int, str]] = []
        for raw_line in text.splitlines():
            line_no_comment = ""
            in_quote: Optional[str] = None
            for char in raw_line:
                if char in ('"', "'"):
                    if in_quote == char:
                        in_quote = None
                    elif in_quote is None:
                        in_quote = char
                elif char == "#" and in_quote is None:
                    break
                line_no_comment += char

            stripped = line_no_comment.rstrip()
            if not stripped:
                continue
            indent = len(stripped) - len(stripped.lstrip(" "))
            lines.append((indent, stripped.strip()))

        if not lines:
            return {}

        res, _ = cls._parse_node(lines, 0, lines[0][0])
        return res if res is not None else {}

    @classmethod
    def _parse_node(cls, lines: List[Tuple[int, str]], idx: int, current_indent: int) -> Tuple[Any, int]:
        if idx >= len(lines):
            return None, idx
        indent, line = lines[idx]
        if line.startswith("- "):
            return cls._parse_seq(lines, idx, indent)
        else:
            return cls._parse_map(lines, idx, indent)

    @classmethod
    def _parse_seq(cls, lines: List[Tuple[int, str]], idx: int, current_indent: int) -> Tuple[List[Any], int]:
        res: List[Any] = []
        while idx < len(lines):
            indent, line = lines[idx]
            if indent < current_indent:
                break
            if indent == current_indent and line.startswith("- "):
                item_str = line[2:].strip()
                if ":" in item_str and not item_str.startswith("{") and not item_str.startswith("["):
                    k, v = item_str.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    item_dict: Dict[str, Any] = {}
                    if v:
                        item_dict[k] = cls._parse_scalar(v)
                        idx += 1
                    else:
                        if idx + 1 < len(lines) and lines[idx + 1][0] > indent:
                            sub_res, idx = cls._parse_node(lines, idx + 1, lines[idx + 1][0])
                            item_dict[k] = sub_res
                        else:
                            item_dict[k] = {}
                            idx += 1

                    while idx < len(lines) and lines[idx][0] > current_indent:
                        s_ind, s_line = lines[idx]
                        if s_line.startswith("- "):
                            break
                        if ":" in s_line:
                            sk, sv = s_line.split(":", 1)
                            sk = sk.strip()
                            sv = sv.strip()
                            if sv:
                                item_dict[sk] = cls._parse_scalar(sv)
                                idx += 1
                            else:
                                if idx + 1 < len(lines) and lines[idx + 1][0] > s_ind:
                                    sub_val, idx = cls._parse_node(lines, idx + 1, lines[idx + 1][0])
                                    item_dict[sk] = sub_val
                                else:
                                    item_dict[sk] = {}
                                    idx += 1
                        else:
                            idx += 1
                    res.append(item_dict)
                else:
                    if item_str:
                        res.append(cls._parse_scalar(item_str))
                        idx += 1
                    else:
                        if idx + 1 < len(lines) and lines[idx + 1][0] > indent:
                            sub_res, idx = cls._parse_node(lines, idx + 1, lines[idx + 1][0])
                            res.append(sub_res)
                        else:
                            res.append(None)
                            idx += 1
            else:
                break
        return res, idx

    @classmethod
    def _parse_map(cls, lines: List[Tuple[int, str]], idx: int, current_indent: int) -> Tuple[Dict[str, Any], int]:
        res: Dict[str, Any] = {}
        while idx < len(lines):
            indent, line = lines[idx]
            if indent < current_indent:
                break
            if indent == current_indent:
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v:
                        res[k] = cls._parse_scalar(v)
                        idx += 1
                    else:
                        if idx + 1 < len(lines) and lines[idx + 1][0] > indent:
                            sub_res, idx = cls._parse_node(lines, idx + 1, lines[idx + 1][0])
                            res[k] = sub_res
                        else:
                            res[k] = {}
                            idx += 1
                else:
                    idx += 1
            else:
                break
        return res, idx

    @classmethod
    def _parse_scalar(cls, val: str) -> Any:
        val = val.strip()
        if not val:
            return ""
        if val in ("|", ">") or val.startswith(("| ", "> ")):
            raise ValueError(f"unsupported YAML block scalar '{val}' (multi-line scalars are not supported by the zero-dependency parser; install PyYAML or simplify the value)")
        if val.startswith(("&", "*", "!")):
            raise ValueError(f"unsupported YAML construct '{val}' (anchors/aliases/tags are not supported by the zero-dependency parser)")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                return []
            return [cls._parse_scalar(x) for x in inner.split(",") if x.strip()]
        if val.startswith("{") and val.endswith("}"):
            try:
                return json.loads(val)
            except Exception:
                pass
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        if val.lower() in ("null", "~"):
            return None
        if re.match(r"^-?\d+$", val):
            return int(val)
        if re.match(r"^-?\d+\.\d+$", val):
            return float(val)
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return val[1:-1]
        return val


class ConfigManager:
    """Manages YAML/JSON configuration files and multi-agent instructions."""

    @staticmethod
    def load_yaml(path: Path) -> Dict[str, Any]:
        """Parse YAML file using native zero-dependency SimpleYamlParser (or PyYAML if installed)."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        try:
            import yaml
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                return parsed
        except ImportError:
            pass

        try:
            parsed = SimpleYamlParser.parse(content)
        except ValueError as e:
            raise ValueError(f"YAML parse error in {path}: {e}") from e
        if isinstance(parsed, dict):
            return parsed
        return {}

    @staticmethod
    def generate_agent_instructions(pipeline_name: str, stages: List[Dict[str, Any]]) -> str:
        """Generate standardized markdown instructions compatible with all coding agents."""
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
3. **Drafting**: Generates modular `{{STAGE}}-{{NNN}}-{{slug}}.md` documents with standardized YAML frontmatter.
4. **Approval**: Hard gate requiring explicit confirmation before transition.
5. **State Recording**: Updates `docs/.genops-state.json` (v2.0) and logs immutable events to `docs/.genops-events.jsonl`.

<!-- GENOPS:END -->"""

    @classmethod
    def sync_agent_file(cls, file_path: Path, new_block: str) -> bool:
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


class ContextCompactor:
    """Extracts structured specifications and compacts living memory into CONTEXT.md."""

    @classmethod
    def compact(cls, root_dir: Path) -> Path:
        """Scan docs/ and synthesize an active, high-density system context card."""
        specs = MarkdownParser.collect_specs(root_dir)
        context_file = root_dir / ".agents" / "context" / "CONTEXT.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)

        # 1. Extract Project Name & Domain Glossary
        project_name = "GenOps Managed System"
        glossary_items: Dict[str, str] = {}
        for s in specs:
            if s.stage == "prd":
                project_name = s.domain.replace("-", " ").title() if s.domain else project_name
                tables = MarkdownTable.parse_tables(s.body)
                for t in tables:
                    for row in t:
                        persona = row.get("Persona") or row.get("As a...")
                        desc = row.get("Role Description") or row.get("Key Motivations")
                        if persona and desc and persona.lower() not in ("persona", "as a..."):
                            glossary_items[persona.strip()] = desc.strip()

        # 2. Extract Technology Preferences from accepted ADRs
        tech_prefs: List[Dict[str, str]] = []
        constraints: List[str] = []
        for s in specs:
            if s.stage == "adr" and s.status.lower() == "accepted":
                tech_prefs.append({
                    "concern": s.domain.title() or "Architecture",
                    "choice": s.id,
                    "reason": f"Formally accepted in {s.path}"
                })
                # Resilient regex for downstream directives section
                match = re.search(r"##\s*(\d+\.\s*)?Downstream Directives.*?\n(.*?)(?=\n##|\Z)", s.body, re.DOTALL | re.IGNORECASE)
                if match:
                    directives_block = match.group(2)
                    for line in directives_block.splitlines():
                        line = line.strip()
                        if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
                            constraints.append(line.lstrip("-*0123456789. "))

        # 3. Extract Core Entities & Modules from LLD
        entities_list: List[str] = []
        for s in specs:
            if s.stage == "lld":
                tables = MarkdownTable.parse_tables(s.body)
                for t in tables:
                    for row in t:
                        ents = row.get("Entities", "")
                        if ents and ents != "-":
                            for e in ents.split(","):
                                if e.strip() and e.strip() not in entities_list:
                                    entities_list.append(e.strip().strip("`"))

        glossary_rows = "\n".join([f"| {k} | {v} |" for k, v in glossary_items.items()]) or "| (Discovered during PRD) | (Definitions) |"
        tech_rows = "\n".join([f"| {tp['concern']} | {tp['choice']} | {tp['reason']} |" for tp in tech_prefs]) or "| (Discovered during ADR) | (Selection) | (Trade-off context) |"
        constraint_bullets = "\n".join([f"- {c}" for c in constraints]) or "- Constraints will be extracted from accepted ADRs."
        entities_str = ", ".join([f"`{e}`" for e in entities_list]) or "None indexed yet"
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        compact_content = f"""# Living Project Context

> Auto-compacted by GenOps Engine on {now_iso}.
> Loaded natively by every GenOps agent skill during Step 1 (LOAD).

## Project Overview
* **System Domain:** {project_name}
* **Indexed Specifications:** {len(specs)} documents across {len(set(s.stage for s in specs))} stages
* **Core Domain Entities:** {entities_str}

## Domain Glossary & Personas
| Term / Persona | Definition / Operational Scope |
|---|---|
{glossary_rows}

## Technology Selections (Accepted ADRs)
| Concern | Selection | Status / Source |
|---|---|---|
{tech_rows}

## Active Architectural Constraints & Invariants
{constraint_bullets}

## Referential Specification Index
| Stage | Document ID | Path | Status |
|---|---|---|---|
""" + "\n".join([f"| `{s.stage.upper()}` | `{s.id}` | `{s.path}` | `{s.status}` |" for s in specs]) + "\n"

        with open(context_file, "w", encoding="utf-8") as cf:
            cf.write(compact_content)
        return context_file


class ImpactSimulator:
    """Simulates change impact across specification lineage DAG, modules, and tests."""

    @classmethod
    def simulate(cls, root_dir: Path, target_query: str) -> Dict[str, Any]:
        """Compute the transitive closure of affected downstream nodes for a given spec ID or path."""
        specs = MarkdownParser.collect_specs(root_dir)
        target_spec = next((s for s in specs if s.id == target_query or s.path == target_query or target_query in s.path), None)

        if not target_spec:
            raise FileNotFoundError(f"Target specification '{target_query}' not found in docs/.")

        # Build adjacency graph from both reference directions for completeness
        downstream_adj: Dict[str, List[str]] = {s.id: [] for s in specs}
        spec_by_id: Dict[str, SpecDocument] = {s.id: s for s in specs}

        for s in specs:
            for up in s.upstream_refs:
                if up in downstream_adj:
                    downstream_adj[up].append(s.id)
            for down in s.downstream_refs:
                if down in downstream_adj:
                    downstream_adj[s.id].append(down)

        # Transitive downstream traversal (index-pointer queue avoids O(n^2) pop(0))
        visited: Set[str] = set()
        queue = [target_spec.id]
        idx = 0
        while idx < len(queue):
            curr = queue[idx]
            idx += 1
            for child in downstream_adj.get(curr, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)

        affected_specs = [spec_by_id[sid] for sid in visited if sid in spec_by_id]

        # Check affected code modules from LLD specs
        affected_modules: List[str] = []
        affected_entities: List[str] = []
        for s in [target_spec] + affected_specs:
            if s.stage == "lld":
                tables = MarkdownTable.parse_tables(s.body)
                for t in tables:
                    for row in t:
                        mod = row.get("Module", "").strip().strip("`")
                        ents = row.get("Entities", "").strip()
                        if mod and mod.lower() not in ("module", "---", "name"):
                            if mod not in affected_modules:
                                affected_modules.append(mod)
                            if ents and ents != "-":
                                for e in ents.split(","):
                                    if e.strip() and e.strip() not in affected_entities:
                                        affected_entities.append(e.strip().strip("`"))

        # Map affected source files in src/
        src_dir = root_dir / "src"
        affected_source_files: List[str] = []
        for mod in affected_modules:
            mod_path = src_dir / mod
            if mod_path.exists():
                for p in mod_path.rglob("*"):
                    if p.is_file() and not p.name.startswith("."):
                        affected_source_files.append(p.relative_to(root_dir).as_posix())

        return {
            "target": {"id": target_spec.id, "path": target_spec.path, "stage": target_spec.stage},
            "downstream_specs_count": len(affected_specs),
            "downstream_specs": [{"id": s.id, "stage": s.stage, "path": s.path} for s in affected_specs],
            "affected_modules": affected_modules,
            "affected_entities": affected_entities,
            "affected_source_files_count": len(affected_source_files),
            "affected_source_files": affected_source_files,
        }


class CompilerVerifier:
    """Executes workspace compiler and linter diagnostics across polyglot stacks."""

    @classmethod
    def verify_workspace(cls, root_dir: Path) -> Dict[str, Any]:
        """Scan src/ and run detected compiler/linter toolchains."""
        src_dir = root_dir / "src"
        results: Dict[str, Any] = {"success": True, "checks": [], "errors": []}

        if not src_dir.exists():
            return results

        # 1. Python syntax + optional Ruff lint
        py_files = list(src_dir.rglob("*.py"))
        if py_files:
            try:
                res = subprocess.run([sys.executable, "-m", "py_compile"] + [str(p) for p in py_files], capture_output=True, text=True)
                if res.returncode != 0:
                    results["success"] = False
                    results["errors"].append(f"Python compilation error: {res.stderr}")
                else:
                    results["checks"].append(f"Python syntax verified ({len(py_files)} files)")
            except OSError:
                pass  # interpreter unavailable (rare); skip syntax check

            # Optional Ruff lint (skipped when ruff is not installed)
            try:
                res = subprocess.run(["ruff", "check"] + [str(p) for p in py_files], capture_output=True, text=True)
                if res.returncode == 0:
                    results["checks"].append(f"Ruff lint passed ({len(py_files)} files)")
                else:
                    results["success"] = False
                    results["errors"].append(f"Ruff lint issues:\n{res.stdout}\n{res.stderr}")
            except OSError:
                pass  # ruff not installed (optional)

        # 2. Go vet + build checks if go.mod exists
        go_mods = list(src_dir.rglob("go.mod"))
        for gm in go_mods:
            try:
                vet = subprocess.run(["go", "vet", "./..."], cwd=gm.parent, capture_output=True, text=True)
                build = subprocess.run(["go", "build", "./..."], cwd=gm.parent, capture_output=True, text=True)
                if vet.returncode == 0 and build.returncode == 0:
                    results["checks"].append(f"Go vet+build passed: {gm.parent.relative_to(root_dir)}")
                else:
                    results["success"] = False
                    detail = (vet.stderr or "") + (build.stderr or "")
                    results["errors"].append(f"Go error in {gm.parent}: {detail}")
            except OSError:
                pass  # Go toolchain not installed on host

        # 3. Rust cargo check
        for ct in list(src_dir.rglob("Cargo.toml")):
            try:
                res = subprocess.run(["cargo", "check"], cwd=ct.parent, capture_output=True, text=True)
                if res.returncode == 0:
                    results["checks"].append(f"Rust cargo check passed: {ct.parent.relative_to(root_dir)}")
                else:
                    results["success"] = False
                    results["errors"].append(f"Rust cargo check error in {ct.parent}: {res.stderr}")
            except OSError:
                pass  # Rust toolchain not installed on host

        # 4. TypeScript/Node check via tsc --noEmit
        for tsconfig in list(src_dir.rglob("tsconfig.json")):
            try:
                res = subprocess.run(["npx", "tsc", "--noEmit", "-p", str(tsconfig)], cwd=tsconfig.parent, capture_output=True, text=True)
                if res.returncode == 0:
                    results["checks"].append(f"TypeScript tsc --noEmit passed: {tsconfig.parent.relative_to(root_dir)}")
                else:
                    results["success"] = False
                    results["errors"].append(f"TypeScript error in {tsconfig.parent}: {res.stderr}")
            except OSError:
                pass  # Node/npx not installed on host

        return results


# ==============================================================================
# Domain V: Scaffolding, Anti-Drift, Traceability, Report & Brownfield Ingest
# ==============================================================================

class ScaffoldingService:
    """Handles deterministic polyglot code scaffolding and casing transforms."""

    @staticmethod
    def split_words(s: str) -> List[str]:
        """Split string on whitespace, underscores, hyphens, and camel/pascal case boundaries."""
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s.strip())
        s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
        return [w for w in re.split(r"[\s\-_]+", s) if w]

    @classmethod
    def build_casing_map(cls, module_raw: str, entity_raw: str = "") -> Dict[str, str]:
        """Generate comprehensive dictionary of casing transformations for templates."""
        m_words = cls.split_words(module_raw)
        m_clean = module_raw.replace("-", " ").replace("_", " ")

        mapping = {
            "module": "-".join(w.lower() for w in m_words),
            "module_name": m_clean.title(),
            "module_path": f"github.com/project/{'-'.join(w.lower() for w in m_words)}",
            "module_kebab": "-".join(w.lower() for w in m_words),
            "module_snake": "_".join(w.lower() for w in m_words),
            "module_camel": (m_words[0].lower() + "".join(w.capitalize() for w in m_words[1:])) if m_words else "",
            "module_pascal": "".join(w.capitalize() for w in m_words),
            "module_lower": module_raw.lower().replace("-", "").replace("_", ""),
        }

        if entity_raw:
            e_words = cls.split_words(entity_raw)
            e_clean = entity_raw.replace("-", " ").replace("_", " ")
            mapping.update({
                "entity": "".join(w.capitalize() for w in e_words),
                "Entity": "".join(w.capitalize() for w in e_words),
                "entity_name": e_clean.title(),
                "entity_lower": entity_raw.lower().replace("-", "").replace("_", ""),
                "entity_kebab": "-".join(w.lower() for w in e_words),
                "entity_snake": "_".join(w.lower() for w in e_words),
                "entity_camel": (e_words[0].lower() + "".join(w.capitalize() for w in e_words[1:])) if e_words else "",
                "entity_screaming_snake": "_".join(w.upper() for w in e_words),
            })
        return mapping

    @staticmethod
    def is_safe_subpath(child: Path, parent: Path) -> bool:
        """Validate that target destination does not escape parent root."""
        try:
            child.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _default_file_content(path: Path) -> str:
        """Return a minimal, syntactically valid body for an unconditional boilerplate file."""
        name = path.name
        if name == "__init__.py":
            return ""
        if name.endswith(".go"):
            return f"package {path.parent.name}\n"
        if name.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
            return "export {}\n"
        if name.endswith(".py"):
            return f'"""{name} boilerplate."""\n'
        if name.endswith(".rs"):
            return ""
        return f"// {name} boilerplate\n"

    @classmethod
    def scaffold_module(cls, root_dir: Path, module: str, scaffold_id: str, entities: List[str]) -> None:
        """Execute deterministic template expansion for a designated module."""
        scaffold_dir = root_dir / ".agents" / "scaffolds" / scaffold_id
        struct_file = scaffold_dir / "STRUCTURE.yaml"

        if not struct_file.exists():
            raise FileNotFoundError(f"Scaffold '{scaffold_id}' not found at {struct_file}")

        scaff = ConfigManager.load_yaml(struct_file)
        src_dir = root_dir / "src"
        module_dest = src_dir / module

        casing = cls.build_casing_map(module, entities[0] if entities else "")
        print(f"Scaffolding module '{module}' using scaffold '{scaffold_id}'...")

        for d in scaff.get("directories", []):
            expanded_d = d
            for k, v in casing.items():
                expanded_d = expanded_d.replace(f"{{{k}}}", v)
            full_d = module_dest / expanded_d
            if not cls.is_safe_subpath(full_d, src_dir):
                raise ValueError(f"Path traversal detected in directory definition: {d}")
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
                if not cls.is_safe_subpath(dest_path, src_dir):
                    raise ValueError(f"Path traversal detected in template output: {dest_rel}")

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(tmpl_text)
                print(f"  [+] Template:  {dest_path.relative_to(root_dir).as_posix()}")

        # default_files: unconditional boilerplate files (e.g. errors.go, __init__.py)
        for df_pattern in scaff.get("default_files", []):
            df_rel = df_pattern
            for k, v in casing.items():
                df_rel = df_rel.replace(f"{{{k}}}", v)

            df_path = src_dir / df_rel
            if not cls.is_safe_subpath(df_path, src_dir):
                raise ValueError(f"Path traversal detected in default file: {df_pattern}")

            df_path.parent.mkdir(parents=True, exist_ok=True)
            if not df_path.exists():
                with open(df_path, "w", encoding="utf-8") as f:
                    f.write(cls._default_file_content(df_path))
                print(f"  [+] Default:   {df_path.relative_to(root_dir).as_posix()}")

        stubs_map = scaff.get("entity_stubs", {})
        for ent in entities:
            ent_casing = cls.build_casing_map(module, ent)
            for stub_type, stub_pattern in stubs_map.items():
                stub_rel = stub_pattern
                for k, v in ent_casing.items():
                    stub_rel = stub_rel.replace(f"{{{k}}}", v)

                stub_path = module_dest / stub_rel
                if not cls.is_safe_subpath(stub_path, src_dir):
                    raise ValueError(f"Path traversal detected in entity stub: {stub_rel}")

                stub_path.parent.mkdir(parents=True, exist_ok=True)
                if not stub_path.exists():
                    lang = scaff.get("language", "").lower()
                    with open(stub_path, "w", encoding="utf-8") as f:
                        if "go" in lang:
                            pkg = stub_path.parent.name
                            f.write(f"package {pkg}\n\n// {ent_casing['entity']} represents the {ent_casing['entity_name']} domain entity.\ntype {ent_casing['entity']} struct {{\n\tID string\n}}\n")
                        elif "python" in lang:
                            f.write(f"\"\"\"{ent_casing['entity']} domain model.\"\"\"\n\nclass {ent_casing['entity']}:\n    pass\n")
                        elif "rust" in lang:
                            f.write(f"//! {ent_casing['entity']} module\n\n#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]\npub struct {ent_casing['entity']} {{\n    pub id: String,\n}}\n")
                        elif "typescript" in lang or "react" in lang or "node" in lang:
                            f.write(f"export interface {ent_casing['entity']} {{\n  id: string;\n}}\n")
                        else:
                            f.write(f"// {ent_casing['entity']} stub\n")
                    print(f"  [+] Stub ({stub_type}): {stub_path.relative_to(root_dir).as_posix()}")


class AntiDriftService:
    """Enforces AST-based verification between LLD designs and source code."""

    @classmethod
    def check_drift(cls, root_dir: Path) -> List[str]:
        """CI/CD Anti-Drift Gate: Verify that code stubs match LLD entity definitions."""
        lld_dir = root_dir / "docs" / "lld"
        src_dir = root_dir / "src"

        if not lld_dir.exists():
            return []

        drift_items: List[str] = []

        for lld_file in lld_dir.glob("*.md"):
            with open(lld_file, "r", encoding="utf-8") as f:
                content = f.read()

            tables = MarkdownTable.parse_tables(content)
            for table in tables:
                for row in table:
                    m_name = row.get("Module", "").strip().strip("`")
                    m_entities = row.get("Entities", "").strip()

                    if not m_name or m_name.lower() in ("module", "---", "name"):
                        continue

                    mod_path = src_dir / m_name
                    if not mod_path.exists():
                        drift_items.append(f"Missing scaffolded module directory: src/{m_name}/ (declared in {lld_file.name})")
                        continue

                    if m_entities and m_entities != "-":
                        ents = [e.strip().strip("`") for e in m_entities.split(",") if e.strip()]
                        for ent in ents:
                            words = ScaffoldingService.split_words(ent)
                            ent_kebab = "-".join(w.lower() for w in words)
                            ent_snake = "_".join(w.lower() for w in words)
                            ent_pascal = "".join(w.capitalize() for w in words)

                            matched = list(mod_path.rglob(f"*{ent_snake}*")) + \
                                      list(mod_path.rglob(f"*{ent_kebab}*")) + \
                                      list(mod_path.rglob(f"*{ent_pascal}*"))

                            if not matched:
                                drift_items.append(f"Module src/{m_name}/ missing implementation stub for entity '{ent}' (declared in {lld_file.name})")
        return drift_items


class TraceabilityService:
    """Generates Bidirectional Requirements Traceability Matrix (RTM)."""

    @classmethod
    def build_rtm(cls, specs: List[SpecDocument]) -> List[Dict[str, str]]:
        """Extract user stories and trace downstream design linkages."""
        rows: List[Dict[str, str]] = []
        for s in specs:
            if s.stage == "prd":
                tables = MarkdownTable.parse_tables(s.body)
                for table in tables:
                    for r in table:
                        prio = r.get("Priority", "").strip()
                        want = r.get("I want to...", "").strip()
                        if not prio or prio.lower() in ("priority", "---"):
                            continue
                        rows.append({
                            "req_id": f"{s.id}:{want[:25]}..." if want else s.id,
                            "prd": s.id,
                            "priority": prio,
                            "downstream": ", ".join(s.downstream_refs) or "UNMAPPED",
                        })
        return rows


class ReportService:
    """Generates self-contained, executive HTML audit dashboard."""

    @classmethod
    def generate_html_report(cls, root_dir: Path, output_file: Path) -> None:
        specs = MarkdownParser.collect_specs(root_dir)
        state_repo = StateRepository(root_dir)
        state_data = state_repo.load_state()
        drifts = AntiDriftService.check_drift(root_dir)
        rtm_rows = TraceabilityService.build_rtm(specs)

        stages_html = ""
        for sid, sinfo in state_data.get("stages", {}).items():
            badge = "badge-green" if sinfo.get("state") == "approved" else "badge-amber"
            stages_html += f"""
            <tr>
                <td><strong>{html.escape(sid.upper())}</strong></td>
                <td><span class="badge {badge}">{html.escape(str(sinfo.get('state')))}</span></td>
                <td>{html.escape(str(sinfo.get('last_run', 'N/A'))[:19])}</td>
                <td><code>{html.escape(str(sinfo.get('combined_hash', 'N/A'))[:12])}...</code></td>
                <td>{sinfo.get('file_count', 0)} files</td>
            </tr>
            """

        specs_html = ""
        for s in specs:
            specs_html += f"""
            <tr>
                <td><code>{html.escape(s.stage.upper())}</code></td>
                <td><strong>{html.escape(s.id)}</strong></td>
                <td>{html.escape(s.path)}</td>
                <td>{html.escape(s.status)}</td>
                <td>{html.escape(', '.join(s.upstream_refs) or '-')}</td>
                <td>{html.escape(', '.join(s.downstream_refs) or '-')}</td>
            </tr>
            """

        drift_html = ""
        if drifts:
            drift_html = "<div class='alert alert-danger'><h3>CI Anti-Drift Violations Detected:</h3><ul>"
            for d in drifts:
                drift_html += f"<li>{html.escape(d)}</li>"
            drift_html += "</ul></div>"
        else:
            drift_html = "<div class='alert alert-success'><strong>✓ Anti-Drift Gate:</strong> 100% of LLD modules and entity stubs are synchronized with <code>src/</code>.</div>"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GenOps Pipeline Executive Audit Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f8fafc; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1, h2, h3 {{ color: #38bdf8; }}
        .card {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #334155; font-size: 14px; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
        .badge-green {{ background: #065f46; color: #34d399; }}
        .badge-amber {{ background: #78350f; color: #fbbf24; }}
        .alert {{ padding: 14px 18px; border-radius: 6px; margin-bottom: 20px; }}
        .alert-success {{ background: #064e3b; border: 1px solid #059669; color: #a7f3d0; }}
        .alert-danger {{ background: #7f1d1d; border: 1px solid #dc2626; color: #fecaca; }}
        code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GenOps Specification Pipeline & Audit Dashboard</h1>
        <p style="color: #94a3b8;">Generated on: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | State Version: 2.0 (LF-Normalized SHA-256)</p>
        
        {drift_html}

        <div class="card">
            <h2>1. Pipeline Stage Governance Health</h2>
            <table>
                <thead>
                    <tr>
                        <th>Stage</th>
                        <th>State</th>
                        <th>Last Execution</th>
                        <th>Output Hash</th>
                        <th>Artifacts</th>
                    </tr>
                </thead>
                <tbody>
                    {stages_html}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>2. Specification Document Registry ({len(specs)} Indexed Documents)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Stage</th>
                        <th>Document ID</th>
                        <th>File Location</th>
                        <th>Status</th>
                        <th>Upstream Dependencies</th>
                        <th>Downstream Dependents</th>
                    </tr>
                </thead>
                <tbody>
                    {specs_html}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)


class BrownfieldIngestionService:
    """Reverse engineers brownfield codebases and produces baseline LLD specifications."""

    @classmethod
    def ingest_codebase(cls, root_dir: Path, src_rel_path: str = "src") -> Tuple[Path, int]:
        src_path = root_dir / src_rel_path
        if not src_path.exists():
            raise FileNotFoundError(f"Source directory '{src_rel_path}' not found.")

        modules: Dict[str, Dict[str, Any]] = {}
        for item in sorted(src_path.iterdir()):
            if item.is_dir() and not item.name.startswith(".") and not DeterministicHasher._should_skip(item):
                m_name = item.name
                files = [p.relative_to(item).as_posix() for p in item.rglob("*")
                         if p.is_file() and not p.name.startswith(".") and not DeterministicHasher._should_skip(p)]
                entities = set()
                for f in files:
                    base = Path(f).stem
                    if base not in ("main", "app", "index", "init", "__init__", "mod", "lib"):
                        entities.add(base.replace("-", " ").replace("_", " ").title().replace(" ", ""))

                modules[m_name] = {
                    "files_count": len(files),
                    "entities": sorted(list(entities)) or [m_name.title()],
                }

        table_rows = []
        for m_name, info in modules.items():
            ents_str = ", ".join(info["entities"])
            table_rows.append(f"| `{m_name}` | Auto-detected module from `{src_rel_path}/{m_name}` | `{ents_str}` |")

        now_str = datetime.datetime.now().strftime("%Y-%m-%d")
        table_content = "\n".join(table_rows) if table_rows else "| `core` | Baseline core module | `CoreEntity` |"

        lld_content = f"""---
id: LLD-001-brownfield-baseline
domain: system-baseline
stage: lld
version: 1.0.0
status: approved
upstream_refs: []
downstream_refs: []
tags: [brownfield, baseline, reverse-engineered]
---

# LLD-001: Brownfield System Architecture Baseline

> Automatically generated by GenOps Brownfield Ingestion Engine on {now_str}.

## 1. System Modules & Entities Map

### Modules
| Module | Description | Entities |
|---|---|---|
{table_content}

## 2. Directory Layout
Baseline reverse-engineered from existing source tree in `{src_rel_path}/`.
"""
        lld_dir = root_dir / "docs" / "lld"
        lld_dir.mkdir(parents=True, exist_ok=True)
        dest_file = lld_dir / "LLD-001-brownfield-baseline.md"

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(lld_content)

        return dest_file, len(modules)


# ==============================================================================
# Domain VI: State Repository & Lineage Graph Engine
# ==============================================================================

class StateRepository:
    """Encapsulates thread-safe persistence of GenOps State v2.0 and Audit Trail."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.state_file = root_dir / "docs" / ".genops-state.json"
        self.lock_file = root_dir / "docs" / ".genops.lock"
        self.event_file = root_dir / "docs" / ".genops-events.jsonl"

    def load_state(self) -> Dict[str, Any]:
        """Read state file safely."""
        if not self.state_file.exists():
            return {"version": "2.0", "pipeline": "genops.yaml", "stages": {}}
        try:
            with open(self.state_file, "r", encoding="utf-8") as sf:
                return json.load(sf)
        except (json.JSONDecodeError, OSError):
            return {"version": "2.0", "pipeline": "genops.yaml", "stages": {}}

    def record_stage(self, stage_id: str, actor: str = "user") -> None:
        """Atomically record stage approval, output hashes, living memory compaction, and event audit."""
        config_file = self.root_dir / "genops.yaml"
        if not config_file.exists():
            raise FileNotFoundError("genops.yaml not found.")

        cfg = ConfigManager.load_yaml(config_file)
        stages = cfg.get("pipeline", {}).get("stages", [])
        stage_conf = next((s for s in stages if s.get("id") == stage_id), None)

        if not stage_conf:
            raise ValueError(f"Stage '{stage_id}' not found in genops.yaml.")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # All cryptographic hashing, Merkle calculations, and state writes occur inside the lock
        with StateLock(self.lock_file):
            out_hashes: Dict[str, str] = {}
            for out_p in stage_conf.get("outputs", []):
                target = self.root_dir / out_p
                if target.is_dir():
                    _, f_hashes = DeterministicHasher.hash_directory(target)
                    for rel, h in f_hashes.items():
                        out_hashes[rel] = h
                elif target.is_file():
                    rel = Path(out_p).name
                    h = DeterministicHasher.hash_file(target)
                    out_hashes[rel] = h

            req_hash, _ = DeterministicHasher.hash_requirements(stage_conf.get("requires", []), self.root_dir)
            combined_root = MerkleTree.compute_root(out_hashes)

            state_data = self.load_state()
            state_data["version"] = "2.0"
            state_data["updated_at"] = now_iso
            state_data.setdefault("stages", {})

            state_data["stages"][stage_id] = {
                "state": "approved",
                "last_run": now_iso,
                "requires_hash": req_hash,
                "output_dir": stage_conf.get("outputs", [""])[0],
                "file_count": len(out_hashes),
                "files": out_hashes,
                "combined_hash": combined_root,
                "approved_by": actor,
            }

            # Boundary-safe Selective Invalidation
            stage_out_paths = [Path(p).as_posix().rstrip("/") for p in stage_conf.get("outputs", [])]
            for st in stages:
                if st.get("id") != stage_id:
                    st_req_paths = [Path(p).as_posix().rstrip("/") for p in st.get("requires", [])]
                    for out_p in stage_out_paths:
                        for req_p in st_req_paths:
                            if out_p == req_p or req_p.startswith(f"{out_p}/") or out_p.startswith(f"{req_p}/"):
                                if st.get("id") in state_data["stages"]:
                                    state_data["stages"][st.get("id")]["state"] = "stale"

            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as sf:
                json.dump(state_data, sf, indent=2)

            event_entry = {
                "timestamp": now_iso,
                "stage": stage_id,
                "action": "APPROVED",
                "actor": actor,
                "files_count": len(out_hashes),
                "requires_hash": req_hash,
                "output_hash": combined_root,
            }
            with open(self.event_file, "a", encoding="utf-8") as ef:
                ef.write(json.dumps(event_entry) + "\n")

            # Compact Living Memory inside lock
            ContextCompactor.compact(self.root_dir)


class LineageGraphService:
    """Constructs, validates, and renders the Directed Acyclic Graph (DAG)."""

    @classmethod
    def generate_graph(cls, specs: List[SpecDocument]) -> Dict[str, Any]:
        """Compute DAG nodes and edges from indexed specs."""
        nodes: Dict[str, Dict[str, Any]] = {s.id: {"path": s.path, "stage": s.stage, "status": s.status} for s in specs}
        edges: List[Tuple[str, str]] = []

        for s in specs:
            for up in s.upstream_refs:
                edges.append((up, s.id))
            for down in s.downstream_refs:
                edges.append((s.id, down))

        unique_edges = sorted(list(set(edges)))
        return {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_documents": len(specs),
            "nodes": nodes,
            "edges": [{"from": e[0], "to": e[1]} for e in unique_edges],
        }

    @classmethod
    def check_rules(cls, specs: List[SpecDocument]) -> List[str]:
        """Verify cross-layer semantic validation rules."""
        spec_ids = {s.id for s in specs}
        violations: List[str] = []

        for s in specs:
            fm = s.frontmatter
            for rk in ["id", "stage", "status"]:
                if rk not in fm:
                    violations.append(f"[{s.path}] Missing required frontmatter key: '{rk}'")

            for up in s.upstream_refs:
                if up not in spec_ids:
                    violations.append(f"[{s.path}] Broken upstream_ref: '{up}' not found in docs/")

            for down in s.downstream_refs:
                if down not in spec_ids:
                    violations.append(f"[{s.path}] Broken downstream_ref: '{down}' not found in docs/")

            if s.stage == "adr":
                adr_st = s.status.lower()
                if adr_st in ("rejected", "deprecated") and s.downstream_refs:
                    violations.append(f"[{s.path}] Rejected/Deprecated ADR has active downstream references")

        return violations


# ==============================================================================
# Domain VII: MCP JSON-RPC 2.0 Stdio Server
# ==============================================================================

class MCPServer:
    """Zero-dependency JSON-RPC 2.0 stdio MCP Server for AI Agent Integration."""

    TOOLS_SPEC = [
        {"name": "genops_validate", "description": "Validate GenOps configuration, presets, templates, and scaffolds against JSON schemas.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_status", "description": "Retrieve current status of all GenOps pipeline stages and detect staleness.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_impact", "description": "Simulate change impact blast radius across downstream specs and code modules.", "inputSchema": {"type": "object", "required": ["spec"], "properties": {"spec": {"type": "string"}}}},
        {"name": "genops_hash", "description": "Compute LF-normalized SHA-256 hash for a specific file or directory.", "inputSchema": {"type": "object", "required": ["target"], "properties": {"target": {"type": "string"}}}},
        {"name": "genops_record", "description": "Record stage approval and output hashes into state v2.", "inputSchema": {"type": "object", "required": ["stage"], "properties": {"stage": {"type": "string"}, "actor": {"type": "string", "default": "agent"}}}},
        {"name": "genops_scaffold", "description": "Deterministically scaffold a module from a scaffold template.", "inputSchema": {"type": "object", "required": ["module", "scaffold"], "properties": {"module": {"type": "string"}, "scaffold": {"type": "string"}, "entities": {"type": "string"}}}},
        {"name": "genops_compact", "description": "Compact active living project memory into CONTEXT.md.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_verify", "description": "Execute compiler and linter diagnostics across workspace.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_graph", "description": "Generate specification lineage graph and DAG visualization.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_drift", "description": "Run CI/CD anti-drift check between LLD specifications and source code.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_check_rules", "description": "Run semantic cross-layer validation rules across specifications.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_rtm", "description": "Generate Requirements Traceability Matrix (RTM).", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "genops_context", "description": "Extract targeted upstream DAG lineage slice for a domain.", "inputSchema": {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}}},
        {"name": "genops_report", "description": "Generate self-contained executive HTML dashboard.", "inputSchema": {"type": "object", "properties": {"html": {"type": "string", "default": "docs/report.html"}}}},
        {"name": "genops_ingest", "description": "Brownfield codebase reverse engineering & baseline spec generator.", "inputSchema": {"type": "object", "properties": {"src": {"type": "string", "default": "src"}}}},
    ]

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.state_repo = StateRepository(root_dir)

    def dispatch(self, name: str, args: Dict[str, Any]) -> Tuple[str, bool]:
        """Dispatch tool calls to domain services."""
        try:
            if name == "genops_validate":
                errors = []
                schema_path = self.root_dir / ".agents" / "schemas" / "genops.schema.json"
                if schema_path.exists():
                    schema = json.load(open(schema_path, "r", encoding="utf-8"))
                    cfg = ConfigManager.load_yaml(self.root_dir / "genops.yaml")
                    errors.extend(JsonSchemaValidator.validate(cfg, schema, "genops.yaml"))
                if errors:
                    return "Validation Errors:\n" + "\n".join(f"- {e}" for e in errors), True
                return "Valid: Pipeline configuration strictly matches JSON Schema.", False

            elif name == "genops_status":
                state = self.state_repo.load_state()
                return json.dumps(state, indent=2), False

            elif name == "genops_impact":
                spec_query = args.get("spec", "")
                result = ImpactSimulator.simulate(self.root_dir, spec_query)
                return json.dumps(result, indent=2), False

            elif name == "genops_hash":
                tgt = self.root_dir / args.get("target", "")
                if tgt.is_file():
                    return DeterministicHasher.hash_file(tgt), False
                elif tgt.is_dir():
                    comb, _ = DeterministicHasher.hash_directory(tgt)
                    return comb, False
                return f"Target '{args.get('target')}' not found.", True

            elif name == "genops_record":
                stg = args.get("stage", "")
                actor = args.get("actor", "agent")
                self.state_repo.record_stage(stg, actor)
                return f"Stage '{stg}' recorded successfully by {actor}.", False

            elif name == "genops_scaffold":
                mod = args.get("module", "")
                scaff = args.get("scaffold", "")
                ents = [e.strip() for e in args.get("entities", "").split(",") if e.strip()]
                ScaffoldingService.scaffold_module(self.root_dir, mod, scaff, ents)
                return f"Module '{mod}' scaffolded successfully.", False

            elif name == "genops_compact":
                p = ContextCompactor.compact(self.root_dir)
                return f"Compacted living memory persisted to {p.relative_to(self.root_dir).as_posix()}", False

            elif name == "genops_verify":
                res = CompilerVerifier.verify_workspace(self.root_dir)
                return json.dumps(res, indent=2), not res["success"]

            elif name == "genops_graph":
                specs = MarkdownParser.collect_specs(self.root_dir)
                graph = LineageGraphService.generate_graph(specs)
                out_path = self.root_dir / "docs" / ".genops-graph.json"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(graph, f, indent=2)
                return "Graph persisted to docs/.genops-graph.json.", False

            elif name == "genops_drift":
                drifts = AntiDriftService.check_drift(self.root_dir)
                if drifts:
                    return "Drift Detected:\n" + "\n".join(f"- {d}" for d in drifts), True
                return "Anti-Drift Gate: All stubs in sync with LLD.", False

            elif name == "genops_check_rules":
                specs = MarkdownParser.collect_specs(self.root_dir)
                violations = LineageGraphService.check_rules(specs)
                if violations:
                    return "Violations:\n" + "\n".join(f"- {v}" for v in violations), True
                return "All cross-layer semantic rules passed.", False

            elif name == "genops_rtm":
                specs = MarkdownParser.collect_specs(self.root_dir)
                rows = TraceabilityService.build_rtm(specs)
                return json.dumps(rows, indent=2), False

            elif name == "genops_context":
                domain = args.get("domain", "")
                specs = MarkdownParser.collect_specs(self.root_dir)
                matched = [s for s in specs if s.domain == domain or domain in s.id or domain in str(s.upstream_refs)]
                if not matched:
                    return f"No specs found for domain: '{domain}'", True
                out = [f"## [{s.stage.upper()}] {s.id} ({s.path})\n{s.body.strip()}" for s in matched]
                return "\n\n---\n\n".join(out), False

            elif name == "genops_report":
                out_html = self.root_dir / args.get("html", "docs/report.html")
                ReportService.generate_html_report(self.root_dir, out_html)
                return f"Report generated at {out_html.relative_to(self.root_dir).as_posix()}.", False

            elif name == "genops_ingest":
                src_dir = args.get("src", "src")
                dest, count = BrownfieldIngestionService.ingest_codebase(self.root_dir, src_dir)
                return f"Brownfield baseline LLD generated at {dest.relative_to(self.root_dir).as_posix()} with {count} detected modules.", False

            return f"Unknown tool: {name}", True
        except Exception as e:
            return f"Error executing tool '{name}': {str(e)}", True

    def run(self) -> None:
        """Main stdio loop."""
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
                            "serverInfo": {"name": "genops-engine", "version": __version__},
                        },
                    }
                elif method in ("notifications/initialized", "ping"):
                    if req_id is not None:
                        resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                    else:
                        continue
                elif method == "tools/list":
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.TOOLS_SPEC}}
                elif method == "tools/call":
                    params = req.get("params", {})
                    name = params.get("name", "")
                    args = params.get("arguments", {})
                    out_text, is_error = self.dispatch(name, args)
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


# ==============================================================================
# Domain VIII: CLI Controller & Dispatcher
# ==============================================================================

def cmd_init(args: argparse.Namespace, root_dir: Path) -> None:
    preset_name = args.preset
    agent_target = args.agent or "all"
    pkg_dir = Path(__file__).resolve().parent.parent

    # If target project doesn't have .agents/, populate it from bundled package
    target_agents_dir = root_dir / ".agents"
    if not target_agents_dir.exists() and pkg_dir.exists() and (pkg_dir / "presets").exists() and root_dir != pkg_dir:
        target_agents_dir.mkdir(parents=True, exist_ok=True)
        for folder in ["presets", "schemas", "scaffolds", "templates", "skills", "scripts"]:
            src_f = pkg_dir / folder
            if src_f.exists() and not (target_agents_dir / folder).exists():
                shutil.copytree(src_f, target_agents_dir / folder)

    if preset_name:
        preset_file = root_dir / ".agents" / "presets" / f"{preset_name}.yaml"
        if not preset_file.exists() and (pkg_dir / "presets" / f"{preset_name}.yaml").exists():
            preset_file = pkg_dir / "presets" / f"{preset_name}.yaml"

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

    cfg = ConfigManager.load_yaml(config_file)
    pipeline = cfg.get("pipeline", {})
    p_name = pipeline.get("name", "Specification Pipeline")
    stages = pipeline.get("stages", [])

    block = ConfigManager.generate_agent_instructions(p_name, stages)

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
        ConfigManager.sync_agent_file(target_path, block)
        print(f"  [+] Synced agent instructions: {target_path.relative_to(root_dir).as_posix()}")

    state_repo = StateRepository(root_dir)
    if not state_repo.state_file.exists():
        state_repo.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_repo.state_file, "w", encoding="utf-8") as sf:
            json.dump({"version": "2.0", "pipeline": "genops.yaml", "stages": {}}, sf, indent=2)

    ContextCompactor.compact(root_dir)
    print(f"\n[OK] GenOps initialized successfully across {len(files_to_update)} agent interfaces.")


_UNSUPPORTED_SCHEMA_KEYWORDS = {
    "$ref", "minLength", "maxLength", "minProperties", "maxProperties",
    "uniqueItems", "oneOf", "anyOf", "allOf", "not", "const",
    "multipleOf", "exclusiveMinimum", "exclusiveMaximum",
    "patternProperties", "dependencies", "format",
}


def _scan_schema_keywords(node: Any, warnings: List[str], where: str) -> None:
    """Recursively detect JSON Schema keywords the built-in validator silently ignores."""
    if isinstance(node, dict):
        for k in node.keys():
            if k in _UNSUPPORTED_SCHEMA_KEYWORDS:
                warnings.append(f"{where}: uses unsupported keyword '{k}' (ignored by the built-in Draft-07 subset validator)")
        for v in node.values():
            _scan_schema_keywords(v, warnings, where)
    elif isinstance(node, list):
        for v in node:
            _scan_schema_keywords(v, warnings, where)


def _collect_validation(root_dir: Path) -> Tuple[List[str], List[str]]:
    """Run all schema/integrity checks, returning (errors, warnings)."""
    config_file = root_dir / "genops.yaml"
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Validate genops.yaml against schema
    cfg_schema_path = root_dir / ".agents" / "schemas" / "genops.schema.json"
    cfg = ConfigManager.load_yaml(config_file)
    if cfg_schema_path.exists():
        schema_data = json.load(open(cfg_schema_path, "r", encoding="utf-8"))
        errors.extend(JsonSchemaValidator.validate(cfg, schema_data, "genops.yaml"))
        _scan_schema_keywords(schema_data, warnings, "genops.schema.json")

    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])
    stage_ids = {s.get("id") for s in stages if "id" in s}

    for stg in stages:
        sid = stg.get("id")
        if not sid:
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

    # 2. Validate scaffold STRUCTURE.yaml files against schema and references
    scaff_schema_path = root_dir / ".agents" / "schemas" / "scaffold.schema.json"
    scaffold_dir = root_dir / ".agents" / "scaffolds"
    known_casing_keys = set(ScaffoldingService.build_casing_map("module-name", "EntityName").keys())
    if scaffold_dir.exists() and scaff_schema_path.exists():
        scaff_schema = json.load(open(scaff_schema_path, "r", encoding="utf-8"))
        _scan_schema_keywords(scaff_schema, warnings, "scaffold.schema.json")
        for sf in scaffold_dir.glob("*/STRUCTURE.yaml"):
            try:
                s_data = ConfigManager.load_yaml(sf)
                scaff_errors = JsonSchemaValidator.validate(s_data, scaff_schema, sf.relative_to(root_dir).as_posix())
                errors.extend(scaff_errors)
            except Exception as e:
                errors.append(f"Failed to parse scaffold '{sf}': {e}")
                continue

            # Verify referenced template files exist
            for tmpl_name in s_data.get("templates", {}):
                if not (sf.parent / tmpl_name).exists():
                    errors.append(f"Scaffold '{sf.parent.name}' references missing template '{tmpl_name}'")

            # Verify all placeholders are known casing keys
            def _check_placeholders(text: str, where: str) -> None:
                for token in re.findall(r"\{(\w+)\}", str(text)):
                    if token not in known_casing_keys:
                        errors.append(f"Scaffold '{sf.parent.name}' uses unknown placeholder '{{{token}}}' in {where}")

            for d in s_data.get("directories", []):
                _check_placeholders(d, "directories")
            for tmpl_name, dest in s_data.get("templates", {}).items():
                _check_placeholders(dest, f"templates.{tmpl_name}")
            for stub_type, stub_pat in s_data.get("entity_stubs", {}).items():
                _check_placeholders(stub_pat, f"entity_stubs.{stub_type}")
            for df in s_data.get("default_files", []):
                _check_placeholders(df, "default_files")

    # 3. Validate pipeline presets against the genops schema
    presets_dir = root_dir / ".agents" / "presets"
    if presets_dir.exists() and cfg_schema_path.exists():
        preset_schema = json.load(open(cfg_schema_path, "r", encoding="utf-8"))
        for preset_file in sorted(presets_dir.glob("*.yaml")):
            try:
                preset_data = ConfigManager.load_yaml(preset_file)
                errors.extend(JsonSchemaValidator.validate(preset_data, preset_schema, preset_file.relative_to(root_dir).as_posix()))
            except Exception as e:
                errors.append(f"Failed to parse preset '{preset_file}': {e}")

    # 4. Validate state file if present
    state_schema_path = root_dir / ".agents" / "schemas" / "state.schema.json"
    state_file = root_dir / "docs" / ".genops-state.json"
    if state_file.exists() and state_schema_path.exists():
        try:
            state_data = json.load(open(state_file, "r", encoding="utf-8"))
            state_schema = json.load(open(state_schema_path, "r", encoding="utf-8"))
            _scan_schema_keywords(state_schema, warnings, "state.schema.json")
            errors.extend(JsonSchemaValidator.validate(state_data, state_schema, "docs/.genops-state.json"))
        except Exception as e:
            errors.append(f"Failed to parse state file: {e}")

    return errors, warnings


def cmd_validate(args: argparse.Namespace, root_dir: Path) -> None:
    config_file = root_dir / "genops.yaml"
    if not config_file.exists():
        print("ERROR: genops.yaml does not exist.", file=sys.stderr)
        sys.exit(1)

    print("Running JSON Schema validation & integrity checks...")
    errors, warnings = _collect_validation(root_dir)

    if warnings:
        print(f"\n[!] {len(warnings)} WARNINGS:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[X] {len(errors)} SCHEMA / PIPELINE ERRORS FOUND:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[OK] Zero-Dependency Schema Validation PASSED: All configs, templates, and scaffolds are VALID.")


def cmd_doctor(args: argparse.Namespace, root_dir: Path) -> None:
    """Run every governance gate in one shot and report a consolidated health check."""
    config_file = root_dir / "genops.yaml"
    if not config_file.exists():
        print("ERROR: genops.yaml not found. Run `genops init` first.", file=sys.stderr)
        sys.exit(1)

    print("GenOps Doctor — comprehensive repository health check\n")
    checks: List[Tuple[str, List[str], List[str]]] = []

    v_errors, v_warnings = _collect_validation(root_dir)
    checks.append(("validate (schemas, templates, scaffolds, presets)", v_errors, v_warnings))

    specs = MarkdownParser.collect_specs(root_dir)
    checks.append(("check-rules (cross-layer semantic integrity)", LineageGraphService.check_rules(specs), []))

    checks.append(("drift (LLD <-> source sync)", AntiDriftService.check_drift(root_dir), []))

    ver = CompilerVerifier.verify_workspace(root_dir)
    ver_errors = [] if ver.get("success") else ver.get("errors", [])
    checks.append(("verify (compiler/linter diagnostics)", ver_errors, []))

    total = 0
    for name, errs, warns in checks:
        if errs:
            print(f"[FAIL] {name} ({len(errs)} issue(s))")
            for e in errs:
                print(f"        - {e}")
            total += len(errs)
        else:
            print(f"[PASS] {name}")
        for w in warns:
            print(f"        ! {w}")

    print()
    if total:
        print(f"[X] Doctor found {total} issue(s). Fix them before relying on the pipeline.")
        sys.exit(1)
    print("[OK] All governance gates passed — GenOps is healthy.")


def cmd_demo(args: argparse.Namespace, root_dir: Path) -> None:
    """Scaffold a throwaway module and verify it, proving the pipeline end-to-end."""
    scaffold_id = args.scaffold or "go-service"
    module = args.module or "demo-svc"
    entities = [e.strip() for e in (args.entities or "Ping").split(",") if e.strip()]

    scaffold_src = root_dir / ".agents" / "scaffolds" / scaffold_id
    if not scaffold_src.exists():
        print(f"ERROR: scaffold '{scaffold_id}' not found at {scaffold_src}.", file=sys.stderr)
        sys.exit(1)

    demo_root = root_dir / ".genops-demo"
    shutil.rmtree(demo_root, ignore_errors=True)
    (demo_root / ".agents" / "scaffolds").mkdir(parents=True)
    shutil.copytree(scaffold_src, demo_root / ".agents" / "scaffolds" / scaffold_id)

    print(f"GenOps demo — scaffolding '{module}' ({scaffold_id}) and verifying...\n")
    ScaffoldingService.scaffold_module(demo_root, module, scaffold_id, entities)

    files = [p for p in (demo_root / "src").rglob("*") if p.is_file() and not p.name.startswith(".")]
    print(f"\nGenerated {len(files)} files under .genops-demo/src/{module}/.")

    result = CompilerVerifier.verify_workspace(demo_root)
    for c in result.get("checks", []):
        print(f"  [+] {c}")
    for e in result.get("errors", []):
        print(f"  [-] {e}")

    shutil.rmtree(demo_root, ignore_errors=True)
    print("\n[OK] Demo complete — throwaway workspace removed.")
    if not result.get("success", False):
        sys.exit(1)


def cmd_impact(args: argparse.Namespace, root_dir: Path) -> None:
    """CLI Change-Impact Simulator."""
    try:
        res = ImpactSimulator.simulate(root_dir, args.spec)
        print(f"\nChange Impact Blast Radius for: {res['target']['id']} ({res['target']['path']})")
        print("=" * 80)
        print(f"├── Affected Downstream Specs ({res['downstream_specs_count']}):")
        for s in res["downstream_specs"]:
            print(f"│   ├── [{s['stage'].upper()}] {s['id']} ({s['path']})")
        print(f"├── Affected Code Modules ({len(res['affected_modules'])}):")
        for m in res["affected_modules"]:
            print(f"│   ├── src/{m}/")
        print(f"├── Affected Domain Entities: {', '.join(res['affected_entities']) or 'None'}")
        print(f"└── Source Files Requiring Review ({res['affected_source_files_count']}):")
        for sf in res["affected_source_files"][:10]:
            print(f"    ├── {sf}")
        if res["affected_source_files_count"] > 10:
            print(f"    └── ... ({res['affected_source_files_count'] - 10} more files)")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args: argparse.Namespace, root_dir: Path) -> None:
    config_file = root_dir / "genops.yaml"
    if not config_file.exists():
        print("ERROR: genops.yaml not found. Run /genops-init first.", file=sys.stderr)
        sys.exit(1)

    cfg = ConfigManager.load_yaml(config_file)
    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])

    state_repo = StateRepository(root_dir)
    state_data = state_repo.load_state()
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
            live_req_hash, _ = DeterministicHasher.hash_requirements(reqs, root_dir)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="GenOps Deterministic Pipeline Engine")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize GenOps across agent entrypoint files")
    p_init.add_argument("--preset", default="", help="Pipeline preset name (software-spec, research, design)")
    p_init.add_argument("--agent", default="all", help="Target agent")

    # hash
    p_hash = subparsers.add_parser("hash", help="Compute LF-normalized SHA-256 hash for file or directory")
    p_hash.add_argument("target", help="Path to file or directory")

    # validate
    subparsers.add_parser("validate", help="Validate genops.yaml, presets, templates, and scaffolds")

    # doctor
    subparsers.add_parser("doctor", help="Run all governance gates (validate, check-rules, drift, verify) at once")

    # impact
    p_imp = subparsers.add_parser("impact", help="Simulate change impact blast radius across downstream specs and code")
    p_imp.add_argument("spec", help="Target specification ID or file path")

    # status
    subparsers.add_parser("status", help="Show pipeline health status dashboard")

    # record
    p_rec = subparsers.add_parser("record", help="Record stage approval into state v2")
    p_rec.add_argument("stage", help="Stage ID")
    p_rec.add_argument("--actor", default="user", help="Approver identity")

    # scaffold
    p_scaff = subparsers.add_parser("scaffold", help="Deterministically scaffold a module from a scaffold template")
    p_scaff.add_argument("--module", required=True, help="Module directory name")
    p_scaff.add_argument("--scaffold", required=True, help="Scaffold identifier")
    p_scaff.add_argument("--entities", default="", help="Comma-separated entities")

    # graph
    subparsers.add_parser("graph", help="Generate specification lineage DAG")

    # check-rules
    subparsers.add_parser("check-rules", help="Verify semantic cross-layer validation rules")

    # drift
    subparsers.add_parser("drift", help="Run CI/CD anti-drift check between LLD and code")

    # rtm
    subparsers.add_parser("rtm", help="Generate Requirements Traceability Matrix")

    # context
    p_ctx = subparsers.add_parser("context", help="Extract upstream DAG lineage slice for a domain")
    p_ctx.add_argument("--domain", required=True, help="Domain slug")

    # compact
    subparsers.add_parser("compact", help="Compact living project memory into CONTEXT.md")

    # verify
    subparsers.add_parser("verify", help="Run compiler verification across source modules")

    # report
    p_rep = subparsers.add_parser("report", help="Generate self-contained executive HTML dashboard")
    p_rep.add_argument("--html", default="docs/report.html", help="Output HTML filepath")

    # ingest
    p_ing = subparsers.add_parser("ingest", help="Brownfield codebase reverse engineering")
    p_ing.add_argument("--src", default="src", help="Source directory to analyze")

    # mcp
    subparsers.add_parser("mcp", help="Run JSON-RPC stdio MCP server for agent tool-calling")

    # demo
    p_demo = subparsers.add_parser("demo", help="Scaffold a throwaway module and verify it (proves the pipeline end-to-end)")
    p_demo.add_argument("--scaffold", default="go-service", help="Scaffold id (default: go-service)")
    p_demo.add_argument("--module", default="demo-svc", help="Module name (default: demo-svc)")
    p_demo.add_argument("--entities", default="Ping", help="Comma-separated entities")

    args = parser.parse_args()
    
    # Dynamic project root discovery: search from CWD upward for genops.yaml or .git
    curr_dir = Path.cwd().resolve()
    root_dir = curr_dir
    found = False
    for candidate in [curr_dir] + list(curr_dir.parents):
        if (candidate / "genops.yaml").exists() or (candidate / ".git").exists():
            root_dir = candidate
            found = True
            break

    if not found and args.command != "init":
        print("ERROR: no genops.yaml or .git found in this directory tree.", file=sys.stderr)
        print("Run from a GenOps project, or bootstrap one with: genops init --preset software-spec", file=sys.stderr)
        sys.exit(1)

    if args.command == "init":
        cmd_init(args, root_dir)
    elif args.command == "hash":
        target = root_dir / args.target
        if target.is_file():
            print(f"{target.relative_to(root_dir).as_posix()}: {DeterministicHasher.hash_file(target)}")
        elif target.is_dir():
            comb, files = DeterministicHasher.hash_directory(target)
            print(f"Directory: {target.relative_to(root_dir).as_posix()}")
            for f, h in files.items():
                print(f"  {f}: {h}")
            print(f"Combined Hash: {comb}")
        else:
            print(f"Error: Target '{args.target}' does not exist.", file=sys.stderr)
            sys.exit(1)
    elif args.command == "validate":
        cmd_validate(args, root_dir)
    elif args.command == "doctor":
        cmd_doctor(args, root_dir)
    elif args.command == "demo":
        cmd_demo(args, root_dir)
    elif args.command == "impact":
        cmd_impact(args, root_dir)
    elif args.command == "status":
        cmd_status(args, root_dir)
    elif args.command == "record":
        repo = StateRepository(root_dir)
        repo.record_stage(args.stage, args.actor)
        print(f"[OK] Stage '{args.stage}' state recorded safely (lock-protected v2.0 schema).")
    elif args.command == "scaffold":
        ents = [e.strip() for e in (args.entities or "").split(",") if e.strip()]
        ScaffoldingService.scaffold_module(root_dir, args.module, args.scaffold, ents)
        print(f"[OK] Successfully scaffolded '{args.module}' in src/{args.module}/.")
    elif args.command == "graph":
        specs = MarkdownParser.collect_specs(root_dir)
        graph = LineageGraphService.generate_graph(specs)
        graph_file = root_dir / "docs" / ".genops-graph.json"
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        with open(graph_file, "w", encoding="utf-8") as gf:
            json.dump(graph, gf, indent=2)
        print(f"[OK] Lineage graph persisted to docs/.genops-graph.json.")
    elif args.command == "check-rules":
        specs = MarkdownParser.collect_specs(root_dir)
        violations = LineageGraphService.check_rules(specs)
        if violations:
            print(f"\n[!] {len(violations)} RULE VIOLATIONS FOUND:")
            for v in violations:
                print(f"  - {v}")
            sys.exit(1)
        else:
            print("\n[OK] All cross-layer semantic validation rules PASSED.")
    elif args.command == "drift":
        drifts = AntiDriftService.check_drift(root_dir)
        if drifts:
            print(f"\n[X] DRIFT DETECTED ({len(drifts)} issues):")
            for d in drifts:
                print(f"  - {d}")
            sys.exit(1)
        else:
            print("\n[OK] Anti-Drift Gate: All LLD modules and entity stubs are synchronized with src/.")
    elif args.command == "rtm":
        specs = MarkdownParser.collect_specs(root_dir)
        rows = TraceabilityService.build_rtm(specs)
        if not rows:
            print("No PRD requirements found to trace.")
            return
        print("\nGenOps Requirements Traceability Matrix (RTM)")
        print("=" * 85)
        print(f"{'Requirement':<35} | {'PRD':<15} | {'Priority':<8} | {'Downstream Design':<20}")
        print("-" * 85)
        for r in rows:
            print(f"{r['req_id']:<35} | {r['prd']:<15} | {r['priority']:<8} | {r['downstream']:<20}")
    elif args.command == "context":
        specs = MarkdownParser.collect_specs(root_dir)
        target = [s for s in specs if s.domain == args.domain or args.domain in s.id or args.domain in str(s.upstream_refs)]
        if not target:
            print(f"No specifications found for domain: '{args.domain}'", file=sys.stderr)
            sys.exit(1)
        print(f"# Context Lineage Slice for Domain: {args.domain}\n")
        for s in target:
            print(f"## [{s.stage.upper()}] {s.id} ({s.path})\n{s.body.strip()}\n\n" + "=" * 60 + "\n")
    elif args.command == "compact":
        p = ContextCompactor.compact(root_dir)
        print(f"[OK] Compacted living memory persisted to {p.relative_to(root_dir).as_posix()}")
    elif args.command == "verify":
        res = CompilerVerifier.verify_workspace(root_dir)
        if res["success"]:
            print("[OK] Compiler & linter verification passed cleanly.")
        else:
            print("[X] Compiler diagnostics found errors:")
            for err in res["errors"]:
                print(f"  - {err}")
            sys.exit(1)
    elif args.command == "report":
        out_html = root_dir / args.html
        ReportService.generate_html_report(root_dir, out_html)
        print(f"[OK] Self-contained executive report generated at {out_html.relative_to(root_dir).as_posix()}.")
    elif args.command == "ingest":
        lld_dest, count = BrownfieldIngestionService.ingest_codebase(root_dir, args.src)
        print(f"[OK] Brownfield baseline LLD generated at {lld_dest.relative_to(root_dir).as_posix()} with {count} detected modules.")
    elif args.command == "mcp":
        server = MCPServer(root_dir)
        server.run()


if __name__ == "__main__":
    main()
