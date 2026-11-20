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
import contextlib
import datetime
import glob
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import unquote, urlparse

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from genops_engine import (  # noqa: E402
    AntiDriftService as _EngineAntiDriftService,
    ExplainService,
    FederationService,
    JsonSchemaValidator,
    SarifExporter,
    SimpleYamlParser,
    WorkspaceService,
    _find_unquoted_colon,
    _split_unquoted,
    _unquote_scalar,
)

__version__ = "3.2.0"

# Standardized POSIX / BSD exit codes
EXIT_OK = 0
EXIT_GATE_FAILURE = 1
EXIT_USAGE_ERROR = 2
EXIT_LOCK_TIMEOUT = 3

# Ensure stdout and stderr handle utf-8 cleanly across Windows/Linux/macOS
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def utc_now_iso() -> str:
    """Return current UTC timestamp formatted per IETF RFC 3339 (YYYY-MM-DDTHH:MM:SSZ)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _JsonLogFormatter(logging.Formatter):
    """Render single-line structured JSON diagnostics to stderr."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(
    verbose: bool = False, quiet: bool = False, log_format: Optional[str] = None
) -> logging.Logger:
    """Configure centralized stderr logging without polluting stdout (critical for MCP stdio)."""
    log = logging.getLogger("genops")
    env_level = os.environ.get("GENOPS_LOG_LEVEL", "WARNING").upper()
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR
    else:
        level = getattr(logging, env_level, logging.WARNING)
    log.setLevel(level)

    fmt_mode = (log_format or os.environ.get("GENOPS_LOG_FORMAT", "text")).strip().lower()
    if fmt_mode == "json":
        formatter: logging.Formatter = _JsonLogFormatter()
    elif verbose:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    else:
        formatter = logging.Formatter("[%(levelname)s] %(message)s")

    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        for handler in log.handlers:
            handler.setFormatter(formatter)
    log.propagate = False
    return log


logger = configure_logging()


def _use_color() -> bool:
    """Return True if ANSI terminal colors are permitted per no-color.org and TTY checks."""
    if "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _use_unicode() -> bool:
    """Return True when stdout supports UTF-8 box-drawing glyphs."""
    if os.environ.get("TERM") == "dumb":
        return False
    enc = getattr(sys.stdout, "encoding", None) or ""
    return "utf" in enc.lower()


def _style(text: str, ansi_code: str) -> str:
    """Wrap text in ANSI color sequence only when terminal color is enabled."""
    if not _use_color():
        return text
    return f"\033[{ansi_code}m{text}\033[0m"


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically write UTF-8 text to *path* via a sibling temporary file and os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
        ConfigManager.invalidate_cache()
        MarkdownParser.invalidate_cache()
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _pkg_agents_dir() -> Path:
    """Return the bundled `.agents` directory housing scripts, schemas, scaffolds, templates, skills, and presets."""
    return Path(__file__).resolve().parent.parent


def _resolve_asset_dir(root_dir: Path, subdir: str) -> Path:
    """Resolve a `.agents/<subdir>` asset folder from *root_dir* or fall back to the bundled engine copy."""
    local = root_dir / ".agents" / subdir
    if local.is_dir():
        return local
    bundled = _pkg_agents_dir() / subdir
    if bundled.is_dir():
        return bundled
    return local


def _safe_rel(path: Path, base: Path) -> str:
    """Format *path* relative to *base* as POSIX text, falling back to full POSIX path for external assets."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _git_head_short(root_dir: Path) -> Optional[str]:
    """Return the abbreviated HEAD commit SHA if *root_dir* resides in a git repository, else None."""
    if not any((p / ".git").exists() for p in [root_dir, *root_dir.parents]):
        return None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            sha = res.stdout.strip()
            return sha or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _record_audit_event_safe(
    root_dir: Path, action: str, stage: str, actor: str, details: Optional[Dict[str, Any]] = None
) -> None:
    """Best-effort audit log append that never fails CLI/MCP gates on read-only workspaces."""
    if not is_genops_project(root_dir):
        return
    try:
        StateRepository(root_dir).append_event(action, stage, actor, details)
    except Exception as exc:
        logger.debug("Skipping audit event %s: %s", action, exc)


# ==============================================================================
# Domain I: Cryptographic & Deterministic State Engine
# ==============================================================================

class DeterministicHasher:
    """Handles cross-platform cryptographic hashing with mandatory LF normalization."""

    # Directories and artifacts that must never be part of a deterministic hash.
    EXCLUDED_DIR_NAMES = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox",
        "dist", "build", "target", ".next", ".genops-demo", ".vscode", ".idea", ".cargo",
    }
    EXCLUDED_FILE_NAMES = {"thumbs.db", "desktop.ini"}
    EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

    @classmethod
    def _should_skip(cls, path: Path, base_dir: Optional[Path] = None) -> bool:
        """Skip bytecode/build artifacts, OS metadata files, dot-directories, virtualenvs, and escaping symlinks."""
        if path.is_symlink():
            try:
                resolved_target = path.resolve()
            except OSError:
                return True
            if base_dir is not None and not ScaffoldingService.is_safe_subpath(resolved_target, base_dir):
                return True
        if path.name.lower() in cls.EXCLUDED_FILE_NAMES:
            return True
        if path.suffix.lower() in cls.EXCLUDED_SUFFIXES:
            return True
        if base_dir is not None:
            try:
                parts = path.relative_to(base_dir).parts
            except ValueError:
                parts = path.parts
        else:
            parts = path.parts
        for part in parts:
            if part in cls.EXCLUDED_DIR_NAMES:
                return True
            if part.startswith(".") and part not in (".", ".."):
                return True
        return False

    @staticmethod
    def normalize_lf(data: bytes) -> bytes:
        """Normalize CRLF (\\r\\n) and standalone CR (\\r) line endings to LF (\\n)."""
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

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
        Compute combined SHA-256 manifest digest of all matching files in dir_path.
        Returns (combined_hash, {relative_filename: file_hash}).
        """
        if not dir_path.is_dir():
            return "", {}

        files = sorted([
            p for p in dir_path.rglob(pattern)
            if p.is_file() and not cls._should_skip(p, dir_path)
        ])
        file_hashes: Dict[str, str] = {}
        for p in files:
            rel = p.relative_to(dir_path).as_posix()
            file_hashes[rel] = cls.hash_file(p)

        return MerkleTree.compute_root(file_hashes), file_hashes

    @classmethod
    def hash_requirements(cls, requires_list: List[str], base_dir: Path) -> Tuple[str, Dict[str, str]]:
        """Compute combined hash across all prerequisite directories and glob patterns."""
        all_files: Dict[str, str] = {}

        for req in requires_list:
            target = base_dir / req
            if target.is_dir():
                _, f_hashes = cls.hash_directory(target)
                for rel, h in f_hashes.items():
                    full_rel = (Path(req) / rel).as_posix()
                    all_files[full_rel] = h
            elif target.is_file():
                if not cls._should_skip(target, base_dir):
                    rel = Path(req).as_posix()
                    all_files[rel] = cls.hash_file(target)
            else:
                matched = sorted(glob.glob(str(base_dir / req)))
                for m in matched:
                    mp = Path(m)
                    if mp.is_file() and not cls._should_skip(mp, base_dir):
                        rel = mp.relative_to(base_dir).as_posix()
                        all_files[rel] = cls.hash_file(mp)

        return MerkleTree.compute_root(all_files), all_files


class MerkleTree:
    """Computes deterministic sorted manifest root digests from file hash maps."""

    @staticmethod
    def compute_root(file_hashes: Dict[str, str]) -> str:
        """Calculate a deterministic SHA-256 manifest digest from {filepath: file_sha256}."""
        if not file_hashes:
            return ""
        hasher = hashlib.sha256()
        for k in sorted(file_hashes.keys()):
            hasher.update(k.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(file_hashes[k].encode("utf-8"))
            hasher.update(b"\n")
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
                try:
                    os.write(self.fd, f"{os.getpid()}:{time.time():.6f}\n".encode("utf-8"))
                except OSError:
                    pass
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
            self.fd = None
            try:
                if self.lock_path.exists():
                    os.remove(self.lock_path)
            except OSError:
                pass


# ==============================================================================
# Domain II: Zero-Dependency JSON Schema Validator (Draft-07 Core via genops_engine)
# ==============================================================================
# JsonSchemaValidator is imported from genops_engine.schema


# ==============================================================================
# Domain III: Document Parsing & Markdown Extraction
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
    """Line-oriented Markdown table parser with fenced-code and escaped-pipe awareness."""

    _DIVIDER_CELL_RE = re.compile(r"^:?-{2,}:?$")

    @staticmethod
    def _split_table_row(line: str) -> List[str]:
        """Split a Markdown pipe-table row ignoring escaped pipes (\\|) and pipes inside backticks."""
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|") and not stripped.endswith("\\|"):
            stripped = stripped[:-1]

        cells: List[str] = []
        buf: List[str] = []
        in_code = False
        i = 0
        while i < len(stripped):
            ch = stripped[i]
            if ch == "\\" and not in_code and i + 1 < len(stripped) and stripped[i + 1] == "|":
                buf.append("|")
                i += 2
                continue
            if ch == "`":
                in_code = not in_code
                buf.append(ch)
            elif ch == "|" and not in_code:
                cells.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
            i += 1
        cells.append("".join(buf).strip())
        return cells

    @classmethod
    def _is_divider_row(cls, line: str) -> bool:
        """Return True if *line* is a valid GFM table header separator row."""
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            return False
        cells = cls._split_table_row(s)
        return bool(cells) and all(cls._DIVIDER_CELL_RE.match(c.replace(" ", "")) for c in cells)

    @classmethod
    def parse_tables(cls, markdown_text: str) -> List[List[Dict[str, str]]]:
        """Parse all markdown tables in a document into row dicts, ignoring fenced code blocks."""
        tables: List[List[Dict[str, str]]] = []
        lines = markdown_text.splitlines()
        in_fence = False
        fence_marker = ""
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith(("```", "~~~")):
                marker = line[:3]
                if not in_fence:
                    in_fence = True
                    fence_marker = marker
                elif marker == fence_marker:
                    in_fence = False
                    fence_marker = ""
                i += 1
                continue
            if in_fence:
                i += 1
                continue

            if line.startswith("|") and line.endswith("|"):
                if i + 1 < len(lines) and cls._is_divider_row(lines[i + 1]):
                    headers = [c.strip("`").strip() for c in cls._split_table_row(line)]
                    table_rows: List[Dict[str, str]] = []
                    i += 2
                    while i < len(lines):
                        row_line = lines[i].strip()
                        if row_line.startswith(("```", "~~~")):
                            break
                        if not (row_line.startswith("|") and row_line.endswith("|")):
                            break
                        cells = cls._split_table_row(row_line)
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
    """Parses frontmatter and content from GenOps Markdown documents with mtime-aware caching."""

    NON_SPEC_DIRS = {"eval", "evals", "rfcs", "guides", "releases", "framework", "audit"}
    _FM_BLOCK_RE = re.compile(r"\A---[ \t]*\r?\n(.*?(?:\r?\n)?)---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
    _FM_CACHE: Dict[Tuple[str, int, int], Tuple[Dict[str, Any], str]] = {}
    _SPEC_CACHE: Dict[Tuple[str, Tuple[Tuple[str, int, int], ...]], List[SpecDocument]] = {}

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._FM_CACHE.clear()
        cls._SPEC_CACHE.clear()

    @staticmethod
    def _parse_frontmatter_value(v: str) -> Any:
        """Parse a single frontmatter scalar or inline [a, b] / {a: b} collection with quote and depth awareness."""
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [MarkdownParser._parse_frontmatter_value(x.strip()) for x in _split_unquoted(inner, ",") if x.strip()]
        if v.startswith("{") and v.endswith("}"):
            return SimpleYamlParser._parse_scalar(v)
        return _unquote_scalar(v)

    @classmethod
    def parse_frontmatter(cls, file_path: Path) -> Tuple[Dict[str, Any], str]:
        """Extract and parse YAML frontmatter block from markdown document (including block scalars and anchors)."""
        if not file_path.is_file():
            return {}, ""
        try:
            st = file_path.stat()
            cache_key = (str(file_path.resolve()), st.st_mtime_ns, st.st_size)
            cached = cls._FM_CACHE.get(cache_key)
            if cached is not None:
                return dict(cached[0]), cached[1]
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except OSError:
            return {}, ""

        match = cls._FM_BLOCK_RE.match(content)
        if not match:
            return {}, content

        fm_raw = match.group(1)
        fm_lines = fm_raw.splitlines()
        body = content[match.end():]

        # Validate top-level frontmatter lines and detect advanced YAML 1.2 constructs (block scalars/anchors)
        uses_advanced_yaml = False
        in_block_indent: Optional[int] = None
        for raw_ln in fm_lines:
            if in_block_indent is not None:
                if not raw_ln.strip():
                    continue
                ind = len(raw_ln) - len(raw_ln.lstrip(" "))
                if ind > in_block_indent:
                    continue
                in_block_indent = None
            stripped = raw_ln.strip()
            if not stripped or stripped.startswith("#"):
                continue
            ind = len(raw_ln) - len(raw_ln.lstrip(" "))
            if ind == 0:
                if stripped.startswith("- "):
                    raise ValueError(f"{file_path.name}: unexpected list item in frontmatter: '{stripped}'")
                c_idx = _find_unquoted_colon(stripped)
                if c_idx == -1 and ":" not in stripped:
                    raise ValueError(f"{file_path.name}: malformed frontmatter line (no ':'): '{stripped}'")
                val_part = stripped[(c_idx if c_idx != -1 else stripped.find(":")) + 1:].strip()
                if val_part.startswith("!"):
                    raise ValueError(f"{file_path.name}: unsupported YAML custom tag in frontmatter: '{val_part}'")
                if val_part in SimpleYamlParser._BLOCK_HEADERS or val_part.startswith(("&", "*")):
                    uses_advanced_yaml = True
                    if val_part in SimpleYamlParser._BLOCK_HEADERS:
                        in_block_indent = ind
            else:
                if not stripped.startswith("- "):
                    uses_advanced_yaml = True

        if uses_advanced_yaml:
            parsed = SimpleYamlParser.parse(fm_raw)
            fm_dict = parsed if isinstance(parsed, dict) else {}
            cls._FM_CACHE[cache_key] = (dict(fm_dict), body)
            return fm_dict, body

        fm_dict = {}
        i = 0
        while i < len(fm_lines):
            line = fm_lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            colon_idx = _find_unquoted_colon(line)
            if colon_idx == -1:
                colon_idx = line.find(":")

            k = line[:colon_idx].strip()
            v = line[colon_idx + 1:].strip()

            if v:
                fm_dict[k] = cls._parse_frontmatter_value(v)
                i += 1
            else:
                items: List[Any] = []
                j = i + 1
                while j < len(fm_lines):
                    sub = fm_lines[j].strip()
                    if not sub:
                        j += 1
                        continue
                    if sub.startswith("- "):
                        items.append(cls._parse_frontmatter_value(sub[2:].strip()))
                        j += 1
                        continue
                    break
                fm_dict[k] = items if items else None
                i = j

        cls._FM_CACHE[cache_key] = (dict(fm_dict), body)
        return fm_dict, body

    @classmethod
    def _stage_dirs_from_config(cls, root_dir: Path) -> Optional[List[Tuple[Path, str]]]:
        """Return configured (output_dir_path, stage_id) pairs under docs/ when genops.yaml exists."""
        cfg_file = root_dir / "genops.yaml"
        if not cfg_file.is_file():
            return None
        try:
            cfg = ConfigManager.load_yaml(cfg_file)
        except Exception as e:
            logger.warning("Failed to load %s while scoping docs: %s", cfg_file, e)
            return None
        docs_dir = (root_dir / "docs").resolve()
        stage_dirs: List[Tuple[Path, str]] = []
        for st in cfg.get("pipeline", {}).get("stages", []):
            sid = str(st.get("id", "")).strip()
            for out_p in st.get("outputs", []):
                cand = (root_dir / str(out_p)).resolve()
                if cand == docs_dir or docs_dir in cand.parents:
                    stage_dirs.append((cand, sid))
        return stage_dirs or None

    @classmethod
    def collect_specs(cls, root_dir: Path) -> List[SpecDocument]:
        """Scan configured pipeline spec directories (or docs/ fallback) and parse frontmatter with mtime caching."""
        base_root = root_dir.resolve()
        docs_dir = base_root / "docs"
        if not docs_dir.exists():
            return []

        configured_dirs = cls._stage_dirs_from_config(base_root)
        md_entries: List[Tuple[Path, Optional[str]]] = []
        seen_paths: Set[Path] = set()

        if configured_dirs is not None:
            for s_dir, sid in configured_dirs:
                if not s_dir.is_dir():
                    continue
                for md in sorted(s_dir.rglob("*.md")):
                    rmd = md.resolve()
                    if rmd not in seen_paths:
                        seen_paths.add(rmd)
                        md_entries.append((rmd, sid))
        else:
            for md in sorted(docs_dir.rglob("*.md")):
                rmd = md.resolve()
                rel_parts = rmd.relative_to(docs_dir).parts
                if any(part.lower() in cls.NON_SPEC_DIRS for part in rel_parts[:-1]):
                    continue
                md_entries.append((rmd, None))

        sig_items: List[Tuple[str, int, int]] = []
        for rmd, _ in md_entries:
            try:
                st = rmd.stat()
                sig_items.append((str(rmd), st.st_mtime_ns, st.st_size))
            except OSError:
                continue
        spec_cache_key = (str(base_root), tuple(sig_items))
        cached_specs = cls._SPEC_CACHE.get(spec_cache_key)
        if cached_specs is not None:
            return list(cached_specs)

        specs: List[SpecDocument] = []
        for md, configured_stage in md_entries:
            if md.name.startswith(".") or md.parent.name.lower() in cls.NON_SPEC_DIRS:
                continue
            try:
                fm, body = cls.parse_frontmatter(md)
            except ValueError as e:
                logger.warning("Skipping unparseable frontmatter in %s: %s", md.relative_to(base_root).as_posix(), e)
                continue
            if not fm:
                continue

            rel_p = md.relative_to(base_root).as_posix()
            spec_id = str(fm.get("id") or md.stem)
            default_stage = configured_stage or md.parent.name
            up_refs = fm.get("upstream_refs", [])
            down_refs = fm.get("downstream_refs", [])
            if not isinstance(up_refs, list):
                up_refs = [str(up_refs)] if up_refs else []
            if not isinstance(down_refs, list):
                down_refs = [str(down_refs)] if down_refs else []
            specs.append(SpecDocument(
                id=spec_id,
                path=rel_p,
                stage=str(fm.get("stage", default_stage)),
                domain=str(fm.get("domain", "")),
                version=str(fm.get("version", "1.0.0")),
                status=str(fm.get("status", "draft")),
                upstream_refs=[str(x) for x in up_refs],
                downstream_refs=[str(x) for x in down_refs],
                frontmatter=fm,
                body=body,
            ))
        cls._SPEC_CACHE[spec_cache_key] = list(specs)
        return specs


# ==============================================================================
# Domain IV: Configuration, Living Memory & Change-Impact Simulator
# ==============================================================================
# SimpleYamlParser is imported from genops_engine.yaml_parser


class ConfigManager:
    """Manages YAML/JSON configuration files and multi-agent instructions with mtime-keyed caching."""

    _YAML_CACHE: Dict[Tuple[str, int, int], Dict[str, Any]] = {}

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._YAML_CACHE.clear()

    @classmethod
    def load_yaml(cls, path: Path) -> Dict[str, Any]:
        """Parse YAML/JSON file using native SimpleYamlParser (or PyYAML if installed) with mtime caching."""
        resolved = path.resolve()
        cache_key: Optional[Tuple[str, int, int]] = None
        try:
            st = resolved.stat()
            cache_key = (str(resolved), st.st_mtime_ns, st.st_size)
            cached = cls._YAML_CACHE.get(cache_key)
            if cached is not None:
                return dict(cached)
        except OSError:
            pass

        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        try:
            parsed_json = json.loads(content)
            res = parsed_json if isinstance(parsed_json, dict) else {}
            if cache_key is not None:
                cls._YAML_CACHE[cache_key] = dict(res)
            return res
        except json.JSONDecodeError:
            pass

        try:
            parsed = SimpleYamlParser.parse(content)
            if isinstance(parsed, dict):
                if cache_key is not None:
                    cls._YAML_CACHE[cache_key] = dict(parsed)
                return parsed
        except ValueError as e:
            try:
                import yaml  # type: ignore[import-not-found]
                parsed_yaml = yaml.safe_load(content)
                res_yaml = parsed_yaml if isinstance(parsed_yaml, dict) else {}
                if cache_key is not None:
                    cls._YAML_CACHE[cache_key] = dict(res_yaml)
                return res_yaml
            except Exception:
                raise ValueError(f"YAML parse error in {path}: {e}") from e
        return {}

    @staticmethod
    def generate_agent_instructions(pipeline_name: str, stages: List[Dict[str, Any]]) -> str:
        """Generate standardized markdown instructions compatible with all coding agents."""
        cmd_table = ["| Command | Scope | Skill Protocol | Description |", "|---|---|---|---|"]
        for st in stages:
            sid = st.get("id", "")
            sname = st.get("name", "")
            sfocus = st.get("focus", "")
            cmd_table.append(f"| `/genops-{sid}` | {sname} | `.agents/skills/genops-{sid}/SKILL.md` | {sfocus} |")
        cmd_table.append("| `/genops` | Pipeline Engine | `.agents/skills/genops/SKILL.md` | Orchestrate pipeline, check health status |")

        table_str = "\n".join(cmd_table)
        return f"""<!-- GENOPS:START — managed by genops-init, edit pipeline stages via genops.yaml -->

## GenOps Cascading Specification Pipeline ({pipeline_name})

This project uses **GenOps**, a separation-of-concerns pipeline engine that decomposes complex software work into isolated, cascading specification stages backed by deterministic LF-normalized SHA-256 tracking.

> When a user invokes `/genops-<stage>` (or requests a pipeline stage), read `.agents/skills/genops-stage/SKILL.md` and `.agents/skills/genops-<stage>/SKILL.md` before executing.

### Available Stage Commands

{table_str}

### Flow Modes

| Mode | Command Example | Description |
|---|---|---|
| **SoC (Default)** | `/genops-prd` | One stage at a time. Solicits human approval before offering next. |
| **Targeted** | `/genops-prd --domain <slug>` | Scopes execution or modification exclusively to specified domain. |
| **Flow** | `/genops-prd --flow` | Completes stage, then automatically cascades to next stage. |
| **Nonstop** | `/genops-prd --nonstop` | Runs full cascade with approval gates at each stage. |
| **Fast-Track** | `/genops-prd --fast` | Generates immediate spec draft from context with inline critic notes. |
| **Incremental** | `/genops --from adr --domain <slug>` | Starts incremental cascade for a single domain. |
| **Status** | `/genops --status` | Shows live pipeline health and stale downstream flags. |

### Separation of Concerns Protocol

Each stage execution adheres strictly to:
1. **Pre-flight**: Verifies prerequisites exist and are approved (`python .agents/scripts/genops.py validate`).
2. **Context**: Loads `.agents/context/CONTEXT.md` first; uses `python .agents/scripts/genops.py context --domain <slug>` when upstream specs exceed 60k chars.
3. **Drafting**: Generates modular `{{STAGE}}-{{NNN}}-{{slug}}.md` documents with standardized YAML frontmatter and zero `TODO`/`TBD` placeholders.
4. **Approval**: Hard gate requiring explicit confirmation before transition.
5. **State Recording**: Updates `docs/.genops-state.json` (v2.0) and appends a hash-chained event to `docs/.genops-events.jsonl` (`python .agents/scripts/genops.py record <stage>`).

### Execution & Architectural Invariants

- **Zero-Chatter & Token Economy**: Lead with actionable output, specs, diffs, or gate receipts. No pleasantries or filler. Batch independent tool calls in parallel and cap command outputs at <= 2,500 bytes.
- **First-Principles Engineering**: Resolve root causes directly; never weaken schemas, lineage rules, anti-drift checks, or compiler verifications to pass a gate.
- **Mutation Exactness (RFC-0018)**: Immediately before editing an existing file, read the exact target range on disk and use its verbatim bytes as the replacement anchor. Write new files once with final content; never write-then-edit.
- **Workspace Hygiene**: Keep the repository root clean. Store temporary probes in `.agents/loop/scratch/` (or isolated `tempfile` directories in tests) and remove transient artifacts upon completion.
- **Verification Gate**: Run `python .agents/scripts/genops.py doctor` and `python -m unittest discover -s tests -p "test_*.py"` after engine or pipeline changes.

<!-- GENOPS:END -->"""

    _TITLE_MAP = {
        "AGENTS.md": "Agent Operating Governance & GenOps Instructions",
        "CLAUDE.md": "Claude Code Instructions",
        "GEMINI.md": "Gemini & Antigravity Instructions",
        "CONVENTIONS.md": "Engineering Conventions & GenOps Protocol",
        ".windsurfrules": "Windsurf Agent Rules",
        ".cursorrules": "Cursor Agent Rules",
        "genops.mdc": "Cursor GenOps Rule",
        "copilot-instructions.md": "GitHub Copilot Instructions",
    }

    @classmethod
    def sync_agent_file(cls, file_path: Path, new_block: str, dry_run: bool = False) -> bool:
        """Safely insert or update GENOPS:START/END block in an agent instruction file."""
        header_pattern = re.compile(r"<!-- GENOPS:START.*?-->.*?<!-- GENOPS:END -->", re.DOTALL)

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if header_pattern.search(content):
                updated = header_pattern.sub(lambda _: new_block, content)
            else:
                updated = content.rstrip() + "\n\n" + new_block + "\n"
        else:
            raw_stem = file_path.stem.lstrip(".")
            clean_stem = re.sub(r"[-_]?instructions$", "", raw_stem, flags=re.IGNORECASE).upper() or "GENOPS"
            title = cls._TITLE_MAP.get(file_path.name, f"{clean_stem} Instructions")
            updated = f"# {title}\n\n{new_block}\n"

        if file_path.suffix == ".mdc" and not updated.lstrip().startswith("---"):
            mdc_header = (
                "---\n"
                "description: GenOps Cascading Specification Pipeline rules and slash-command protocols\n"
                'globs: "**/*"\n'
                "alwaysApply: true\n"
                "---\n\n"
            )
            updated = mdc_header + updated

        if not dry_run:
            _atomic_write_text(file_path, updated)
        return True


class ContextCompactor:
    """Extracts structured specifications and compacts living memory into CONTEXT.md."""

    @classmethod
    def compact(cls, root_dir: Path) -> Path:
        """Scan configured spec outputs and synthesize an active, high-density system context card."""
        specs = MarkdownParser.collect_specs(root_dir)
        context_file = root_dir / ".agents" / "context" / "CONTEXT.md"

        # 1. Extract Project Name, Active Domains & Domain Glossary
        domains = sorted({s.domain for s in specs if s.domain})
        project_name = ", ".join(d.replace("-", " ").title() for d in domains) if domains else "GenOps Managed System"
        glossary_items: Dict[str, str] = {}
        for s in specs:
            if s.stage in ("prd", "brief", "lit-review"):
                tables = MarkdownTable.parse_tables(s.body)
                for t in tables:
                    for row in t:
                        persona = row.get("Persona") or row.get("User Persona") or row.get("As a...")
                        desc = row.get("Role Description") or row.get("Primary Goal") or row.get("Key Motivations")
                        if persona and desc and persona.lower() not in ("persona", "user persona", "as a..."):
                            glossary_items[persona.strip()] = desc.strip()

        # 2. Extract Technology Preferences from accepted ADRs (or design tokens from mockups)
        tech_prefs: List[Dict[str, str]] = []
        constraints: List[str] = []
        for s in specs:
            if s.stage == "adr" and s.status.lower() in ("accepted", "approved"):
                tech_prefs.append({
                    "concern": s.domain.title() or "Architecture",
                    "choice": s.id,
                    "reason": f"Formally accepted in {s.path}"
                })
                match = re.search(r"##\s*(\d+\.\s*)?Downstream Directives.*?\n(.*?)(?=\n##|\Z)", s.body, re.DOTALL | re.IGNORECASE)
                if match:
                    directives_block = match.group(2)
                    for line in directives_block.splitlines():
                        line = line.strip()
                        if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
                            constraints.append(line.lstrip("-*0123456789. "))
            elif s.stage == "mockups" and s.status.lower() in ("accepted", "approved"):
                tech_prefs.append({
                    "concern": f"Design System ({s.domain or 'UI'})",
                    "choice": s.id,
                    "reason": f"Design tokens defined in {s.path}",
                })

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
                                cleaned = e.strip().strip("`")
                                if cleaned and cleaned not in entities_list:
                                    entities_list.append(cleaned)

        glossary_rows = "\n".join([f"| {k} | {v} |" for k, v in glossary_items.items()]) or "| (Discovered during PRD / Brief) | (Definitions) |"
        tech_rows = "\n".join([f"| {tp['concern']} | {tp['choice']} | {tp['reason']} |" for tp in tech_prefs]) or "| (Discovered during ADR) | (Selection) | (Trade-off context) |"
        constraint_bullets = "\n".join([f"- {c}" for c in constraints]) or "- Constraints will be extracted from accepted ADRs."
        entities_str = ", ".join([f"`{e}`" for e in entities_list]) or "None indexed yet"
        domains_str = ", ".join([f"`{d}`" for d in domains]) or "None indexed yet"
        now_iso = utc_now_iso()

        compact_content = f"""# Living Project Context

> Auto-compacted by GenOps Engine on {now_iso}.
> Loaded natively by every GenOps agent skill during Step 1 (LOAD).

## Project Overview
* **System Domain:** {project_name}
* **Active Domains:** {domains_str}
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

        _atomic_write_text(context_file, compact_content)
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

        downstream_adj: Dict[str, List[str]] = {s.id: [] for s in specs}
        spec_by_id: Dict[str, SpecDocument] = {s.id: s for s in specs}

        for s in specs:
            for up in s.upstream_refs:
                if up in downstream_adj:
                    downstream_adj[up].append(s.id)
            for down in s.downstream_refs:
                if down in downstream_adj:
                    downstream_adj[s.id].append(down)

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
        _rank = {"prd": 0, "brief": 0, "lit-review": 0, "hld": 1, "wireframes": 1, "hypothesis": 1,
                 "adr": 2, "mockups": 2, "experiment": 2, "lld": 3, "prototype": 3, "report": 3, "code": 4}
        affected_specs.sort(key=lambda s: (_rank.get(s.stage, 99), s.stage, s.id))

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
                                    cleaned = e.strip().strip("`")
                                    if cleaned and cleaned not in affected_entities:
                                        affected_entities.append(cleaned)

        src_dir = root_dir / "src"
        affected_source_files: List[str] = []
        for mod in affected_modules:
            mod_path = src_dir / mod
            if mod_path.exists():
                for p in sorted(mod_path.rglob("*")):
                    if p.is_file() and not DeterministicHasher._should_skip(p, mod_path):
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

    DEFAULT_TIMEOUT = 120

    @classmethod
    def verify_workspace(cls, root_dir: Path, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Scan src/ (ignoring virtualenvs/node_modules/build output) and run detected compilers/linters."""
        src_dir = root_dir / "src"
        results: Dict[str, Any] = {"success": True, "checks": [], "errors": [], "skipped": []}

        if not src_dir.exists():
            return results

        # 1. Python syntax + optional Ruff lint
        py_files = [
            p for p in sorted(src_dir.rglob("*.py"))
            if not DeterministicHasher._should_skip(p, src_dir)
            and not p.name.startswith("-")
            and not any(part.startswith("-") for part in p.relative_to(src_dir).parts)
        ]
        if py_files:
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "py_compile"] + [str(p.resolve()) for p in py_files],
                    capture_output=True, text=True, timeout=timeout,
                )
                if res.returncode != 0:
                    results["success"] = False
                    results["errors"].append(f"Python compilation error: {res.stderr}")
                else:
                    results["checks"].append(f"Python syntax verified ({len(py_files)} files)")
            except subprocess.TimeoutExpired:
                results["success"] = False
                results["errors"].append(f"Python compilation timed out after {timeout}s")
            except OSError:
                results["skipped"].append("Python syntax check skipped (interpreter unavailable)")

            ruff_bin = shutil.which("ruff")
            if ruff_bin:
                try:
                    res = subprocess.run(
                        [ruff_bin, "check", "--"] + [str(p.resolve()) for p in py_files],
                        capture_output=True, text=True, timeout=timeout,
                    )
                    if res.returncode == 0:
                        results["checks"].append(f"Ruff lint passed ({len(py_files)} files)")
                    else:
                        results["success"] = False
                        results["errors"].append(f"Ruff lint issues:\n{res.stdout}\n{res.stderr}")
                except subprocess.TimeoutExpired:
                    results["success"] = False
                    results["errors"].append(f"Ruff lint timed out after {timeout}s")
                except OSError:
                    results["skipped"].append("Ruff lint skipped (not installed)")
            else:
                results["skipped"].append("Ruff lint skipped (not installed)")

        # 2. Go vet + build checks if go.mod exists
        go_mods = [p for p in sorted(src_dir.rglob("go.mod")) if not DeterministicHasher._should_skip(p, src_dir)]
        go_bin = shutil.which("go")
        for gm in go_mods:
            rel_gm = gm.parent.relative_to(root_dir)
            if not go_bin:
                results["skipped"].append(f"Go vet+build skipped: {rel_gm} (toolchain not installed)")
                continue
            try:
                vet = subprocess.run([go_bin, "vet", "./..."], cwd=gm.parent, capture_output=True, text=True, timeout=timeout)
                build = subprocess.run([go_bin, "build", "./..."], cwd=gm.parent, capture_output=True, text=True, timeout=timeout)
                if vet.returncode == 0 and build.returncode == 0:
                    results["checks"].append(f"Go vet+build passed: {rel_gm}")
                else:
                    results["success"] = False
                    detail = (vet.stderr or "") + (build.stderr or "")
                    results["errors"].append(f"Go error in {gm.parent}: {detail}")
            except subprocess.TimeoutExpired:
                results["success"] = False
                results["errors"].append(f"Go check timed out in {rel_gm} after {timeout}s")
            except OSError:
                results["skipped"].append(f"Go vet+build skipped: {rel_gm} (toolchain not installed)")

        # 3. Rust cargo check
        cargo_tomls = [p for p in sorted(src_dir.rglob("Cargo.toml")) if not DeterministicHasher._should_skip(p, src_dir)]
        cargo_bin = shutil.which("cargo")
        for ct in cargo_tomls:
            rel_ct = ct.parent.relative_to(root_dir)
            if not cargo_bin:
                results["skipped"].append(f"Rust cargo check skipped: {rel_ct} (toolchain not installed)")
                continue
            try:
                res = subprocess.run([cargo_bin, "check"], cwd=ct.parent, capture_output=True, text=True, timeout=timeout)
                if res.returncode == 0:
                    results["checks"].append(f"Rust cargo check passed: {rel_ct}")
                else:
                    results["success"] = False
                    results["errors"].append(f"Rust cargo check error in {ct.parent}: {res.stderr}")
            except subprocess.TimeoutExpired:
                results["success"] = False
                results["errors"].append(f"Rust cargo check timed out in {rel_ct} after {timeout}s")
            except OSError:
                results["skipped"].append(f"Rust cargo check skipped: {rel_ct} (toolchain not installed)")

        # 4. TypeScript/Node check via local tsc, global tsc, or npx --no-install tsc
        tsconfigs = [p for p in sorted(src_dir.rglob("tsconfig.json")) if not DeterministicHasher._should_skip(p, src_dir)]
        for tsconfig in tsconfigs:
            rel_ts = tsconfig.parent.relative_to(root_dir)
            tsc_name = "tsc.cmd" if sys.platform == "win32" else "tsc"
            local_tsc = tsconfig.parent / "node_modules" / ".bin" / tsc_name
            global_tsc = shutil.which("tsc")
            npx_bin = shutil.which("npx")
            if local_tsc.is_file():
                cmd = [str(local_tsc), "--noEmit", "-p", str(tsconfig)]
            elif global_tsc:
                cmd = [global_tsc, "--noEmit", "-p", str(tsconfig)]
            elif npx_bin and (tsconfig.parent / "node_modules").is_dir():
                cmd = [npx_bin, "--no-install", "tsc", "--noEmit", "-p", str(tsconfig)]
            else:
                results["skipped"].append(f"TypeScript tsc skipped: {rel_ts} (tsc not installed)")
                continue
            try:
                res = subprocess.run(cmd, cwd=tsconfig.parent, capture_output=True, text=True, timeout=timeout)
                if res.returncode == 0:
                    results["checks"].append(f"TypeScript tsc --noEmit passed: {rel_ts}")
                else:
                    results["success"] = False
                    detail = (res.stdout or "") + (res.stderr or "")
                    results["errors"].append(f"TypeScript error in {tsconfig.parent}: {detail}")
            except subprocess.TimeoutExpired:
                results["success"] = False
                results["errors"].append(f"TypeScript check timed out in {rel_ts} after {timeout}s")
            except OSError:
                results["skipped"].append(f"TypeScript tsc skipped: {rel_ts} (npx/tsc not installed)")

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

        effective_entity = entity_raw.strip() if entity_raw and entity_raw.strip() else ("".join(w.capitalize() for w in m_words) or "Entity")
        e_words = cls.split_words(effective_entity) or ["Entity"]
        e_clean = effective_entity.replace("-", " ").replace("_", " ")
        mapping.update({
            "entity": "".join(w.capitalize() for w in e_words),
            "Entity": "".join(w.capitalize() for w in e_words),
            "entity_name": e_clean.title(),
            "entity_lower": effective_entity.lower().replace("-", "").replace("_", ""),
            "entity_kebab": "-".join(w.lower() for w in e_words),
            "entity_snake": "_".join(w.lower() for w in e_words),
            "entity_camel": (e_words[0].lower() + "".join(w.capitalize() for w in e_words[1:])),
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
    def _go_pkg_name(dir_name: str) -> str:
        """Sanitize a directory name into a valid Go package identifier."""
        cleaned = re.sub(r"[^a-z0-9]", "", dir_name.lower())
        if not cleaned or cleaned[0].isdigit():
            return f"pkg{cleaned}"
        return cleaned

    @classmethod
    def _default_file_content(cls, path: Path) -> str:
        """Return a minimal, syntactically valid body for an unconditional boilerplate file."""
        name = path.name
        if name == "__init__.py":
            return ""
        if name == "index.html":
            return (
                "<!doctype html>\n"
                '<html lang="en">\n'
                "  <head>\n"
                '    <meta charset="UTF-8" />\n'
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
                f"    <title>{html.escape(path.parent.name)}</title>\n"
                "  </head>\n"
                "  <body>\n"
                '    <div id="root"></div>\n'
                '    <script type="module" src="/src/main.tsx"></script>\n'
                "  </body>\n"
                "</html>\n"
            )
        if name == "App.tsx":
            return (
                "export function App() {\n"
                '  return <main><h1>GenOps Application</h1></main>;\n'
                "}\n\n"
                "export default App;\n"
            )
        if name == "main.tsx":
            return (
                "import { StrictMode } from 'react';\n"
                "import { createRoot } from 'react-dom/client';\n"
                "import { App } from './App';\n\n"
                "const root = document.getElementById('root');\n"
                "if (root) {\n"
                "  createRoot(root).render(<StrictMode><App /></StrictMode>);\n"
                "}\n"
            )
        if name.endswith(".go"):
            return f"package {cls._go_pkg_name(path.parent.name)}\n"
        if name.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
            return "export {};\n"
        if name.endswith(".py"):
            return f'"""{name} boilerplate."""\n'
        if name.endswith(".rs"):
            return f"//! {name} module\n"
        return f"// {name} boilerplate\n"

    @classmethod
    def _entity_stub_content(
        cls, lang: str, stub_type: str, ent_casing: Dict[str, str], stub_path: Path
    ) -> str:
        """Generate role-aware, syntactically valid stub code that never causes symbol collisions."""
        entity = ent_casing["entity"]
        entity_name = ent_casing["entity_name"]
        entity_snake = ent_casing["entity_snake"]
        stype = stub_type.lower()

        if "go" in lang:
            pkg = cls._go_pkg_name(stub_path.parent.name)
            if "test" in stype:
                return (
                    f"package {pkg}\n\n"
                    'import "testing"\n\n'
                    f"func Test{entity}(t *testing.T) {{\n"
                    f'\te := {entity}{{ID: "test-1"}}\n'
                    '\tif e.ID == "" {\n'
                    '\t\tt.Fatal("expected non-empty ID")\n'
                    "\t}\n"
                    "}\n"
                )
            if stype in ("service", "repository", "handler"):
                suffix = stype.capitalize()
                return (
                    f"package {pkg}\n\n"
                    f"// {entity}{suffix} handles {stype} operations for {entity_name}.\n"
                    f"type {entity}{suffix} struct{{}}\n"
                )
            return (
                f"package {pkg}\n\n"
                f"// {entity} represents the {entity_name} domain entity.\n"
                f"type {entity} struct {{\n\tID string\n}}\n"
            )

        if "python" in lang:
            if "test" in stype:
                return (
                    f'"""Unit tests for {entity} domain entity."""\n\n'
                    "import unittest\n\n\n"
                    f"class Test{entity}(unittest.TestCase):\n"
                    f"    def test_{entity_snake}_placeholder(self) -> None:\n"
                    "        self.assertTrue(True)\n"
                )
            if stype in ("service", "adapter", "router"):
                suffix = stype.capitalize()
                return f'"""{entity}{suffix} layer."""\n\n\nclass {entity}{suffix}:\n    pass\n'
            return f'"""{entity} domain model."""\n\nfrom dataclasses import dataclass\n\n\n@dataclass\nclass {entity}:\n    id: str\n'

        if "rust" in lang:
            if "test" in stype:
                return (
                    f"//! Integration tests for {entity}\n\n"
                    "#[test]\n"
                    f"fn test_{entity_snake}_placeholder() {{\n"
                    "    assert_eq!(1 + 1, 2);\n"
                    "}\n"
                )
            if stype in ("service", "handler"):
                suffix = stype.capitalize()
                return f"//! {entity}{suffix} module\n\npub struct {entity}{suffix};\n"
            return (
                f"//! {entity} module\n\n"
                "#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]\n"
                f"pub struct {entity} {{\n    pub id: String,\n}}\n"
            )

        if "typescript" in lang or "react" in lang or "node" in lang:
            if "test" in stype:
                return (
                    "import { describe, it, expect } from 'vitest';\n\n"
                    f"describe('{entity}', () => {{\n"
                    "  it('is defined', () => {\n"
                    "    expect(true).toBe(true);\n"
                    "  });\n"
                    "});\n"
                )
            if stype == "component":
                return (
                    f"export function {entity}Card() {{\n"
                    f"  return <div>{entity_name}</div>;\n"
                    "}\n"
                )
            if stype == "hook":
                return (
                    f"export function use{entity}() {{\n"
                    "  return { loading: false };\n"
                    "}\n"
                )
            if stype in ("service", "controller"):
                suffix = stype.capitalize()
                return f"export class {entity}{suffix} {{}}\n"
            return f"export interface {entity} {{\n  id: string;\n}}\n"

        return f"// {entity} ({stub_type}) stub\n"

    @classmethod
    def scaffold_module(
        cls,
        root_dir: Path,
        module: str,
        scaffold_id: str,
        entities: List[str],
        force: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute deterministic template expansion for a designated module without printing to stdout."""
        scaffolds_root = _resolve_asset_dir(root_dir, "scaffolds")
        scaffold_dir = scaffolds_root / scaffold_id
        if not cls.is_safe_subpath(scaffold_dir, scaffolds_root):
            raise ValueError(f"Path traversal detected in scaffold id: {scaffold_id}")
        struct_file = scaffold_dir / "STRUCTURE.yaml"

        if not struct_file.exists():
            raise FileNotFoundError(f"Scaffold '{scaffold_id}' not found at {struct_file}")

        scaff = ConfigManager.load_yaml(struct_file)
        src_dir = root_dir / "src"
        casing = cls.build_casing_map(module, entities[0] if entities else "")
        module_kebab = casing["module_kebab"] or module
        module_dest = src_dir / module_kebab
        if not cls.is_safe_subpath(module_dest, src_dir):
            raise ValueError(f"Path traversal detected in module name: {module}")

        summary: Dict[str, Any] = {
            "module": module_kebab,
            "scaffold": scaffold_id,
            "dry_run": dry_run,
            "directories": [],
            "created": [],
            "overwritten": [],
            "skipped": [],
        }

        for d in scaff.get("directories", []):
            expanded_d = d
            for k, v in casing.items():
                expanded_d = expanded_d.replace(f"{{{k}}}", v)
            full_d = module_dest / expanded_d
            if not cls.is_safe_subpath(full_d, src_dir):
                raise ValueError(f"Path traversal detected in directory definition: {d}")
            if not dry_run:
                full_d.mkdir(parents=True, exist_ok=True)
            summary["directories"].append(full_d.relative_to(root_dir).as_posix())

        templates_map = scaff.get("templates", {})
        for tmpl_name, dest_pattern in templates_map.items():
            tmpl_src = scaffold_dir / tmpl_name
            if not tmpl_src.exists():
                continue
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

            rel_str = dest_path.relative_to(root_dir).as_posix()
            if dest_path.exists() and not force:
                summary["skipped"].append(rel_str)
                continue
            existed = dest_path.exists()
            if not dry_run:
                _atomic_write_text(dest_path, tmpl_text)
            (summary["overwritten"] if existed else summary["created"]).append(rel_str)

        # default_files: unconditional boilerplate files
        for df_pattern in scaff.get("default_files", []):
            df_rel = df_pattern
            for k, v in casing.items():
                df_rel = df_rel.replace(f"{{{k}}}", v)

            df_path = src_dir / df_rel
            if not cls.is_safe_subpath(df_path, src_dir):
                raise ValueError(f"Path traversal detected in default file: {df_pattern}")

            rel_str = df_path.relative_to(root_dir).as_posix()
            if df_path.exists():
                summary["skipped"].append(rel_str)
                continue
            if not dry_run:
                _atomic_write_text(df_path, cls._default_file_content(df_path))
            summary["created"].append(rel_str)

        stubs_map = scaff.get("entity_stubs", {})
        lang = str(scaff.get("language", "")).lower()
        for ent in entities:
            ent_casing = cls.build_casing_map(module, ent)
            for stub_type, stub_pattern in stubs_map.items():
                stub_rel = stub_pattern
                for k, v in ent_casing.items():
                    stub_rel = stub_rel.replace(f"{{{k}}}", v)

                stub_path = module_dest / stub_rel
                if not cls.is_safe_subpath(stub_path, src_dir):
                    raise ValueError(f"Path traversal detected in entity stub: {stub_rel}")

                rel_str = stub_path.relative_to(root_dir).as_posix()
                if stub_path.exists():
                    summary["skipped"].append(rel_str)
                    continue
                if not dry_run:
                    stub_content = cls._entity_stub_content(lang, stub_type, ent_casing, stub_path)
                    _atomic_write_text(stub_path, stub_content)
                summary["created"].append(rel_str)

        return summary


class AntiDriftService:
    """Enforces AST/symbol, filename, reverse-module, and SQL contract anti-drift between LLD designs and source code."""

    _SOURCE_EXTS = _EngineAntiDriftService._SOURCE_EXTS

    @classmethod
    def _entity_symbol_in_module(cls, mod_path: Path, ent_pascal: str, raw_ent: str = "") -> bool:
        return _EngineAntiDriftService._entity_symbol_in_module(
            mod_path, ent_pascal, raw_ent=raw_ent, should_skip_fn=DeterministicHasher._should_skip
        )

    @classmethod
    def check_drift(cls, root_dir: Path) -> List[str]:
        return _EngineAntiDriftService.check_drift(
            root_dir, MarkdownTable, ScaffoldingService, DeterministicHasher
        )


class TraceabilityService:
    """Generates Bidirectional Requirements Traceability Matrix (RTM) across software-spec, design, and research presets."""

    _HEADING_US_RE = re.compile(r"^###\s+((?:US|REQ|GOAL|H)-[A-Za-z0-9_-]+):\s*(.+)$")
    _PRIO_LINE_RE = re.compile(r"\*\*Priority:\*\*\s*`?([P0-3]{2}|High|Medium|Low|Critical)`?", re.IGNORECASE)
    _ROOT_RTM_STAGES = {"prd", "brief", "hypothesis", "lit-review"}

    @classmethod
    def _trace_downstream_chain(cls, start_id: str, downstream_adj: Dict[str, List[str]], spec_by_id: Dict[str, SpecDocument]) -> Tuple[str, Dict[str, List[str]]]:
        """Compute full transitive downstream lineage across software-spec, design, and research stages."""
        visited: Set[str] = set()
        queue = [start_id]
        idx = 0
        while idx < len(queue):
            curr = queue[idx]
            idx += 1
            for nxt in downstream_adj.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)

        chain: Dict[str, List[str]] = {"hld": [], "adr": [], "lld": [], "modules": []}
        for sid in sorted(visited):
            sp = spec_by_id.get(sid)
            if not sp:
                continue
            if sp.stage in ("hld", "wireframes", "hypothesis"):
                chain["hld"].append(sp.id)
            elif sp.stage in ("adr", "mockups", "experiment"):
                chain["adr"].append(sp.id)
            elif sp.stage in ("lld", "prototype", "report"):
                chain["lld"].append(sp.id)
                for tbl in MarkdownTable.parse_tables(sp.body):
                    for row in tbl:
                        mod = row.get("Module", "").strip().strip("`")
                        if mod and mod.lower() not in ("module", "---", "name") and mod not in chain["modules"]:
                            chain["modules"].append(mod)

        parts: List[str] = []
        for key in ("hld", "adr", "lld"):
            if chain[key]:
                parts.extend(chain[key])
        if chain["modules"]:
            parts.extend(f"src/{m}/" for m in chain["modules"])
        return (", ".join(parts) if parts else "UNMAPPED"), chain

    @classmethod
    def build_rtm(cls, specs: List[SpecDocument]) -> List[Dict[str, Any]]:
        """Extract requirements/stories/goals/hypotheses from root specs and trace downstream lineage."""
        downstream_adj: Dict[str, List[str]] = {s.id: [] for s in specs}
        spec_by_id: Dict[str, SpecDocument] = {s.id: s for s in specs}
        for s in specs:
            for up in s.upstream_refs:
                if up in downstream_adj and s.id not in downstream_adj[up]:
                    downstream_adj[up].append(s.id)
            for down in s.downstream_refs:
                if down in spec_by_id and down not in downstream_adj[s.id]:
                    downstream_adj[s.id].append(down)

        rows: List[Dict[str, Any]] = []
        for s in specs:
            if s.stage not in cls._ROOT_RTM_STAGES:
                continue
            downstream_str, chain = cls._trace_downstream_chain(s.id, downstream_adj, spec_by_id)
            seen_ids: Set[str] = set()

            # 1. Extract from tabular requirement / goal / hypothesis tables
            for table in MarkdownTable.parse_tables(s.body):
                for r in table:
                    prio = (r.get("Priority") or r.get("Importance") or r.get("Status") or "").strip().strip("`")
                    want = (
                        r.get("I want to...")
                        or r.get("User Story")
                        or r.get("Capability")
                        or r.get("Requirement")
                        or r.get("Goal")
                        or r.get("Hypothesis")
                        or r.get("Statement")
                        or ""
                    ).strip()
                    req_code = (
                        r.get("Req ID", "").strip().strip("`")
                        or r.get("User Story", "").strip().strip("`")
                        or r.get("Goal ID", "").strip().strip("`")
                        or r.get("Hypothesis ID", "").strip().strip("`")
                        or r.get("ID", "").strip().strip("`")
                    )
                    if not prio and (req_code or want):
                        prio = "P1"
                    if not prio or prio.lower() in ("priority", "importance", "status", "---"):
                        continue
                    if not req_code and not want:
                        continue
                    label = req_code or (f"{s.id}:{want[:25]}..." if want else s.id)
                    key = req_code or label
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    rows.append({
                        "req_id": f"{s.id}:{req_code}" if req_code and not req_code.startswith(s.id) else label,
                        "prd": s.id,
                        "priority": prio,
                        "downstream": downstream_str,
                        "lineage": chain,
                    })

            # 2. Extract from heading-style stories/goals/hypotheses (### US-01: ..., ### GOAL-01: ..., ### H-01: ...)
            lines = s.body.splitlines()
            for idx, line in enumerate(lines):
                m = cls._HEADING_US_RE.match(line.strip())
                if not m:
                    continue
                us_id = m.group(1).strip()
                us_title = m.group(2).strip()
                if us_id in seen_ids:
                    continue
                prio = "P1"
                for lookahead in lines[idx + 1: idx + 6]:
                    pm = cls._PRIO_LINE_RE.search(lookahead)
                    if pm:
                        prio = pm.group(1).upper()
                        break
                seen_ids.add(us_id)
                rows.append({
                    "req_id": f"{us_id}: {us_title}"[:35],
                    "prd": s.id,
                    "priority": prio,
                    "downstream": downstream_str,
                    "lineage": chain,
                })
        return rows


class ReportService:
    """Generates self-contained, WCAG-accessible, print-ready executive HTML audit dashboard."""

    @staticmethod
    def _badge_class(state: str) -> str:
        st = state.lower()
        if st in ("approved", "accepted", "pass"):
            return "badge-green"
        if st in ("stale", "modified", "fail", "error"):
            return "badge-red"
        if st in ("drafting", "generated"):
            return "badge-amber"
        return "badge-slate"

    @classmethod
    def generate_html_report(cls, root_dir: Path, output_file: Path) -> None:
        specs = MarkdownParser.collect_specs(root_dir)
        state_repo = StateRepository(root_dir)
        cfg_file = root_dir / "genops.yaml"
        next_action = ""
        if cfg_file.is_file():
            live_status = state_repo.compute_live_status()
            stage_items = live_status.get("stages", {})
            next_action = str(live_status.get("next_action", ""))
        else:
            raw_state = state_repo.load_state()
            stage_items = raw_state.get("stages", {})
        drifts = AntiDriftService.check_drift(root_dir)
        violations = LineageGraphService.check_rules(specs, root_dir)
        rtm_rows = TraceabilityService.build_rtm(specs)
        traced_reqs = sum(1 for r in rtm_rows if str(r.get("downstream", "UNMAPPED")).upper() != "UNMAPPED")
        rtm_cov_pct = round((traced_reqs / len(rtm_rows)) * 100) if rtm_rows else 100

        stages_html = ""
        approved_count = 0
        for sid, sinfo in stage_items.items():
            st_val = str(sinfo.get("state", "absent"))
            if st_val == "approved":
                approved_count += 1
            badge = cls._badge_class(st_val)
            chash = str(sinfo.get("live_output_hash") or sinfo.get("combined_hash") or "N/A")
            stages_html += f"""
            <tr>
                <td><strong>{html.escape(sid.upper())}</strong></td>
                <td><span class="badge {badge}">{html.escape(st_val)}</span></td>
                <td>{html.escape(str(sinfo.get('last_run', 'Never'))[:20])}</td>
                <td><code>{html.escape(chash[:12]) if chash != 'N/A' else 'N/A'}</code></td>
                <td>{int(sinfo.get('file_count', 0))} files</td>
            </tr>
            """
        if not stages_html:
            stages_html = '<tr><td colspan="5" style="color:#94a3b8;">No pipeline stages recorded yet. Run <code>genops record &lt;stage&gt;</code> after stage approval.</td></tr>'

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
        if not specs_html:
            specs_html = '<tr><td colspan="6" style="color:#94a3b8;">No specifications indexed in configured <code>docs/</code> directories yet.</td></tr>'

        rtm_html = ""
        for r in rtm_rows:
            rtm_html += f"""
            <tr>
                <td><strong>{html.escape(str(r.get('req_id', '')))}</strong></td>
                <td><code>{html.escape(str(r.get('prd', '')))}</code></td>
                <td>{html.escape(str(r.get('priority', '')))}</td>
                <td>{html.escape(str(r.get('downstream', 'UNMAPPED')))}</td>
            </tr>
            """
        if not rtm_html:
            rtm_html = '<tr><td colspan="4" style="color:#94a3b8;">No PRD requirements found to trace yet.</td></tr>'

        events_html = ""
        if state_repo.event_file.is_file():
            try:
                event_lines = [ln for ln in state_repo.event_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
                for ln in reversed(event_lines[-20:]):
                    ev = json.loads(ln)
                    eh = str(ev.get("event_hash", ""))[:12] or "legacy"
                    events_html += f"""
                    <tr>
                        <td>{html.escape(str(ev.get('timestamp', '')))}</td>
                        <td><code>{html.escape(str(ev.get('action', '')))}</code></td>
                        <td>{html.escape(str(ev.get('stage', '')))}</td>
                        <td>{html.escape(str(ev.get('actor', '')))}</td>
                        <td><code>{html.escape(eh)}</code></td>
                    </tr>
                    """
            except (OSError, json.JSONDecodeError):
                pass
        if not events_html:
            events_html = '<tr><td colspan="5" style="color:#94a3b8;">No audit events recorded yet.</td></tr>'

        alerts_html = ""
        if drifts:
            alerts_html += "<div class='alert alert-danger'><h3>CI Anti-Drift Violations Detected:</h3><ul>"
            alerts_html += "".join(f"<li>{html.escape(d)}</li>" for d in drifts)
            alerts_html += "</ul></div>"
        else:
            alerts_html += "<div class='alert alert-success'><strong>[PASS] Anti-Drift Gate:</strong> All LLD modules and entity stubs are synchronized with <code>src/</code>.</div>"

        if violations:
            alerts_html += "<div class='alert alert-danger'><h3>Semantic Cross-Layer Rule Violations:</h3><ul>"
            alerts_html += "".join(f"<li>{html.escape(v)}</li>" for v in violations)
            alerts_html += "</ul></div>"
        if next_action:
            alerts_html += f"<div class='alert' style='background:#0f2942;border:1px solid #0284c7;color:#bae6fd;'><strong>Next Step:</strong> {html.escape(next_action)}</div>"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GenOps Pipeline Executive Audit Dashboard</title>
    <!-- GenOps Specification Pipeline & Audit Dashboard -->
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f8fafc; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1, h2, h3 {{ color: #38bdf8; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
        .kpi-val {{ font-size: 28px; font-weight: 700; color: #f8fafc; }}
        .kpi-lbl {{ font-size: 12px; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }}
        .card {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
        .table-responsive {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #334155; font-size: 14px; }}
        th {{ background: #0f172a; color: #cbd5e1; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
        .badge-green {{ background: #065f46; color: #34d399; }}
        .badge-amber {{ background: #78350f; color: #fbbf24; }}
        .badge-red {{ background: #7f1d1d; color: #fecaca; }}
        .badge-slate {{ background: #334155; color: #e2e8f0; }}
        .alert {{ padding: 14px 18px; border-radius: 6px; margin-bottom: 16px; }}
        .alert-success {{ background: #064e3b; border: 1px solid #059669; color: #a7f3d0; }}
        .alert-danger {{ background: #7f1d1d; border: 1px solid #dc2626; color: #fecaca; }}
        code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; }}
        @media print {{
            body {{ background: #ffffff; color: #0f172a; padding: 0; }}
            .card, .kpi {{ background: #ffffff; border-color: #cbd5e1; }}
            h1, h2, h3 {{ color: #0f172a; }}
            th {{ background: #f1f5f9; color: #0f172a; }}
            td, th {{ border-bottom-color: #cbd5e1; }}
            code {{ background: #f1f5f9; color: #0f172a; }}
            .kpi-val {{ color: #0f172a; }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <h1>GenOps Specification Pipeline &amp; Audit Dashboard</h1>
        <p style="color: #94a3b8;">Generated on: {utc_now_iso()} | Engine: v{__version__} | State Schema: v2.0 (LF-Normalized SHA-256)</p>

        <section class="kpi-grid" aria-label="Pipeline Summary Metrics">
            <div class="kpi"><div class="kpi-val">{approved_count}/{len(stage_items)}</div><div class="kpi-lbl">Stages Approved</div></div>
            <div class="kpi"><div class="kpi-val">{len(specs)}</div><div class="kpi-lbl">Indexed Specs</div></div>
            <div class="kpi"><div class="kpi-val">{len(rtm_rows)}</div><div class="kpi-lbl">Traced Requirements</div></div>
            <div class="kpi"><div class="kpi-val">{rtm_cov_pct}%</div><div class="kpi-lbl">RTM Coverage ({traced_reqs}/{len(rtm_rows)})</div></div>
            <div class="kpi"><div class="kpi-val">{len(drifts) + len(violations)}</div><div class="kpi-lbl">Gate Issues</div></div>
        </section>

        {alerts_html}

        <section class="card">
            <h2>1. Pipeline Stage Governance Health</h2>
            <div class="table-responsive">
            <table aria-label="Pipeline Stage Governance Health">
                <thead>
                    <tr>
                        <th scope="col">Stage</th>
                        <th scope="col">State</th>
                        <th scope="col">Last Execution</th>
                        <th scope="col">Live Output Hash</th>
                        <th scope="col">Artifacts</th>
                    </tr>
                </thead>
                <tbody>
                    {stages_html}
                </tbody>
            </table>
            </div>
        </section>

        <section class="card">
            <h2>2. Specification Document Registry ({len(specs)} Indexed Documents)</h2>
            <div class="table-responsive">
            <table aria-label="Specification Document Registry">
                <thead>
                    <tr>
                        <th scope="col">Stage</th>
                        <th scope="col">Document ID</th>
                        <th scope="col">File Location</th>
                        <th scope="col">Status</th>
                        <th scope="col">Upstream Dependencies</th>
                        <th scope="col">Downstream Dependents</th>
                    </tr>
                </thead>
                <tbody>
                    {specs_html}
                </tbody>
            </table>
            </div>
        </section>

        <section class="card">
            <h2>3. Requirements Traceability Matrix ({len(rtm_rows)} Requirements)</h2>
            <div class="table-responsive">
            <table aria-label="Requirements Traceability Matrix">
                <thead>
                    <tr>
                        <th scope="col">Requirement</th>
                        <th scope="col">PRD</th>
                        <th scope="col">Priority</th>
                        <th scope="col">Downstream Lineage</th>
                    </tr>
                </thead>
                <tbody>
                    {rtm_html}
                </tbody>
            </table>
            </div>
        </section>

        <section class="card">
            <h2>4. Immutable Audit Event Trail (Latest Events)</h2>
            <div class="table-responsive">
            <table aria-label="Audit Event Trail">
                <thead>
                    <tr>
                        <th scope="col">Timestamp (UTC)</th>
                        <th scope="col">Action</th>
                        <th scope="col">Stage</th>
                        <th scope="col">Actor</th>
                        <th scope="col">Event Hash</th>
                    </tr>
                </thead>
                <tbody>
                    {events_html}
                </tbody>
            </table>
            </div>
        </section>
    </main>
</body>
</html>
"""
        _atomic_write_text(output_file, html_content)


class BrownfieldIngestionService:
    """Reverse engineers brownfield codebases and produces baseline LLD specifications."""

    _SOURCE_EXTS = {".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".rs", ".java"}
    _IGNORED_STEMS = {
        "main", "app", "index", "init", "__init__", "mod", "lib",
        "deps", "container", "errors", "exceptions", "ports", "interfaces",
    }
    _IGNORED_SUFFIXES = ("_router", "_controller", "_service", "_repository", "_handler", "_test", ".test", ".spec")
    _LAYER_DIR_NAMES = {
        "app", "domain", "services", "service", "ports", "adapters",
        "controllers", "routers", "handlers", "repositories", "models",
        "schemas", "internal", "cmd", "pkg", "tests", "test",
    }

    @classmethod
    def _extract_entities(cls, files: List[str], fallback: str) -> List[str]:
        """Extract PascalCase domain entity names from source file paths."""
        entities: Set[str] = set()
        for f in files:
            fp = Path(f)
            if fp.suffix.lower() not in cls._SOURCE_EXTS:
                continue
            base = fp.stem
            lower_base = base.lower()
            if lower_base in cls._IGNORED_STEMS or lower_base.startswith("test_") or lower_base.endswith(cls._IGNORED_SUFFIXES):
                continue
            entities.add(base.replace("-", " ").replace("_", " ").title().replace(" ", ""))
        fallback_ent = fallback.replace("-", " ").replace("_", " ").title().replace(" ", "") or "CoreEntity"
        return sorted(list(entities)) or [fallback_ent]

    @classmethod
    def ingest_codebase(
        cls,
        root_dir: Path,
        src_rel_path: str = "src",
        force: bool = False,
        dry_run: bool = False,
    ) -> Tuple[Path, int]:
        src_path = root_dir / src_rel_path
        if not ScaffoldingService.is_safe_subpath(src_path, root_dir):
            raise ValueError(f"Path traversal detected in source directory: {src_rel_path}")
        if not src_path.exists():
            raise FileNotFoundError(f"Source directory '{src_rel_path}' not found.")

        top_dirs = [
            item for item in sorted(src_path.iterdir())
            if item.is_dir() and not item.name.startswith(".") and not DeterministicHasher._should_skip(item, src_path)
        ]

        modules: Dict[str, Dict[str, Any]] = {}
        is_single_service_layers = (len(top_dirs) >= 2 and all(d.name.lower() in cls._LAYER_DIR_NAMES for d in top_dirs))
        if is_single_service_layers or not top_dirs:
            files = [
                p.relative_to(src_path).as_posix()
                for p in sorted(src_path.rglob("*"))
                if p.is_file() and not DeterministicHasher._should_skip(p, src_path)
            ]
            if files:
                m_name = re.sub(r"[^a-z0-9-]+", "-", root_dir.name.lower()).strip("-") or "core"
                modules[m_name] = {
                    "files_count": len(files),
                    "entities": cls._extract_entities(files, m_name),
                }
        else:
            for item in top_dirs:
                m_name = item.name
                files = [
                    p.relative_to(item).as_posix()
                    for p in sorted(item.rglob("*"))
                    if p.is_file() and not DeterministicHasher._should_skip(p, item)
                ]
                modules[m_name] = {
                    "files_count": len(files),
                    "entities": cls._extract_entities(files, m_name),
                }

        table_rows = []
        for m_name, info in modules.items():
            ents_str = ", ".join(info["entities"])
            table_rows.append(f"| `{m_name}` | Auto-detected module from `{src_rel_path}/{m_name}` | `{ents_str}` |")

        now_str = utc_now_iso()
        table_content = "\n".join(table_rows) if table_rows else "| `core` | Baseline core module | `CoreEntity` |"

        lld_content = f"""---
id: LLD-001-brownfield-baseline
domain: system-baseline
stage: lld
version: 1.0.0
status: approved
created_at: {now_str}
updated_at: {now_str}
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
        dest_file = root_dir / "docs" / "lld" / "LLD-001-brownfield-baseline.md"
        if dest_file.exists() and not force:
            raise FileExistsError(f"{dest_file.relative_to(root_dir).as_posix()} already exists. Pass --force to overwrite.")
        if not dry_run:
            _atomic_write_text(dest_file, lld_content)

        return dest_file, len(modules)


# ==============================================================================
# Domain VI: State Repository & Lineage Graph Engine
# ==============================================================================

class StateRepository:
    """Encapsulates lock-protected persistence of GenOps State v2.0 and hash-chained audit logs."""

    VALID_RECORD_STATES = {"drafting", "generated", "approved", "skipped"}
    _ZERO_HASH = "0" * 64

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.state_file = root_dir / "docs" / ".genops-state.json"
        self.lock_file = root_dir / "docs" / ".genops.lock"
        self.event_file = root_dir / "docs" / ".genops-events.jsonl"

    @staticmethod
    def _default_state() -> Dict[str, Any]:
        return {"version": "2.0", "pipeline": "genops.yaml", "stages": {}}

    @staticmethod
    def _paths_overlap(out_paths: List[str], req_paths: List[str]) -> bool:
        """Return True if any output directory/file path overlaps a requirement path."""
        norm_outs = [Path(str(p)).as_posix().rstrip("/") for p in out_paths if p]
        norm_reqs = [Path(str(p)).as_posix().rstrip("/") for p in req_paths if p]
        for out_p in norm_outs:
            for req_p in norm_reqs:
                if out_p == req_p or req_p.startswith(f"{out_p}/") or out_p.startswith(f"{req_p}/"):
                    return True
        return False

    def load_state(self) -> Dict[str, Any]:
        """Read state file safely, backing up corrupted JSON rather than silently wiping it."""
        if not self.state_file.exists():
            return self._default_state()
        try:
            with open(self.state_file, "r", encoding="utf-8") as sf:
                data = json.load(sf)
            return data if isinstance(data, dict) else self._default_state()
        except json.JSONDecodeError as e:
            logger.warning("Corrupt state file %s (%s); preserving backup before reset.", self.state_file, e)
            backup = self.state_file.with_suffix(".json.corrupt")
            if not backup.exists():
                try:
                    shutil.copy2(self.state_file, backup)
                except OSError:
                    pass
            return self._default_state()
        except OSError as e:
            logger.warning("Failed to read state file %s: %s", self.state_file, e)
            return self._default_state()

    def _last_event_hash(self) -> str:
        """Return the trailing event_hash from the JSONL audit log via O(1) tail seek, or 64 zeros at genesis."""
        if not self.event_file.is_file():
            return self._ZERO_HASH
        try:
            with open(self.event_file, "rb") as ef:
                ef.seek(0, os.SEEK_END)
                size = ef.tell()
                if size == 0:
                    return self._ZERO_HASH
                chunk_size = min(size, 16384)
                ef.seek(size - chunk_size, os.SEEK_SET)
                tail_text = ef.read(chunk_size).decode("utf-8", errors="replace")
        except OSError:
            return self._ZERO_HASH
        lines = [ln.strip() for ln in tail_text.splitlines() if ln.strip()]
        if not lines:
            return self._ZERO_HASH
        try:
            last_obj = json.loads(lines[-1])
            return str(last_obj.get("event_hash") or self._ZERO_HASH)
        except json.JSONDecodeError:
            return self._ZERO_HASH

    def rotate_events(self, max_events: int = 500, actor: str = "system") -> Dict[str, Any]:
        """Rotate docs/.genops-events.jsonl into docs/.genops-events.archive.jsonl with a cryptographic checkpoint."""
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        archive_file = self.root_dir / "docs" / ".genops-events.archive.jsonl"
        with StateLock(self.lock_file):
            if not self.event_file.is_file():
                return {"rotated": False, "archived_count": 0, "remaining_count": 0}
            raw_lines = [ln.strip() for ln in self.event_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if len(raw_lines) <= max_events:
                return {"rotated": False, "archived_count": 0, "remaining_count": len(raw_lines)}

            cut_idx = len(raw_lines) - max_events
            to_archive = raw_lines[:cut_idx]
            to_keep = raw_lines[cut_idx:]

            archive_file.parent.mkdir(parents=True, exist_ok=True)
            with open(archive_file, "a", encoding="utf-8") as af:
                for ln in to_archive:
                    af.write(ln + "\n")

            archived_last_hash = self._ZERO_HASH
            try:
                archived_last_hash = str(json.loads(to_archive[-1]).get("event_hash") or self._ZERO_HASH)
            except Exception:
                pass
            archive_sha256 = DeterministicHasher.hash_file(archive_file)

            checkpoint: Dict[str, Any] = {
                "timestamp": utc_now_iso(),
                "stage": "pipeline",
                "action": "ROTATION_CHECKPOINT",
                "actor": actor,
                "prev_hash": self._ZERO_HASH,
                "archived_count": len(to_archive),
                "archived_last_hash": archived_last_hash,
                "archive_sha256": archive_sha256,
            }
            chk_canonical = json.dumps(checkpoint, sort_keys=True, separators=(",", ":"))
            checkpoint["event_hash"] = hashlib.sha256(chk_canonical.encode("utf-8")).hexdigest()

            rechained: List[str] = [json.dumps(checkpoint)]
            prev_h = checkpoint["event_hash"]
            for ln in to_keep:
                ev = json.loads(ln)
                ev.pop("event_hash", None)
                ev["prev_hash"] = prev_h
                can = json.dumps(ev, sort_keys=True, separators=(",", ":"))
                ev["event_hash"] = hashlib.sha256(can.encode("utf-8")).hexdigest()
                prev_h = ev["event_hash"]
                rechained.append(json.dumps(ev))

            _atomic_write_text(self.event_file, "\n".join(rechained) + "\n")
            return {
                "rotated": True,
                "archived_count": len(to_archive),
                "remaining_count": len(rechained),
                "archive_file": "docs/.genops-events.archive.jsonl",
                "archive_sha256": archive_sha256,
            }

    def _append_event_unlocked(
        self, action: str, stage: str, actor: str, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Append a hash-chained audit event while caller already holds StateLock."""
        entry: Dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "stage": stage,
            "action": action,
            "actor": actor,
            "prev_hash": self._last_event_hash(),
        }
        commit = _git_head_short(self.root_dir)
        if commit:
            entry["git_commit"] = commit
        if details:
            for k, v in details.items():
                if k not in ("timestamp", "stage", "action", "actor", "prev_hash", "event_hash", "git_commit"):
                    entry[k] = v
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.event_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.event_file, "a", encoding="utf-8") as ef:
            ef.write(json.dumps(entry) + "\n")
        return entry

    def append_event(
        self, action: str, stage: str, actor: str = "user", details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Thread/process-safe append of a hash-chained governance event."""
        with StateLock(self.lock_file):
            return self._append_event_unlocked(action, stage, actor, details)

    def verify_event_chain(self) -> List[str]:
        """Verify JSON syntax and cryptographic hash chaining of docs/.genops-events.jsonl."""
        if not self.event_file.is_file():
            return []
        errors: List[str] = []
        try:
            raw_lines = self.event_file.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            return [f"Could not read event log {self.event_file}: {e}"]

        expected_prev = self._ZERO_HASH
        for lineno, raw in enumerate(raw_lines, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                ev = json.loads(stripped)
            except json.JSONDecodeError as e:
                errors.append(f"docs/.genops-events.jsonl line {lineno}: invalid JSON ({e})")
                continue
            if not isinstance(ev, dict):
                errors.append(f"docs/.genops-events.jsonl line {lineno}: event entry must be a JSON object")
                continue
            if "event_hash" not in ev:
                continue
            recorded_hash = str(ev["event_hash"])
            if ev.get("prev_hash") != expected_prev:
                errors.append(
                    f"docs/.genops-events.jsonl line {lineno}: broken prev_hash "
                    f"(expected {expected_prev[:12]}..., got {str(ev.get('prev_hash', ''))[:12]}...)"
                )
            payload = {k: v for k, v in ev.items() if k != "event_hash"}
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if recomputed != recorded_hash:
                errors.append(
                    f"docs/.genops-events.jsonl line {lineno}: event_hash mismatch "
                    f"(possible tampering; expected {recomputed[:12]}..., got {recorded_hash[:12]}...)"
                )
            expected_prev = recorded_hash
        return errors

    def _collect_stage_outputs(self, stage_conf: Dict[str, Any]) -> Dict[str, str]:
        """Compute deterministic output file hash map without cross-directory key collisions."""
        outputs = [str(p) for p in stage_conf.get("outputs", []) if p]
        multi = len(outputs) > 1
        out_hashes: Dict[str, str] = {}
        for out_p in outputs:
            prefix = Path(out_p).as_posix().rstrip("/")
            target = self.root_dir / out_p
            if target.is_dir():
                _, f_hashes = DeterministicHasher.hash_directory(target)
                for rel, h in f_hashes.items():
                    key = f"{prefix}/{rel}" if multi else rel
                    out_hashes[key] = h
            elif target.is_file() and not DeterministicHasher._should_skip(target, self.root_dir):
                key = prefix if multi else Path(out_p).name
                out_hashes[key] = DeterministicHasher.hash_file(target)
        return out_hashes

    def _promote_frontmatter_status(self, stage_conf: Dict[str, Any], stage_id: str) -> None:
        """Promote frontmatter `status: draft` to approved/accepted before computing final hashes."""
        target_status = "accepted" if stage_id == "adr" else "approved"
        now_iso = utc_now_iso()
        status_re = re.compile(r'^(status:[ \t]*)["\']?draft["\']?([ \t]*(?:#.*)?)$', re.IGNORECASE | re.MULTILINE)
        updated_re = re.compile(r"^(updated_at:[ \t]*).*$", re.MULTILINE)

        candidates: List[Path] = []
        for out_p in stage_conf.get("outputs", []):
            target = self.root_dir / str(out_p)
            if target.is_dir():
                candidates.extend(
                    p for p in sorted(target.rglob("*.md"))
                    if p.is_file()
                    and not DeterministicHasher._should_skip(p, target)
                    and p.parent.name.lower() not in MarkdownParser.NON_SPEC_DIRS
                )
            elif target.is_file() and target.suffix.lower() == ".md":
                candidates.append(target)

        for md_path in candidates:
            try:
                content = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            match = MarkdownParser._FM_BLOCK_RE.match(content)
            if not match:
                continue
            fm_block = match.group(1)
            new_fm, count = status_re.subn(rf"\g<1>{target_status}\g<2>", fm_block)
            if count == 0:
                continue
            new_fm = updated_re.sub(rf"\g<1>{now_iso}", new_fm)
            updated_content = f"---\n{new_fm}---\n" + content[match.end():]
            if updated_content != content:
                _atomic_write_text(md_path, updated_content)

    def _build_stage_dependencies(self, stage_conf: Dict[str, Any]) -> Dict[str, List[str]]:
        """Map each spec file produced by *stage_conf* to its resolved upstream spec paths."""
        specs = MarkdownParser.collect_specs(self.root_dir)
        id_to_path = {s.id: s.path for s in specs}
        out_prefixes = [Path(str(p)).as_posix().rstrip("/") for p in stage_conf.get("outputs", []) if p]
        deps: Dict[str, List[str]] = {}
        for s in specs:
            in_stage = any(s.path == op or s.path.startswith(f"{op}/") for op in out_prefixes)
            if not in_stage or not s.upstream_refs:
                continue
            resolved = sorted({id_to_path[u] for u in s.upstream_refs if u in id_to_path})
            if resolved:
                deps[s.path] = resolved
        return deps

    @staticmethod
    def _scan_output_placeholders(root_dir: Path, stage_conf: Dict[str, Any]) -> List[str]:
        """Scan stage markdown outputs (outside fenced code blocks) for unresolved TODO/TBD or template tokens."""
        issues: List[str] = []
        todo_re = re.compile(r"(?:^|\s)(?:TODO|TBD|FIXME)(?:\s*:|\b)", re.IGNORECASE)
        token_re = re.compile(r"\{(?:Domain|NNN|slug|YYYY-MM-DDTHH:MM:SSZ)\}")

        candidates: List[Path] = []
        for out_p in stage_conf.get("outputs", []):
            target = root_dir / str(out_p)
            if target.is_dir():
                candidates.extend(
                    p for p in sorted(target.rglob("*.md"))
                    if p.is_file()
                    and not DeterministicHasher._should_skip(p, target)
                    and p.parent.name.lower() not in MarkdownParser.NON_SPEC_DIRS
                )
            elif target.is_file() and target.suffix.lower() == ".md":
                candidates.append(target)

        for md_path in candidates:
            try:
                text = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            rel = md_path.relative_to(root_dir).as_posix() if root_dir in md_path.parents else md_path.name
            in_fence = False
            fence_marker = ""
            for lineno, raw_ln in enumerate(text.splitlines(), start=1):
                s = raw_ln.strip()
                if s.startswith(("```", "~~~")):
                    mk = s[:3]
                    if not in_fence:
                        in_fence = True
                        fence_marker = mk
                    elif mk == fence_marker:
                        in_fence = False
                        fence_marker = ""
                    continue
                if in_fence:
                    continue
                if todo_re.search(s):
                    issues.append(f"{rel}:{lineno} contains unresolved placeholder ('{s[:60]}')")
                elif token_re.search(s):
                    issues.append(f"{rel}:{lineno} contains unexpanded template token ('{s[:60]}')")
        return issues

    def record_stage(
        self, stage_id: str, actor: str = "user", state: str = "approved", force: bool = False
    ) -> Dict[str, Any]:
        """Atomically record stage lifecycle state, hashes, dependencies, and hash-chained audit event."""
        if state not in self.VALID_RECORD_STATES:
            raise ValueError(
                f"Invalid state '{state}'. Expected one of: {', '.join(sorted(self.VALID_RECORD_STATES))}."
            )
        config_file = self.root_dir / "genops.yaml"
        if not config_file.exists():
            raise FileNotFoundError("genops.yaml not found.")

        cfg = ConfigManager.load_yaml(config_file)
        stages = cfg.get("pipeline", {}).get("stages", [])
        stage_conf = next((s for s in stages if s.get("id") == stage_id), None)
        if not stage_conf:
            valid_ids = ", ".join(str(s.get("id", "")) for s in stages if s.get("id"))
            raise ValueError(f"Stage '{stage_id}' not found in genops.yaml. Valid stages: {valid_ids}.")

        now_iso = utc_now_iso()

        with StateLock(self.lock_file):
            if state == "approved":
                self._promote_frontmatter_status(stage_conf, stage_id)

            out_hashes = self._collect_stage_outputs(stage_conf)
            if state in ("approved", "generated") and not out_hashes:
                raise ValueError(
                    f"Cannot record '{state}' for stage '{stage_id}': no output files found in {stage_conf.get('outputs', [])}."
                )

            reqs_list = stage_conf.get("requires", [])
            req_hash, _ = DeterministicHasher.hash_requirements(reqs_list, self.root_dir)
            if state == "approved" and not force:
                if reqs_list and not req_hash:
                    raise ValueError(
                        f"Cannot approve stage '{stage_id}': required upstream prerequisites in {reqs_list} are missing or empty. "
                        "Complete and approve upstream stages first (or pass --force to override)."
                    )
                placeholder_issues = self._scan_output_placeholders(self.root_dir, stage_conf)
                if placeholder_issues:
                    raise ValueError(
                        f"Cannot approve stage '{stage_id}': unresolved placeholders found: {'; '.join(placeholder_issues[:3])} "
                        "(resolve placeholders or pass --force)."
                    )
            combined_root = MerkleTree.compute_root(out_hashes)
            dependencies = self._build_stage_dependencies(stage_conf)

            state_data = self.load_state()
            state_data["version"] = "2.0"
            state_data["updated_at"] = now_iso
            stages_state = state_data.setdefault("stages", {})
            prev_combined = str(stages_state.get(stage_id, {}).get("combined_hash", ""))

            stages_state[stage_id] = {
                "state": state,
                "last_run": now_iso,
                "requires_hash": req_hash,
                "output_dir": stage_conf.get("outputs", [""])[0] if stage_conf.get("outputs") else "",
                "file_count": len(out_hashes),
                "files": out_hashes,
                "combined_hash": combined_root,
                "dependencies": dependencies,
                "approved_by": actor,
            }

            # Transitive selective invalidation across both explicit `next` and outputs->requires edges
            invalidated: List[str] = []
            if combined_root != prev_combined:
                adj: Dict[str, List[str]] = {str(s.get("id", "")): list(s.get("next", [])) for s in stages}
                for src_st in stages:
                    src_id = str(src_st.get("id", ""))
                    src_outs = [str(x) for x in src_st.get("outputs", [])]
                    for dst_st in stages:
                        dst_id = str(dst_st.get("id", ""))
                        if dst_id == src_id or dst_id in adj.get(src_id, []):
                            continue
                        if self._paths_overlap(src_outs, [str(x) for x in dst_st.get("requires", [])]):
                            adj.setdefault(src_id, []).append(dst_id)

                queue = list(adj.get(stage_id, []))
                visited: Set[str] = {stage_id}
                while queue:
                    nxt_id = queue.pop(0)
                    if nxt_id in visited:
                        continue
                    visited.add(nxt_id)
                    if nxt_id in stages_state and stages_state[nxt_id].get("state") in ("approved", "generated"):
                        stages_state[nxt_id]["state"] = "stale"
                        invalidated.append(nxt_id)
                    queue.extend(adj.get(nxt_id, []))

            _atomic_write_text(self.state_file, json.dumps(state_data, indent=2) + "\n")

            self._append_event_unlocked(
                action=state.upper(),
                stage=stage_id,
                actor=actor,
                details={
                    "files_count": len(out_hashes),
                    "requires_hash": req_hash,
                    "output_hash": combined_root,
                    "files": out_hashes,
                },
            )
            if invalidated:
                self._append_event_unlocked(
                    action="STALE_INVALIDATED",
                    stage=stage_id,
                    actor=actor,
                    details={"invalidated_stages": invalidated},
                )

            ContextCompactor.compact(self.root_dir)
            return {
                "stage": stage_id,
                "state": state,
                "file_count": len(out_hashes),
                "combined_hash": combined_root,
                "invalidated": invalidated,
            }

    @staticmethod
    def _diff_file_maps(baseline: Dict[str, str], live: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
        """Return sorted (added, modified, removed) paths between two {rel_path: sha256} maps."""
        added = sorted(k for k in live if k not in baseline)
        modified = sorted(k for k in live if k in baseline and live[k] != baseline[k])
        removed = sorted(k for k in baseline if k not in live)
        return added, modified, removed

    @staticmethod
    def _domains_for_paths(rel_paths: List[str], specs: List[SpecDocument]) -> List[str]:
        """Extract unique domain/module slugs affected by changed file paths."""
        path_to_domain = {s.path: s.domain for s in specs if s.domain}
        domains: Set[str] = set()
        for rp in rel_paths:
            if rp in path_to_domain:
                domains.add(path_to_domain[rp])
                continue
            m = re.match(r"^[A-Za-z]+-\d+-([a-z0-9-]+)\.md$", Path(rp).name, re.IGNORECASE)
            if m:
                domains.add(m.group(1).lower())
            elif rp.startswith("src/") and len(Path(rp).parts) >= 2:
                domains.add(Path(rp).parts[1])
        return sorted(domains)

    def _upstream_baseline_files(
        self, reqs: List[str], stages: List[Dict[str, Any]], st_map: Dict[str, Any]
    ) -> Dict[str, str]:
        """Reconstruct expected requirement-file hashes from recorded upstream stages."""
        baseline: Dict[str, str] = {}
        for up_st in stages:
            up_id = str(up_st.get("id", ""))
            up_outs = [str(x) for x in up_st.get("outputs", [])]
            if up_id not in st_map or not self._paths_overlap(up_outs, reqs):
                continue
            up_files = st_map[up_id].get("files", {})
            if not isinstance(up_files, dict):
                continue
            if len(up_outs) == 1:
                prefix = Path(up_outs[0]).as_posix().rstrip("/")
                is_dir = (self.root_dir / up_outs[0]).is_dir() or up_outs[0].endswith("/")
                for rel, h in up_files.items():
                    full_key = f"{prefix}/{rel}" if is_dir and not rel.startswith(f"{prefix}/") else (prefix if not is_dir else rel)
                    baseline[full_key] = str(h)
            else:
                for rel, h in up_files.items():
                    baseline[rel] = str(h)
        return baseline

    def compute_live_status(self, domain_filter: Optional[str] = None) -> Dict[str, Any]:
        """Compute live cryptographic pipeline status, per-file/domain drift attribution, and next action."""
        config_file = self.root_dir / "genops.yaml"
        if not config_file.exists():
            raise FileNotFoundError("genops.yaml not found.")

        cfg = ConfigManager.load_yaml(config_file)
        pipeline = cfg.get("pipeline", {})
        stages = pipeline.get("stages", [])
        state_data = self.load_state()
        st_map = state_data.get("stages", {})
        specs = MarkdownParser.collect_specs(self.root_dir)

        next_map: Dict[str, List[str]] = {str(stg.get("id", "")): list(stg.get("next", [])) for stg in stages}
        for src_st in stages:
            src_id = str(src_st.get("id", ""))
            for dst_st in stages:
                dst_id = str(dst_st.get("id", ""))
                if dst_id != src_id and dst_id not in next_map.get(src_id, []):
                    if self._paths_overlap([str(x) for x in src_st.get("outputs", [])], [str(x) for x in dst_st.get("requires", [])]):
                        next_map.setdefault(src_id, []).append(dst_id)

        issues: List[str] = []
        stages_out: Dict[str, Dict[str, Any]] = {}

        for stg in stages:
            sid = str(stg.get("id", ""))
            recorded = st_map.get(sid, {}) if isinstance(st_map.get(sid), dict) else {}
            recorded_state = str(recorded.get("state", "absent"))
            st_state = recorded_state
            last_run = str(recorded.get("last_run", "Never"))[:19]
            reqs = [str(r) for r in stg.get("requires", [])]

            live_out_files = self._collect_stage_outputs(stg)
            live_out_hash = MerkleTree.compute_root(live_out_files)
            stored_out_hash = str(recorded.get("combined_hash", ""))

            upstream_status = "N/A" if not reqs else "consistent"
            downstream_status = "consistent"
            live_req_hash = ""
            live_req_files: Dict[str, str] = {}
            stored_req_hash = str(recorded.get("requires_hash", ""))
            changed_files: Dict[str, List[str]] = {"added": [], "modified": [], "removed": []}
            affected_domains: List[str] = []

            # 1. Check upstream requirements drift
            if reqs:
                live_req_hash, live_req_files = DeterministicHasher.hash_requirements(reqs, self.root_dir)
                if not live_req_hash:
                    upstream_status = "blocked"
                elif stored_req_hash and live_req_hash != stored_req_hash:
                    upstream_status = "changed"
                    st_state = "stale"
                    downstream_status = "at-risk"
                    baseline = self._upstream_baseline_files(reqs, stages, st_map)
                    if baseline:
                        added, mod, rem = self._diff_file_maps(baseline, live_req_files)
                    else:
                        added, mod, rem = [], [], []
                    changed_files = {"added": added, "modified": mod, "removed": rem}
                    all_changed = added + mod + rem
                    affected_domains = self._domains_for_paths(all_changed, specs)
                    detail_parts = []
                    if added:
                        detail_parts.append(f"+ added: {', '.join(added)}")
                    if mod:
                        detail_parts.append(f"~ modified: {', '.join(mod)}")
                    if rem:
                        detail_parts.append(f"- removed: {', '.join(rem)}")
                    detail_str = f" ({'; '.join(detail_parts)})" if detail_parts else ""
                    dom_str = f" -> affected domain(s): {', '.join(affected_domains)}" if affected_domains else ""
                    issues.append(f"Stage '{sid}': upstream dependencies changed{detail_str}{dom_str}")
                elif not stored_req_hash:
                    upstream_status = "pending"

            # 2. Check own output drift (unrecorded edits/additions/deletions after approval)
            if recorded and st_state in ("approved", "generated") and stored_out_hash and live_out_hash != stored_out_hash:
                stored_files = recorded.get("files", {}) if isinstance(recorded.get("files"), dict) else {}
                out_added, out_mod, out_rem = self._diff_file_maps(stored_files, live_out_files)
                prefix = Path(str(stg.get("outputs", [""])[0])).as_posix().rstrip("/") if len(stg.get("outputs", [])) == 1 else ""
                qual = lambda p: f"{prefix}/{p}" if prefix and not p.startswith(f"{prefix}/") else p
                q_added = [qual(p) for p in out_added]
                q_mod = [qual(p) for p in out_mod]
                q_rem = [qual(p) for p in out_rem]
                changed_files["added"] = sorted(set(changed_files["added"] + q_added))
                changed_files["modified"] = sorted(set(changed_files["modified"] + q_mod))
                changed_files["removed"] = sorted(set(changed_files["removed"] + q_rem))
                out_domains = self._domains_for_paths(q_added + q_mod + q_rem, specs)
                affected_domains = sorted(set(affected_domains + out_domains))
                st_state = "stale"
                downstream_status = "at-risk"
                out_parts = []
                if q_added:
                    out_parts.append(f"+ added: {', '.join(q_added)}")
                if q_mod:
                    out_parts.append(f"~ modified: {', '.join(q_mod)}")
                if q_rem:
                    out_parts.append(f"- removed: {', '.join(q_rem)}")
                issues.append(f"Stage '{sid}': unrecorded output edits detected ({'; '.join(out_parts)}). Run 'genops record {sid}'.")

            if st_state == "absent":
                downstream_status = "blocked"

            stages_out[sid] = {
                "state": st_state,
                "recorded_state": recorded_state,
                "last_run": last_run,
                "upstream_status": upstream_status,
                "downstream_status": downstream_status,
                "file_count": len(live_out_files) if recorded or live_out_files else 0,
                "live_requires_hash": live_req_hash,
                "stored_requires_hash": stored_req_hash,
                "live_output_hash": live_out_hash,
                "stored_output_hash": stored_out_hash,
                "changed_files": changed_files,
                "affected_domains": affected_domains,
            }

        # 3. Propagate staleness/absence transitively downstream
        changed = True
        while changed:
            changed = False
            for stg in stages:
                sid = str(stg.get("id", ""))
                if stages_out[sid]["state"] in ("stale", "absent"):
                    for nxt in next_map.get(sid, []):
                        if nxt in stages_out and stages_out[nxt]["state"] in ("approved", "generated"):
                            stages_out[nxt]["state"] = "stale"
                            stages_out[nxt]["downstream_status"] = "at-risk"
                            issues.append(
                                f"Stage '{nxt}': transitively affected by {stages_out[sid]['state']} upstream '{sid}'. Regenerate the chain."
                            )
                            changed = True

        # 4. Synthesize deterministic Recommended Next Action
        stage_ids = [str(s.get("id", "")) for s in stages if s.get("id")]
        next_action = "Pipeline configuration has no stages."
        if stage_ids:
            live_states = [stages_out[sid]["state"] for sid in stage_ids]
            if all(s == "absent" for s in live_states):
                demo_hint = " (or run 'genops demo' to preview an end-to-end scaffold)." if "code" in stage_ids else "."
                next_action = (
                    f"Pipeline has not started yet. Prompt your AI agent with '/genops-{stage_ids[0]}'{demo_hint}"
                )
            elif "stale" in live_states:
                first_stale = next(sid for sid in stage_ids if stages_out[sid]["state"] == "stale")
                next_action = (
                    f"Stage '{first_stale}' is stale or modified. Review changes and run '/genops-{first_stale}' "
                    f"(or 'genops record {first_stale}' if already approved) to synchronize downstream stages."
                )
            elif any(s in ("drafting", "generated") for s in live_states):
                first_wip = next(sid for sid in stage_ids if stages_out[sid]["state"] in ("drafting", "generated"))
                wip_state = stages_out[first_wip]["state"]
                next_action = f"Stage '{first_wip}' is '{wip_state}'. Complete review and run 'genops record {first_wip}'."
            elif "absent" in live_states:
                first_absent = next(sid for sid in stage_ids if stages_out[sid]["state"] == "absent")
                next_action = f"Prompt your AI agent with '/genops-{first_absent}' to continue the specification cascade."
            else:
                next_action = "Pipeline 100% synchronized and approved. Run 'genops doctor' or 'genops report' to export audit artifacts."

        result: Dict[str, Any] = {
            "pipeline_name": pipeline.get("name", "Software Specification Pipeline"),
            "timestamp": utc_now_iso(),
            "stages": stages_out,
            "issues": issues,
            "next_action": next_action,
        }
        if domain_filter:
            dom_specs = LineageGraphService.slice_domain_context(specs, domain_filter)
            result["domain_filter"] = domain_filter
            result["domain_specs"] = [
                {"id": s.id, "stage": s.stage, "domain": s.domain, "status": s.status, "path": s.path}
                for s in dom_specs
            ]
        return result


class LineageGraphService:
    """Constructs, validates, slices, and renders the specification Directed Acyclic Graph (DAG)."""

    _ALLOWED_STATUSES = {"draft", "approved", "accepted", "deprecated", "superseded", "rejected"}
    _SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
    _STAGE_ORDER = {
        "prd": 0, "brief": 0, "lit-review": 0,
        "hld": 1, "wireframes": 1, "hypothesis": 1,
        "adr": 2, "mockups": 2, "experiment": 2,
        "lld": 3, "prototype": 3, "report": 3,
        "code": 4,
    }

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
            "generated_at": utc_now_iso(),
            "total_documents": len(specs),
            "nodes": nodes,
            "edges": [{"from": e[0], "to": e[1]} for e in unique_edges],
        }

    _VALID_MERMAID_TYPES = {
        "flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2",
        "classDiagram", "erDiagram", "xychart-beta", "C4Context", "C4Container",
        "C4Component", "C4Dynamic", "C4Deployment", "gantt", "pie", "mindmap", "timeline",
    }
    _TODO_BODY_RE = re.compile(r"(?:^|\s)(?:TODO|TBD|FIXME)(?:\s*:|\b)")
    _UNEXPANDED_TOKEN_RE = re.compile(r"\{(?:Domain|NNN|slug|YYYY-MM-DDTHH:MM:SSZ)\}")

    @classmethod
    def _lint_spec_body(cls, spec: SpecDocument) -> List[str]:
        """Inspect spec body for unresolved TODO/TBD/template tokens (outside fences) and invalid Mermaid headers."""
        issues: List[str] = []
        in_fence = False
        fence_marker = ""
        fence_lang = ""
        checked_mermaid_first_line = False

        for lineno, raw_ln in enumerate(spec.body.splitlines(), start=1):
            s = raw_ln.strip()
            if s.startswith(("```", "~~~")):
                mk = s[:3]
                if not in_fence:
                    in_fence = True
                    fence_marker = mk
                    fence_lang = s[3:].strip().lower()
                    checked_mermaid_first_line = False
                elif mk == fence_marker:
                    in_fence = False
                    fence_marker = ""
                    fence_lang = ""
                continue

            if in_fence:
                if fence_lang == "mermaid" and not checked_mermaid_first_line:
                    if not s or s.startswith("%%"):
                        continue
                    checked_mermaid_first_line = True
                    first_tok = s.split()[0].rstrip(";")
                    if first_tok not in cls._VALID_MERMAID_TYPES:
                        issues.append(
                            f"[{spec.path}:{lineno}] Invalid Mermaid diagram type '{first_tok}' "
                            f"(expected one of: flowchart, graph, sequenceDiagram, stateDiagram-v2, classDiagram, erDiagram)"
                        )
                continue

            if cls._TODO_BODY_RE.search(s):
                issues.append(f"[{spec.path}:{lineno}] Unresolved placeholder marker in specification body: '{s[:60]}'")
            elif cls._UNEXPANDED_TOKEN_RE.search(s):
                issues.append(f"[{spec.path}:{lineno}] Unexpanded template token in specification body: '{s[:60]}'")
        return issues

    @classmethod
    def check_rules(cls, specs: List[SpecDocument], root_dir: Optional[Path] = None) -> List[str]:
        """Verify cross-layer semantic validation rules, duplicates, versions, federation, content quality, and stage linkage."""
        violations: List[str] = []
        id_counts: Dict[str, List[str]] = {}
        for s in specs:
            id_counts.setdefault(s.id, []).append(s.path)
        for sid, paths in sorted(id_counts.items()):
            if len(paths) > 1:
                violations.append(f"Duplicate specification id '{sid}' declared in: {', '.join(paths)}")

        spec_ids = set(id_counts.keys())
        id_to_stage = {s.id: s.stage for s in specs}

        cfg: Dict[str, Any] = {}
        if root_dir is not None and (root_dir / "genops.yaml").is_file():
            try:
                cfg = ConfigManager.load_yaml(root_dir / "genops.yaml")
            except Exception:
                cfg = {}
            ext_ids, ext_stages, fed_errors = FederationService.resolve_external_refs(
                root_dir, cfg, MarkdownParser, DeterministicHasher
            )
            violations.extend(fed_errors)
            spec_ids |= ext_ids
            id_to_stage.update(ext_stages)

        for s in specs:
            fm = s.frontmatter
            for rk in ["id", "stage", "status"]:
                if rk not in fm:
                    violations.append(f"[{s.path}] Missing required frontmatter key: '{rk}'")

            if "status" in fm and s.status.lower() not in cls._ALLOWED_STATUSES:
                violations.append(
                    f"[{s.path}] Invalid status '{s.status}' (expected one of: {', '.join(sorted(cls._ALLOWED_STATUSES))})"
                )

            if "version" in fm:
                ver = str(fm["version"]).strip()
                if not cls._SEMVER_RE.match(ver):
                    violations.append(f"[{s.path}] Invalid SemVer 2.0.0 version '{ver}'")

            for up in s.upstream_refs:
                if up not in spec_ids:
                    violations.append(f"[{s.path}] Broken upstream_ref: '{up}' not found in docs/")

            for down in s.downstream_refs:
                if down not in spec_ids:
                    violations.append(f"[{s.path}] Broken downstream_ref: '{down}' not found in docs/")

            if s.stage == "adr":
                adr_st = s.status.lower()
                if adr_st in ("rejected", "deprecated", "superseded") and s.downstream_refs:
                    violations.append(f"[{s.path}] {s.status} ADR has active downstream references: {s.downstream_refs}")

            violations.extend(cls._lint_spec_body(s))

        # Evaluate pipeline stage prerequisite linkage & Needs-ADR resolution when genops.yaml exists
        if root_dir is not None and cfg:
            stages = cfg.get("pipeline", {}).get("stages", [])

            out_dir_to_stage: Dict[str, str] = {}
            stage_specs: Dict[str, List[SpecDocument]] = {}
            for s in specs:
                stage_specs.setdefault(s.stage, []).append(s)
            for stg in stages:
                sid = str(stg.get("id", ""))
                for op in stg.get("outputs", []):
                    norm_op = Path(str(op)).as_posix().rstrip("/")
                    if norm_op:
                        out_dir_to_stage[norm_op] = sid

            for stg in stages:
                sid = str(stg.get("id", ""))
                req_stages: List[str] = []
                for req in stg.get("requires", []):
                    norm_r = Path(str(req)).as_posix().rstrip("/")
                    if norm_r in out_dir_to_stage and out_dir_to_stage[norm_r] not in req_stages:
                        req_stages.append(out_dir_to_stage[norm_r])
                for s in stage_specs.get(sid, []):
                    if s.id == "LLD-001-brownfield-baseline":
                        continue
                    up_stages = {id_to_stage.get(u, "") for u in s.upstream_refs}
                    for req_sid in req_stages:
                        if req_sid not in up_stages:
                            violations.append(
                                f"[{s.path}] Stage '{sid}' requires upstream stage '{req_sid}' per genops.yaml, "
                                f"but upstream_refs omits any '{req_sid}' document"
                            )

            if stage_specs.get("adr"):
                accepted_adrs = [a for a in stage_specs["adr"] if a.status.lower() in ("accepted", "approved")]
                for hld_spec in stage_specs.get("hld", []):
                    needs_adr_topics: List[str] = []
                    for tbl in MarkdownTable.parse_tables(hld_spec.body):
                        for row in tbl:
                            row_status = str(row.get("Status") or row.get("Decision Status") or "").strip().lower()
                            if row_status == "needs adr":
                                needs_adr_topics.append(
                                    str(row.get("Topic") or row.get("Concern") or row.get("Component") or "Item").strip()
                                )
                    if needs_adr_topics:
                        resolved = any(
                            hld_spec.id in a.upstream_refs or a.id in hld_spec.downstream_refs
                            for a in accepted_adrs
                        )
                        if not resolved:
                            violations.append(
                                f"[{hld_spec.path}] HLD marks '{', '.join(needs_adr_topics)}' as 'Needs ADR' "
                                "without a linked accepted/approved ADR"
                            )

        return violations

    @classmethod
    def get_declared_rules(cls, root_dir: Optional[Path]) -> List[Dict[str, str]]:
        """Extract declarative `pipeline.validation_rules` entries from `genops.yaml`."""
        if root_dir is None or not (root_dir / "genops.yaml").is_file():
            return []
        try:
            cfg = ConfigManager.load_yaml(root_dir / "genops.yaml")
        except Exception:
            return []
        raw_rules = cfg.get("pipeline", {}).get("validation_rules", [])
        if not raw_rules:
            raw_rules = cfg.get("validation", {}).get("rules", [])
        rules: List[Dict[str, str]] = []
        for item in raw_rules:
            if isinstance(item, dict) and item.get("rule"):
                rules.append({
                    "from": str(item.get("from", "")),
                    "to": str(item.get("to", "")),
                    "rule": str(item.get("rule", "")),
                })
        return rules

    @classmethod
    def slice_domain_context(cls, specs: List[SpecDocument], domain: str) -> List[SpecDocument]:
        """Extract exact domain seed specs plus transitive DAG closure ordered by pipeline stage."""
        target = domain.strip().lower()
        if not target:
            return []

        by_id = {s.id: s for s in specs}
        reverse_adj: Dict[str, List[str]] = {}
        forward_adj: Dict[str, List[str]] = {}
        for s in specs:
            for up in s.upstream_refs:
                forward_adj.setdefault(up, []).append(s.id)
                reverse_adj.setdefault(s.id, []).append(up)
            for down in s.downstream_refs:
                forward_adj.setdefault(s.id, []).append(down)
                reverse_adj.setdefault(down, []).append(s.id)

        seeds: List[str] = []
        for s in specs:
            dom = s.domain.lower()
            sid_low = s.id.lower()
            if (
                dom == target
                or sid_low == target
                or sid_low.endswith(f"-{target}")
                or f"-{target}-" in sid_low
            ):
                seeds.append(s.id)

        if not seeds:
            return []

        seed_set = set(seeds)
        visited: Set[str] = set()
        queue: List[str] = list(seeds)
        while queue:
            cur = queue.pop(0)
            if cur in visited or cur not in by_id:
                continue
            visited.add(cur)
            if cur in seed_set:
                neighbors = list(reverse_adj.get(cur, [])) + [
                    nxt for nxt in forward_adj.get(cur, [])
                    if nxt in seed_set or (nxt in by_id and by_id[nxt].stage.lower() == "adr")
                ]
            elif by_id[cur].stage.lower() != "adr":
                neighbors = [
                    nxt for nxt in reverse_adj.get(cur, [])
                    if nxt in seed_set or (nxt in by_id and by_id[nxt].stage.lower() == "adr")
                ]
            else:
                neighbors = []
            for nxt in neighbors:
                if nxt not in visited:
                    queue.append(nxt)

        sliced = [by_id[sid] for sid in visited]
        sliced.sort(key=lambda sp: (cls._STAGE_ORDER.get(sp.stage.lower(), 5), sp.stage.lower(), sp.id))
        return sliced

    @staticmethod
    def format_domain_context(specs: List[SpecDocument], max_chars: int = 60000) -> str:
        """Render a domain context slice within the configured character/token budget."""
        chunks: List[str] = []
        total = 0
        for idx, s in enumerate(specs):
            section = f"## [{s.stage.upper()}] {s.id} ({s.path})\n{s.body.strip()}"
            sep = "\n\n---\n\n" if chunks else ""
            if max_chars > 0 and total + len(sep) + len(section) > max_chars:
                omitted = len(specs) - idx
                chunks.append(
                    f"[Truncated: omitted {omitted} lower-priority spec(s) to stay within {max_chars}-char token budget]"
                )
                break
            chunks.append(section)
            total += len(sep) + len(section)
        return "\n\n---\n\n".join(chunks)


# ==============================================================================
# Domain VII: MCP JSON-RPC 2.0 Stdio Server
# ==============================================================================


def is_genops_project(path: Path) -> bool:
    """Return True if *path* is a GenOps-initialized workspace root (contains genops.yaml)."""
    return (path / "genops.yaml").is_file()


def discover_project_root(start: Path, allow_git_fallback: bool = False) -> Optional[Path]:
    """Walk upward from *start* to the nearest genops.yaml root (or optional .git fallback)."""
    candidates = [start] + list(start.parents)
    for candidate in candidates:
        if is_genops_project(candidate):
            return candidate
    if allow_git_fallback:
        for candidate in candidates:
            if (candidate / ".git").exists():
                return candidate
    return None


class MCPServer:
    """Zero-dependency JSON-RPC 2.0 stdio MCP Server for AI Agent Integration."""

    _READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
    _MUTATE_IDEMPOTENT = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
    _MUTATE_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}

    TOOLS_SPEC = [
        {"name": "genops_validate", "description": "Run full validation across genops.yaml, scaffolds, presets, state, event chain, and agent sync.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_doctor", "description": "Run every governance gate (validate, check-rules, drift, verify) in one shot.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_status", "description": "Compute live cryptographic status, staleness propagation, and next recommended action.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"domain": {"type": "string"}}}, "annotations": _READ_ONLY},
        {"name": "genops_init", "description": "Initialize GenOps instruction blocks, state file, and context memory in the workspace.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"preset": {"type": "string"}, "agent": {"type": "string", "default": "all"}, "force": {"type": "boolean", "default": False}, "dry_run": {"type": "boolean", "default": False}, "clean_template": {"type": "boolean", "default": False}}}, "annotations": _MUTATE_WRITE},
        {"name": "genops_impact", "description": "Simulate change impact blast radius across downstream specs and code modules.", "inputSchema": {"type": "object", "required": ["spec"], "additionalProperties": False, "properties": {"spec": {"type": "string"}}}, "annotations": _READ_ONLY},
        {"name": "genops_hash", "description": "Compute LF-normalized SHA-256 hash for a workspace file or directory.", "inputSchema": {"type": "object", "required": ["target"], "additionalProperties": False, "properties": {"target": {"type": "string"}}}, "annotations": _READ_ONLY},
        {"name": "genops_record", "description": "Record stage approval/lifecycle state and output hashes into state v2.", "inputSchema": {"type": "object", "required": ["stage"], "additionalProperties": False, "properties": {"stage": {"type": "string"}, "actor": {"type": "string", "default": "agent"}, "state": {"type": "string", "enum": ["drafting", "generated", "approved", "skipped"], "default": "approved"}, "force": {"type": "boolean", "default": False}}}, "annotations": _MUTATE_WRITE},
        {"name": "genops_scaffold", "description": "Deterministically scaffold a module from a scaffold template without clobbering existing templates unless forced.", "inputSchema": {"type": "object", "required": ["module", "scaffold"], "additionalProperties": False, "properties": {"module": {"type": "string"}, "scaffold": {"type": "string"}, "entities": {"type": "string"}, "force": {"type": "boolean", "default": False}, "dry_run": {"type": "boolean", "default": False}}}, "annotations": _MUTATE_WRITE},
        {"name": "genops_compact", "description": "Compact active living project memory into .agents/context/CONTEXT.md.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _MUTATE_IDEMPOTENT},
        {"name": "genops_verify", "description": "Execute compiler and linter diagnostics across workspace.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_graph", "description": "Generate specification lineage graph and persist docs/.genops-graph.json.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _MUTATE_IDEMPOTENT},
        {"name": "genops_drift", "description": "Run CI/CD anti-drift check between LLD specifications and source code.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_check_rules", "description": "Run semantic cross-layer validation rules across specifications.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_rtm", "description": "Generate full-chain Requirements Traceability Matrix (RTM).", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}}, "annotations": _READ_ONLY},
        {"name": "genops_context", "description": "Extract stage-ordered DAG lineage slice for a domain within token budget.", "inputSchema": {"type": "object", "required": ["domain"], "additionalProperties": False, "properties": {"domain": {"type": "string"}, "max_chars": {"type": "integer", "minimum": 1000}}}, "annotations": _READ_ONLY},
        {"name": "genops_report", "description": "Generate self-contained executive HTML audit dashboard.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"html": {"type": "string", "default": "docs/report.html"}}}, "annotations": _MUTATE_IDEMPOTENT},
        {"name": "genops_ingest", "description": "Brownfield codebase reverse engineering & baseline LLD spec generator.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"src": {"type": "string", "default": "src"}, "force": {"type": "boolean", "default": False}, "dry_run": {"type": "boolean", "default": False}}}, "annotations": _MUTATE_WRITE},
        {"name": "genops_explain", "description": "Explain stage metadata, required prerequisites, outputs, skill, template, and validation rules.", "inputSchema": {"type": "object", "required": ["stage"], "additionalProperties": False, "properties": {"stage": {"type": "string"}}}, "annotations": _READ_ONLY},
        {"name": "genops_workspace", "description": "Run multi-project workspace status or doctor across all GenOps subprojects in a monorepo.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"action": {"type": "string", "enum": ["status", "doctor"], "default": "status"}}}, "annotations": _READ_ONLY},
        {"name": "genops_rotate_events", "description": "Rotate docs/.genops-events.jsonl into an archive file with a cryptographic checkpoint.", "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"max_events": {"type": "integer", "minimum": 1, "default": 500}}}, "annotations": _MUTATE_WRITE},
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        self._explicit_root: Optional[Path] = root_dir.resolve() if root_dir is not None else None
        self.root_dir: Path = self._explicit_root or Path.cwd().resolve()
        self.state_repo = StateRepository(self.root_dir)
        self.client_roots: List[Path] = []
        self._tools_by_name = {t["name"]: t for t in self.TOOLS_SPEC}

    @staticmethod
    def _uri_to_path(uri: str) -> Optional[Path]:
        """Convert an MCP workspace root URI to a local filesystem path."""
        if not uri:
            return None
        parsed = urlparse(uri)
        path = unquote(parsed.path) if parsed.scheme == "file" else uri
        if not path:
            return None
        if sys.platform == "win32":
            m = re.match(r"^/([A-Za-z]:[\\/].*)$", path)
            if m:
                path = m.group(1)
            elif re.match(r"^/[A-Za-z]:$", path):
                path = path[1:] + "/"
        p = Path(path)
        return p if p.is_dir() else None

    def _capture_roots(self, roots: List[Any], params: Optional[Dict[str, Any]] = None) -> None:
        """Store client-provided workspace roots from initialize/notifications requests."""
        collected: List[Path] = []

        def _add_uri(uri_val: Any) -> None:
            if isinstance(uri_val, str):
                p = self._uri_to_path(uri_val)
                if p is not None and p not in collected:
                    collected.append(p)

        for r in roots or []:
            if isinstance(r, dict):
                _add_uri(r.get("uri", ""))
            elif isinstance(r, str):
                _add_uri(r)

        if isinstance(params, dict):
            for wf in params.get("workspaceFolders") or []:
                if isinstance(wf, dict):
                    _add_uri(wf.get("uri", ""))
            _add_uri(params.get("rootUri"))
            _add_uri(params.get("rootPath"))

        if collected or roots or params is None:
            self.client_roots = collected

    def _resolve_root(self) -> Optional[Path]:
        """Resolve active GenOps project root: explicit root (if initialized), client roots, then CWD."""
        if self._explicit_root is not None and is_genops_project(self._explicit_root):
            return self._explicit_root
        candidates = list(self.client_roots)
        if self._explicit_root is not None and self._explicit_root not in candidates:
            candidates.append(self._explicit_root)
        cwd = Path.cwd().resolve()
        if cwd not in candidates:
            candidates.append(cwd)
        for c in candidates:
            root = discover_project_root(c)
            if root is not None:
                return root
        return None

    def _bootstrap_root(self) -> Path:
        """Choose target root for genops_init when genops.yaml does not exist yet."""
        if self._explicit_root is not None:
            return self._explicit_root
        if self.client_roots:
            return self.client_roots[0]
        return Path.cwd().resolve()

    def _assets_root(self, project_root: Optional[Path] = None) -> Path:
        """Locate `.agents` assets in workspace or bundled script directory."""
        if project_root and (project_root / ".agents" / "skills").is_dir():
            return project_root / ".agents"
        return Path(__file__).resolve().parent.parent

    def _handle_resources_list(self) -> Dict[str, Any]:
        root = self._resolve_root() or self._bootstrap_root()
        resources = [
            {"uri": "genops://context", "name": "Living Project Context", "description": "Active system context memory (.agents/context/CONTEXT.md)", "mimeType": "text/markdown"},
            {"uri": "genops://state", "name": "Pipeline State v2.0", "description": "Live cryptographic pipeline stage state", "mimeType": "application/json"},
            {"uri": "genops://graph", "name": "Lineage DAG", "description": "Specification dependency graph JSON", "mimeType": "application/json"},
        ]
        if is_genops_project(root):
            for s in MarkdownParser.collect_specs(root):
                resources.append({
                    "uri": f"genops://spec/{s.id}",
                    "name": f"{s.id} ({s.stage.upper()})",
                    "description": f"{s.path} [{s.status}]",
                    "mimeType": "text/markdown",
                })
        return {"resources": resources}

    def _handle_resources_read(self, uri: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        root = self._resolve_root() or self._bootstrap_root()
        if uri == "genops://context":
            ctx_path = root / ".agents" / "context" / "CONTEXT.md"
            text = ctx_path.read_text(encoding="utf-8") if ctx_path.is_file() else ContextCompactor.compact(root).read_text(encoding="utf-8")
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}, None
        if uri == "genops://state":
            if is_genops_project(root):
                payload = StateRepository(root).compute_live_status()
            else:
                payload = StateRepository(root).load_state()
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, indent=2)}]}, None
        if uri == "genops://graph":
            specs = MarkdownParser.collect_specs(root)
            graph = LineageGraphService.generate_graph(specs)
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(graph, indent=2)}]}, None
        if uri.startswith("genops://spec/"):
            target_id = uri[len("genops://spec/"):]
            for s in MarkdownParser.collect_specs(root):
                if s.id == target_id:
                    full_path = root / s.path
                    text = full_path.read_text(encoding="utf-8") if full_path.is_file() else s.body
                    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}, None
            return None, f"Unknown specification resource: {uri}"
        return None, f"Unknown resource URI: {uri}"

    def _handle_prompts_list(self) -> Dict[str, Any]:
        skills_dir = self._assets_root(self._resolve_root()) / "skills"
        prompts: List[Dict[str, Any]] = []
        if skills_dir.is_dir():
            for sk in sorted(skills_dir.glob("genops*/SKILL.md")):
                fm, _ = MarkdownParser.parse_frontmatter(sk)
                name = str(fm.get("name") or sk.parent.name)
                desc = str(fm.get("description") or f"Execute {name} workflow")
                prompts.append({
                    "name": name,
                    "description": desc,
                    "arguments": [
                        {"name": "domain", "description": "Optional target domain slug", "required": False},
                        {"name": "mode", "description": "Optional flow flag (--fast, --flow, --nonstop)", "required": False},
                    ],
                })
        return {"prompts": prompts}

    def _handle_prompts_get(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        skills_dir = self._assets_root(self._resolve_root()) / "skills"
        target_skill = skills_dir / name / "SKILL.md"
        if not target_skill.is_file():
            for sk in sorted(skills_dir.glob("genops*/SKILL.md")):
                fm, _ = MarkdownParser.parse_frontmatter(sk)
                if fm.get("name") == name:
                    target_skill = sk
                    break
        if not target_skill.is_file():
            return None, f"Unknown prompt: {name}"
        fm, body = MarkdownParser.parse_frontmatter(target_skill)
        desc = str(fm.get("description") or f"Execute {name} protocol")
        args_str = " ".join(f"{k}={v}" for k, v in (arguments or {}).items() if v)
        suffix = f"\n\nInvocation parameters: {args_str}" if args_str else ""
        return {
            "description": desc,
            "messages": [{"role": "user", "content": {"type": "text", "text": body.strip() + suffix}}],
        }, None

    def dispatch(self, name: str, args: Dict[str, Any]) -> Tuple[str, bool]:
        """Dispatch MCP tool calls directly to Domain Services."""
        try:
            if name == "genops_init":
                target_root = self._bootstrap_root()
                res = run_init(
                    target_root,
                    preset_name=str(args.get("preset", "")),
                    agent_target=str(args.get("agent", "all")),
                    force=bool(args.get("force", False)),
                    dry_run=bool(args.get("dry_run", False)),
                    clean_template=bool(args.get("clean_template", False)),
                )
                return json.dumps(res, indent=2), False

            root = self._resolve_root()
            if root is None:
                return (
                    "No GenOps project found in the current workspace. "
                    "Run from a project containing genops.yaml, or initialize one with `genops_init` / `genops init --preset software-spec`.",
                    True,
                )
            self.root_dir = root
            self.state_repo = StateRepository(root)

            if name == "genops_validate":
                errors, warnings = _collect_validation(self.root_dir)
                lines: List[str] = []
                if warnings:
                    lines.append("Warnings:\n" + "\n".join(f"- {w}" for w in warnings))
                if errors:
                    _record_audit_event_safe(
                        self.root_dir,
                        "VALIDATE_FAILED",
                        "pipeline",
                        "agent",
                        {"error_count": len(errors), "errors": errors[:10]},
                    )
                    lines.append("Validation Errors:\n" + "\n".join(f"- {e}" for e in errors))
                    return "\n\n".join(lines), True
                lines.insert(0, "Valid: Pipeline configuration, schemas, scaffolds, presets, and event chain passed.")
                return "\n\n".join(lines), False

            elif name == "genops_doctor":
                report = _collect_doctor(self.root_dir)
                return json.dumps(report, indent=2), not report["healthy"]

            elif name == "genops_status":
                live_status = self.state_repo.compute_live_status(domain_filter=args.get("domain"))
                return json.dumps(live_status, indent=2), False

            elif name == "genops_impact":
                spec_query = str(args.get("spec", ""))
                result = ImpactSimulator.simulate(self.root_dir, spec_query)
                return json.dumps(result, indent=2), False

            elif name == "genops_hash":
                rel_target = str(args.get("target", ""))
                tgt = self.root_dir / rel_target
                if not ScaffoldingService.is_safe_subpath(tgt, self.root_dir):
                    return f"Path traversal rejected for target: {rel_target}", True
                if tgt.is_file():
                    return DeterministicHasher.hash_file(tgt), False
                if tgt.is_dir():
                    comb, _ = DeterministicHasher.hash_directory(tgt)
                    return comb, False
                return f"Target '{rel_target}' not found.", True

            elif name == "genops_record":
                stg = str(args.get("stage", ""))
                actor = str(args.get("actor", "agent"))
                st_val = str(args.get("state", "approved"))
                force = bool(args.get("force", False))
                rec = self.state_repo.record_stage(stg, actor, state=st_val, force=force)
                return json.dumps(rec, indent=2), False

            elif name == "genops_scaffold":
                mod = str(args.get("module", ""))
                scaff = str(args.get("scaffold", ""))
                ents = [e.strip() for e in str(args.get("entities", "")).split(",") if e.strip()]
                force = bool(args.get("force", False))
                dry_run = bool(args.get("dry_run", False))
                summary = ScaffoldingService.scaffold_module(
                    self.root_dir, mod, scaff, ents, force=force, dry_run=dry_run
                )
                if not dry_run and is_genops_project(self.root_dir):
                    self.state_repo.append_event("SCAFFOLDED", "code", "agent", {"module": summary["module"], "scaffold": scaff})
                return json.dumps(summary, indent=2), False

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
                _atomic_write_text(out_path, json.dumps(graph, indent=2) + "\n")
                return "Graph persisted to docs/.genops-graph.json.", False

            elif name == "genops_drift":
                drifts = AntiDriftService.check_drift(self.root_dir)
                if drifts:
                    _record_audit_event_safe(
                        self.root_dir,
                        "DRIFT_DETECTED",
                        "code",
                        "agent",
                        {"drift_count": len(drifts), "drifts": drifts[:10]},
                    )
                    return "Drift Detected:\n" + "\n".join(f"- {d}" for d in drifts), True
                return "Anti-Drift Gate: All stubs and symbols in sync with LLD.", False

            elif name == "genops_check_rules":
                specs = MarkdownParser.collect_specs(self.root_dir)
                violations = LineageGraphService.check_rules(specs, self.root_dir)
                declared = LineageGraphService.get_declared_rules(self.root_dir)
                if violations:
                    return "Violations:\n" + "\n".join(f"- {v}" for v in violations), True
                if declared:
                    rules_txt = "\n".join(f"- [{r['from']} -> {r['to']}] {r['rule']}" for r in declared)
                    return f"All cross-layer semantic rules passed.\n\nDeclared pipeline validation rules ({len(declared)}):\n{rules_txt}", False
                return "All cross-layer semantic rules passed.", False

            elif name == "genops_rtm":
                specs = MarkdownParser.collect_specs(self.root_dir)
                rows = TraceabilityService.build_rtm(specs)
                return json.dumps(rows, indent=2), False

            elif name == "genops_context":
                domain = str(args.get("domain", ""))
                max_chars = int(args.get("max_chars", 60000))
                specs = MarkdownParser.collect_specs(self.root_dir)
                matched = LineageGraphService.slice_domain_context(specs, domain)
                if not matched:
                    return f"No specs found for domain: '{domain}'", True
                return LineageGraphService.format_domain_context(matched, max_chars=max_chars), False

            elif name == "genops_report":
                rel_html = str(args.get("html", "docs/report.html"))
                out_html = self.root_dir / rel_html
                if not ScaffoldingService.is_safe_subpath(out_html, self.root_dir):
                    return f"Path traversal rejected for html report: {rel_html}", True
                ReportService.generate_html_report(self.root_dir, out_html)
                return f"Report generated at {out_html.relative_to(self.root_dir).as_posix()}.", False

            elif name == "genops_ingest":
                src_dir = str(args.get("src", "src"))
                force = bool(args.get("force", False))
                dry_run = bool(args.get("dry_run", False))
                dest, count = BrownfieldIngestionService.ingest_codebase(
                    self.root_dir, src_dir, force=force, dry_run=dry_run
                )
                if not dry_run and is_genops_project(self.root_dir):
                    self.state_repo.append_event("INGESTED", "lld", "agent", {"src": src_dir, "modules": count})
                return f"Brownfield baseline LLD generated at {dest.relative_to(self.root_dir).as_posix()} with {count} detected modules.", False

            elif name == "genops_explain":
                stg = str(args.get("stage", ""))
                info = ExplainService.explain_stage(
                    self.root_dir, stg, ConfigManager, StateRepository, _resolve_asset_dir, _safe_rel
                )
                return json.dumps(info, indent=2), False

            elif name == "genops_workspace":
                act = str(args.get("action", "status"))
                if act == "doctor":
                    w_rep = WorkspaceService.workspace_doctor(self.root_dir, _collect_doctor, _safe_rel)
                    return json.dumps(w_rep, indent=2), not w_rep["healthy"]
                w_stat = WorkspaceService.workspace_status(self.root_dir, StateRepository, _safe_rel)
                return json.dumps(w_stat, indent=2), False

            elif name == "genops_rotate_events":
                max_ev = int(args.get("max_events", 500))
                rot = self.state_repo.rotate_events(max_events=max_ev, actor="agent")
                return json.dumps(rot, indent=2), False

            return f"Unknown tool: {name}", True
        except Exception as e:
            logger.debug("MCP dispatch error in %s: %s", name, e, exc_info=True)
            return f"Error executing tool '{name}': {e}", True

    @staticmethod
    def _read_rpc_payload(in_stream: Any) -> Optional[str]:
        """Read next JSON-RPC payload supporting both newline-delimited and UTF-8 byte-accurate Content-Length framing."""
        while True:
            line = in_stream.readline()
            if not line:
                return None
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("content-length:"):
                try:
                    length = int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    return stripped
                while True:
                    hdr = in_stream.readline()
                    if not hdr or not hdr.strip():
                        break
                chunks: List[str] = []
                bytes_read = 0
                while bytes_read < length:
                    ch = in_stream.read(1)
                    if not ch:
                        break
                    chunks.append(ch)
                    bytes_read += len(ch.encode("utf-8"))
                return "".join(chunks)
            return stripped

    @staticmethod
    def _rpc_error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    def run(self, stdin: Optional[Any] = None, stdout: Optional[Any] = None) -> None:
        """Main JSON-RPC 2.0 stdio loop with strict error taxonomy and notification suppression."""
        in_stream = stdin if stdin is not None else sys.stdin
        out_stream = stdout if stdout is not None else sys.stdout

        while True:
            req_id: Any = None
            raw_payload = self._read_rpc_payload(in_stream)
            if raw_payload is None:
                break
            try:
                req = json.loads(raw_payload)
            except json.JSONDecodeError as e:
                out_stream.write(json.dumps(self._rpc_error(None, -32700, f"Parse error: {e}")) + "\n")
                out_stream.flush()
                continue

            if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str) or not req.get("method"):
                err_id = req.get("id") if isinstance(req, dict) else None
                out_stream.write(json.dumps(self._rpc_error(err_id, -32600, "Invalid Request")) + "\n")
                out_stream.flush()
                continue

            method = req["method"]
            params = req.get("params") or {}
            is_notification = "id" not in req
            req_id = req.get("id")

            if is_notification:
                if method == "notifications/roots/list_changed" and isinstance(params, dict):
                    if "roots" in params:
                        self._capture_roots(params.get("roots", []), params=params)
                continue

            try:
                if method == "initialize":
                    p_dict = params if isinstance(params, dict) else {}
                    self._capture_roots(p_dict.get("roots", []), params=p_dict)
                    resp: Dict[str, Any] = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                            "serverInfo": {"name": "genops-engine", "version": __version__},
                        },
                    }
                elif method == "ping":
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                elif method == "tools/list":
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.TOOLS_SPEC}}
                elif method == "tools/call":
                    if not isinstance(params, dict) or not isinstance(params.get("name"), str) or not params.get("name"):
                        resp = self._rpc_error(req_id, -32602, "Invalid params: expected object with tool 'name'")
                    else:
                        tool_name = params["name"]
                        tool_args = params.get("arguments", {})
                        tool_def = self._tools_by_name.get(tool_name)
                        if tool_def is None:
                            resp = self._rpc_error(req_id, -32602, f"Invalid params: Unknown tool '{tool_name}'")
                        elif not isinstance(tool_args, dict):
                            resp = self._rpc_error(req_id, -32602, "Invalid params: 'arguments' must be an object")
                        else:
                            param_errors = JsonSchemaValidator.validate(tool_args, tool_def["inputSchema"], "arguments")
                            if param_errors:
                                resp = self._rpc_error(req_id, -32602, "Invalid params: " + "; ".join(param_errors))
                            else:
                                with contextlib.redirect_stdout(sys.stderr):
                                    out_text, is_error = self.dispatch(tool_name, tool_args)
                                resp = {
                                    "jsonrpc": "2.0",
                                    "id": req_id,
                                    "result": {
                                        "content": [{"type": "text", "text": out_text}],
                                        "isError": is_error,
                                    },
                                }
                elif method == "resources/list":
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": self._handle_resources_list()}
                elif method == "resources/templates/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "resourceTemplates": [
                                {
                                    "uriTemplate": "genops://spec/{id}",
                                    "name": "GenOps Specification Document",
                                    "description": "Read any indexed specification document by its ID (e.g. PRD-001-accounts)",
                                    "mimeType": "text/markdown",
                                }
                            ]
                        },
                    }
                elif method == "logging/setLevel":
                    lvl_str = str(params.get("level", "warning")).upper() if isinstance(params, dict) else "WARNING"
                    lvl_map = {
                        "DEBUG": logging.DEBUG,
                        "INFO": logging.INFO,
                        "NOTICE": logging.INFO,
                        "WARNING": logging.WARNING,
                        "ERROR": logging.ERROR,
                        "CRITICAL": logging.CRITICAL,
                        "ALERT": logging.CRITICAL,
                        "EMERGENCY": logging.CRITICAL,
                    }
                    logger.setLevel(lvl_map.get(lvl_str, logging.WARNING))
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                elif method == "resources/read":
                    if not isinstance(params, dict) or not isinstance(params.get("uri"), str):
                        resp = self._rpc_error(req_id, -32602, "Invalid params: expected string 'uri'")
                    else:
                        res_data, err_msg = self._handle_resources_read(params["uri"])
                        if err_msg:
                            resp = self._rpc_error(req_id, -32602, err_msg)
                        else:
                            resp = {"jsonrpc": "2.0", "id": req_id, "result": res_data}
                elif method == "prompts/list":
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": self._handle_prompts_list()}
                elif method == "prompts/get":
                    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                        resp = self._rpc_error(req_id, -32602, "Invalid params: expected string 'name'")
                    else:
                        pr_data, err_msg = self._handle_prompts_get(params["name"], params.get("arguments"))
                        if err_msg:
                            resp = self._rpc_error(req_id, -32602, err_msg)
                        else:
                            resp = {"jsonrpc": "2.0", "id": req_id, "result": pr_data}
                else:
                    resp = self._rpc_error(req_id, -32601, f"Method '{method}' not found")
            except Exception as e:
                logger.debug("MCP internal error on %s: %s", method, e, exc_info=True)
                resp = self._rpc_error(req_id, -32603, str(e))

            out_stream.write(json.dumps(resp) + "\n")
            out_stream.flush()


# ==============================================================================
# Domain VIII: CLI Controller & Dispatcher
# ==============================================================================

_AGENT_TARGETS_MAP = {
    "antigravity": ["AGENTS.md"],
    "claude": ["CLAUDE.md"],
    "gemini": ["GEMINI.md"],
    "cursor": [".cursor/rules/genops.mdc"],
    "copilot": [".github/copilot-instructions.md"],
    "windsurf": [".windsurfrules"],
    "conventions": ["CONVENTIONS.md"],
}


def run_init(
    root_dir: Path,
    preset_name: str = "",
    agent_target: str = "all",
    force: bool = False,
    dry_run: bool = False,
    clean_template: bool = False,
) -> Dict[str, Any]:
    """Initialize GenOps workspace assets, instruction blocks, state file, and living context."""
    pkg_dir = Path(__file__).resolve().parent.parent
    target_agents_dir = root_dir / ".agents"
    copied_folders: List[str] = []

    if not target_agents_dir.exists() and pkg_dir.exists() and (pkg_dir / "presets").exists() and root_dir != pkg_dir:
        if not dry_run:
            target_agents_dir.mkdir(parents=True, exist_ok=True)
        for folder in ["presets", "schemas", "scaffolds", "templates", "skills", "scripts"]:
            src_f = pkg_dir / folder
            if src_f.exists() and not (target_agents_dir / folder).exists():
                if not dry_run:
                    shutil.copytree(src_f, target_agents_dir / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                copied_folders.append(folder)

    config_file = root_dir / "genops.yaml"
    applied_preset = ""
    if preset_name:
        if config_file.exists() and not force:
            raise FileExistsError("genops.yaml already exists. Pass --force to overwrite it with a preset.")
        preset_file = root_dir / ".agents" / "presets" / f"{preset_name}.yaml"
        if not preset_file.exists() and (pkg_dir / "presets" / f"{preset_name}.yaml").exists():
            preset_file = pkg_dir / "presets" / f"{preset_name}.yaml"
        if not preset_file.exists():
            raise FileNotFoundError(f"Preset '{preset_name}' not found at {preset_file}.")
        p_text = preset_file.read_text(encoding="utf-8")
        if not dry_run:
            _atomic_write_text(config_file, p_text)
        applied_preset = preset_name

    if not config_file.exists() and not (dry_run and preset_name):
        raise FileNotFoundError("genops.yaml missing. Run `genops init --preset software-spec`.")

    if config_file.exists():
        cfg = ConfigManager.load_yaml(config_file)
    else:
        cfg = ConfigManager.load_yaml(pkg_dir / "presets" / f"{preset_name}.yaml")

    pipeline = cfg.get("pipeline", {})
    p_name = str(pipeline.get("name", "Specification Pipeline"))
    stages = pipeline.get("stages", [])
    block = ConfigManager.generate_agent_instructions(p_name, stages)

    if agent_target == "all":
        rel_targets = [rel for paths in _AGENT_TARGETS_MAP.values() for rel in paths]
    elif agent_target in _AGENT_TARGETS_MAP:
        rel_targets = _AGENT_TARGETS_MAP[agent_target]
    else:
        raise ValueError(
            f"Unknown agent target '{agent_target}'. Choose from: all, {', '.join(sorted(_AGENT_TARGETS_MAP))}."
        )

    synced_files: List[str] = []
    for rel in rel_targets:
        ConfigManager.sync_agent_file(root_dir / rel, block, dry_run=dry_run)
        synced_files.append(rel)

    cleaned_paths: List[str] = []
    if clean_template:
        for extra in ["examples", "docs/releases"]:
            extra_path = root_dir / extra
            if extra_path.exists():
                if not dry_run:
                    shutil.rmtree(extra_path, ignore_errors=True)
                cleaned_paths.append(extra)

    state_repo = StateRepository(root_dir)
    if not dry_run:
        if not state_repo.state_file.exists():
            _atomic_write_text(
                state_repo.state_file,
                json.dumps({"version": "2.0", "pipeline": "genops.yaml", "stages": {}}, indent=2) + "\n",
            )
        ContextCompactor.compact(root_dir)
        state_repo.append_event("INIT", "pipeline", "user", {"preset": applied_preset or "existing", "synced": synced_files})

    return {
        "dry_run": dry_run,
        "preset_applied": applied_preset,
        "copied_folders": copied_folders,
        "synced_files": synced_files,
        "cleaned_paths": cleaned_paths,
    }


def cmd_init(args: argparse.Namespace, root_dir: Path) -> None:
    res = run_init(
        root_dir,
        preset_name=args.preset,
        agent_target=args.agent or "all",
        force=bool(getattr(args, "force", False)),
        dry_run=bool(getattr(args, "dry_run", False)),
        clean_template=bool(getattr(args, "clean_template", False)),
    )
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return
    prefix = "[DRY-RUN] " if res["dry_run"] else ""
    if res["preset_applied"]:
        print(f"[OK] {prefix}Applied preset '{res['preset_applied']}' to genops.yaml.")
    for rel in res["synced_files"]:
        print(f"  [+] {prefix}Synced agent instructions: {rel}")
    for cl in res["cleaned_paths"]:
        print(f"  [-] {prefix}Cleaned template asset: {cl}")
    print(f"\n[OK] {prefix}GenOps initialized across {len(res['synced_files'])} agent interfaces.")


_UNSUPPORTED_SCHEMA_KEYWORDS: Set[str] = set()


def _scan_schema_keywords(node: Any, warnings: List[str], where: str) -> None:
    """Recursively detect JSON Schema keywords the built-in validator does not enforce."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _UNSUPPORTED_SCHEMA_KEYWORDS:
                warnings.append(f"{where}: uses unsupported keyword '{k}' (ignored by the built-in Draft-07 subset validator)")
            if k == "properties" and isinstance(v, dict):
                for prop_schema in v.values():
                    _scan_schema_keywords(prop_schema, warnings, where)
            else:
                _scan_schema_keywords(v, warnings, where)
    elif isinstance(node, list):
        for v in node:
            _scan_schema_keywords(v, warnings, where)


def _collect_validation(root_dir: Path) -> Tuple[List[str], List[str]]:
    """Run all schema, scaffold, preset, state, event-chain, and agent-sync checks."""
    config_file = root_dir / "genops.yaml"
    errors: List[str] = []
    warnings: List[str] = []

    if not config_file.exists():
        return ["genops.yaml does not exist. Run `genops init --preset software-spec`."], []

    # 1. Validate genops.yaml against schema
    schemas_dir = _resolve_asset_dir(root_dir, "schemas")
    skills_dir = _resolve_asset_dir(root_dir, "skills")
    templates_dir = _resolve_asset_dir(root_dir, "templates")
    cfg_schema_path = schemas_dir / "genops.schema.json"
    cfg = ConfigManager.load_yaml(config_file)
    if cfg_schema_path.exists():
        with open(cfg_schema_path, "r", encoding="utf-8") as sf:
            schema_data = json.load(sf)
        errors.extend(JsonSchemaValidator.validate(cfg, schema_data, "genops.yaml"))
        _scan_schema_keywords(schema_data, warnings, "genops.schema.json")

    pipeline = cfg.get("pipeline", {})
    stages = pipeline.get("stages", [])
    stage_ids = {s.get("id") for s in stages if "id" in s}

    for stg in stages:
        sid = stg.get("id")
        if not sid:
            continue

        skill_path = skills_dir / f"genops-{sid}" / "SKILL.md"
        if not skill_path.exists():
            warnings.append(f"Stage '{sid}' skill missing at {_safe_rel(skill_path, root_dir)}")

        tmpl_rel = stg.get("template")
        if tmpl_rel:
            tmpl_path = templates_dir / tmpl_rel
            if not tmpl_path.exists():
                errors.append(f"Stage '{sid}' template missing at {_safe_rel(tmpl_path, root_dir)}")
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
    scaff_schema_path = schemas_dir / "scaffold.schema.json"
    scaffold_dir = _resolve_asset_dir(root_dir, "scaffolds")
    known_casing_keys = set(ScaffoldingService.build_casing_map("module-name", "EntityName").keys())
    if scaffold_dir.exists() and scaff_schema_path.exists():
        with open(scaff_schema_path, "r", encoding="utf-8") as scf:
            scaff_schema = json.load(scf)
        _scan_schema_keywords(scaff_schema, warnings, "scaffold.schema.json")
        for sf in sorted(scaffold_dir.glob("*/STRUCTURE.yaml")):
            try:
                s_data = ConfigManager.load_yaml(sf)
                errors.extend(JsonSchemaValidator.validate(s_data, scaff_schema, _safe_rel(sf, root_dir)))
            except Exception as e:
                errors.append(f"Failed to parse scaffold '{sf}': {e}")
                continue

            for tmpl_name in s_data.get("templates", {}):
                if not (sf.parent / tmpl_name).exists():
                    errors.append(f"Scaffold '{sf.parent.name}' references missing template '{tmpl_name}'")

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
    presets_dir = _resolve_asset_dir(root_dir, "presets")
    if presets_dir.exists() and cfg_schema_path.exists():
        with open(cfg_schema_path, "r", encoding="utf-8") as pf:
            preset_schema = json.load(pf)
        for preset_file in sorted(presets_dir.glob("*.yaml")):
            try:
                preset_data = ConfigManager.load_yaml(preset_file)
                errors.extend(JsonSchemaValidator.validate(preset_data, preset_schema, _safe_rel(preset_file, root_dir)))
            except Exception as e:
                errors.append(f"Failed to parse preset '{preset_file}': {e}")

    # 4. Validate state file and audit event hash chain if present
    state_schema_path = schemas_dir / "state.schema.json"
    state_file = root_dir / "docs" / ".genops-state.json"
    if state_file.exists() and state_schema_path.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as sff:
                state_data = json.load(sff)
            with open(state_schema_path, "r", encoding="utf-8") as stf:
                state_schema = json.load(stf)
            _scan_schema_keywords(state_schema, warnings, "state.schema.json")
            errors.extend(JsonSchemaValidator.validate(state_data, state_schema, "docs/.genops-state.json"))
        except Exception as e:
            errors.append(f"Failed to parse state file: {e}")

    errors.extend(StateRepository(root_dir).verify_event_chain())

    # 5. Check managed agent instruction blocks match genops.yaml
    if stages:
        expected_block = ConfigManager.generate_agent_instructions(str(pipeline.get("name", "Specification Pipeline")), stages)
        block_re = re.compile(r"<!-- GENOPS:START.*?-->.*?<!-- GENOPS:END -->", re.DOTALL)
        for paths in _AGENT_TARGETS_MAP.values():
            for rel in paths:
                agent_path = root_dir / rel
                if not agent_path.is_file():
                    continue
                content = agent_path.read_text(encoding="utf-8")
                m = block_re.search(content)
                if m and m.group(0).strip() != expected_block.strip():
                    warnings.append(f"{rel}: managed GenOps instruction block is out of sync with genops.yaml (run `genops init`)")

    return errors, warnings


def _collect_doctor(root_dir: Path) -> Dict[str, Any]:
    """Run all governance gates cleanly and return consolidated results for CLI and MCP."""
    v_errors, v_warnings = _collect_validation(root_dir)
    specs = MarkdownParser.collect_specs(root_dir)
    rule_errors = LineageGraphService.check_rules(specs, root_dir)
    drift_errors = AntiDriftService.check_drift(root_dir)
    ver = CompilerVerifier.verify_workspace(root_dir)
    ver_errors = [] if ver.get("success") else ver.get("errors", [])

    gates = [
        {"name": "validate (schemas, templates, scaffolds, presets)", "errors": v_errors, "warnings": v_warnings},
        {"name": "check-rules (cross-layer semantic integrity)", "errors": rule_errors, "warnings": []},
        {"name": "drift (LLD <-> source sync)", "errors": drift_errors, "warnings": []},
        {"name": "verify (compiler/linter diagnostics)", "errors": ver_errors, "warnings": []},
    ]
    total_errors = sum(len(g["errors"]) for g in gates)
    next_action = ""
    if is_genops_project(root_dir):
        try:
            next_action = str(StateRepository(root_dir).compute_live_status().get("next_action", ""))
        except Exception:
            next_action = ""
    return {
        "healthy": total_errors == 0,
        "total_errors": total_errors,
        "next_action": next_action,
        "gates": gates,
    }


def cmd_validate(args: argparse.Namespace, root_dir: Path) -> None:
    if not (root_dir / "genops.yaml").exists():
        print("[ERROR] genops.yaml does not exist.\n  Hint: Run `python .agents/scripts/genops.py init --preset software-spec`.", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    errors, warnings = _collect_validation(root_dir)
    if errors:
        _record_audit_event_safe(
            root_dir,
            "VALIDATE_FAILED",
            "pipeline",
            "user",
            {"error_count": len(errors), "errors": errors[:10]},
        )
    if getattr(args, "sarif", False):
        sarif_doc = SarifExporter.build_sarif(
            __version__, [{"rule_id": "GENOPS-VALIDATE", "name": "validate", "errors": errors, "warnings": warnings}]
        )
        print(json.dumps(sarif_doc, indent=2))
        if errors:
            sys.exit(EXIT_GATE_FAILURE)
        return
    if getattr(args, "json", False):
        print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, indent=2))
        if errors:
            sys.exit(EXIT_GATE_FAILURE)
        return

    print("Running JSON Schema validation & integrity checks...")
    if warnings:
        print(f"\n[WARN] {len(warnings)} WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    if errors:
        print(f"\n[ERROR] {len(errors)} SCHEMA / PIPELINE ERRORS FOUND:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(EXIT_GATE_FAILURE)

    print("\n[OK] Zero-Dependency Schema Validation PASSED: All configs, templates, and scaffolds are VALID.")


def cmd_doctor(args: argparse.Namespace, root_dir: Path) -> None:
    """Run every governance gate in one shot and report a consolidated health check."""
    if not (root_dir / "genops.yaml").exists():
        print("[ERROR] genops.yaml not found.\n  Hint: Run `python .agents/scripts/genops.py init --preset software-spec`.", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    report = _collect_doctor(root_dir)
    if getattr(args, "sarif", False):
        sarif_doc = SarifExporter.build_sarif(__version__, report["gates"])
        print(json.dumps(sarif_doc, indent=2))
        if not report["healthy"]:
            sys.exit(EXIT_GATE_FAILURE)
        return
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
        if not report["healthy"]:
            sys.exit(EXIT_GATE_FAILURE)
        return

    print("GenOps Doctor — comprehensive repository health check\n")
    for gate in report["gates"]:
        errs = gate["errors"]
        warns = gate["warnings"]
        if errs:
            print(f"{_style('[FAIL]', '31')} {gate['name']} ({len(errs)} issue(s))", file=sys.stderr)
            for e in errs:
                print(f"        - {e}", file=sys.stderr)
        else:
            print(f"{_style('[PASS]', '32')} {gate['name']}")
        for w in warns:
            print(f"        {_style('[WARN]', '33')} {w}", file=sys.stderr)

    print()
    if report.get("next_action"):
        print(f"Next Step: {report['next_action']}")
    if not report["healthy"]:
        print(f"[ERROR] Doctor found {report['total_errors']} issue(s). Fix them before relying on the pipeline.", file=sys.stderr)
        sys.exit(EXIT_GATE_FAILURE)
    print("[OK] All governance gates passed — GenOps is healthy.")


def cmd_demo(args: argparse.Namespace, root_dir: Path) -> None:
    """Scaffold a throwaway module and verify it, proving the pipeline end-to-end."""
    scaffold_id = args.scaffold or "go-service"
    module = args.module or "demo-svc"
    entities = [e.strip() for e in (args.entities or "Ping").split(",") if e.strip()]

    scaffold_src = _resolve_asset_dir(root_dir, "scaffolds") / scaffold_id
    if not scaffold_src.exists():
        print(f"[ERROR] scaffold '{scaffold_id}' not found at {scaffold_src}.", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    demo_root = root_dir / ".genops-demo"
    shutil.rmtree(demo_root, ignore_errors=True)
    try:
        (demo_root / ".agents" / "scaffolds").mkdir(parents=True)
        shutil.copytree(scaffold_src, demo_root / ".agents" / "scaffolds" / scaffold_id)

        print(f"GenOps demo — scaffolding '{module}' ({scaffold_id}) and verifying...\n")
        summary = ScaffoldingService.scaffold_module(demo_root, module, scaffold_id, entities)
        files = [p for p in (demo_root / "src").rglob("*") if p.is_file() and not p.name.startswith(".")]
        print(f"Generated {len(files)} files under .genops-demo/src/{summary['module']}/.")

        result = CompilerVerifier.verify_workspace(demo_root)
        for c in result.get("checks", []):
            print(f"  [+] {c}")
        for s in result.get("skipped", []):
            print(f"  [~] {s}")
        for e in result.get("errors", []):
            print(f"  [-] {e}", file=sys.stderr)
    finally:
        shutil.rmtree(demo_root, ignore_errors=True)

    print("\n[OK] Demo complete — throwaway workspace removed.")
    if not result.get("success", False):
        sys.exit(EXIT_GATE_FAILURE)


def cmd_impact(args: argparse.Namespace, root_dir: Path) -> None:
    """CLI Change-Impact Simulator."""
    res = ImpactSimulator.simulate(root_dir, args.spec)
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return

    use_uni = _use_unicode()
    branch = "├──" if use_uni else "+--"
    leaf = "└──" if use_uni else "`--"
    pipe = "│" if use_uni else "|"

    print(f"\nChange Impact Blast Radius for: {res['target']['id']} ({res['target']['path']})")
    print("=" * 80)
    print(f"{branch} Affected Downstream Specs ({res['downstream_specs_count']}):")
    for s in res["downstream_specs"]:
        print(f"{pipe}   {branch} [{s['stage'].upper()}] {s['id']} ({s['path']})")
    print(f"{branch} Affected Code Modules ({len(res['affected_modules'])}):")
    for m in res["affected_modules"]:
        print(f"{pipe}   {branch} src/{m}/")
    print(f"{branch} Affected Domain Entities: {', '.join(res['affected_entities']) or 'None'}")
    print(f"{leaf} Source Files Requiring Review ({res['affected_source_files_count']}):")
    for sf in res["affected_source_files"][:10]:
        print(f"    {branch} {sf}")
    if res["affected_source_files_count"] > 10:
        print(f"    {leaf} ... ({res['affected_source_files_count'] - 10} more files)")


def cmd_status(args: argparse.Namespace, root_dir: Path) -> None:
    if not (root_dir / "genops.yaml").exists():
        print("[ERROR] genops.yaml not found.\n  Hint: Run `python .agents/scripts/genops.py init --preset software-spec`.", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    res = StateRepository(root_dir).compute_live_status(domain_filter=getattr(args, "domain", ""))
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return

    print(f"\nPipeline: {res['pipeline_name']}")
    print(f"Status as of: {res['timestamp']}\n")
    print(f"{'Stage':<12} | {'State':<10} | {'Last Run':<19} | {'Upstream':<12} | {'Downstream':<12}")
    print("-" * 75)

    for sid, st in res["stages"].items():
        print(f"{sid:<12} | {st['state']:<10} | {st['last_run']:<19} | {st['upstream_status']:<12} | {st['downstream_status']:<12}")

    if res.get("domain_specs"):
        print(f"\nDomain Slice '{res.get('domain_filter', '')}' ({len(res['domain_specs'])} specs):")
        for ds in res["domain_specs"]:
            print(f"  - [{ds['stage'].upper()}] {ds['id']} ({ds['status']}) — {ds['path']}")

    if res["issues"]:
        print("\nIssues detected:")
        for iss in res["issues"]:
            print(f"  [WARN] {iss}")

    print(f"\nNext Step: {res['next_action']}")


def main() -> None:
    common_sub = argparse.ArgumentParser(add_help=False)
    common_sub.add_argument("--root", "-C", default=argparse.SUPPRESS, help="Explicit project root directory")
    common_sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit machine-readable JSON output")
    common_sub.add_argument("--sarif", action="store_true", default=argparse.SUPPRESS, help="Emit OASIS SARIF v2.1.0 JSON report")
    common_sub.add_argument("--verbose", "-v", action="store_true", default=argparse.SUPPRESS, help="Enable verbose debug logging on stderr")
    common_sub.add_argument("--quiet", "-q", action="store_true", default=argparse.SUPPRESS, help="Suppress non-error diagnostic logs")
    common_sub.add_argument("--log-format", choices=["text", "json"], default=argparse.SUPPRESS, help="Stderr log format (text or json)")

    parser = argparse.ArgumentParser(
        description="GenOps Deterministic Pipeline Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python .agents/scripts/genops.py init --preset software-spec\n"
            "  python .agents/scripts/genops.py doctor\n"
            "  python .agents/scripts/genops.py status --json\n"
            "  python .agents/scripts/genops.py scaffold --module billing --scaffold go-service --entities Invoice\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", "-C", default="", help="Explicit project root directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument("--sarif", action="store_true", help="Emit OASIS SARIF v2.1.0 JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging on stderr")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error diagnostic logs")
    parser.add_argument("--log-format", choices=["text", "json"], default="", help="Stderr log format (text or json)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", parents=[common_sub], help="Initialize GenOps across agent entrypoint files")
    p_init.add_argument("--preset", default="", help="Pipeline preset name (software-spec, research, design)")
    p_init.add_argument("--agent", default="all", help="Target agent")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing genops.yaml when applying --preset")
    p_init.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    p_init.add_argument("--clean-template", action="store_true", help="Remove template examples/ and release notes")

    # hash
    p_hash = subparsers.add_parser("hash", parents=[common_sub], help="Compute LF-normalized SHA-256 hash for file or directory")
    p_hash.add_argument("target", help="Path to file or directory")

    # validate
    subparsers.add_parser("validate", parents=[common_sub], help="Validate genops.yaml, presets, templates, and scaffolds")

    # doctor
    subparsers.add_parser("doctor", parents=[common_sub], help="Run all governance gates (validate, check-rules, drift, verify) at once")

    # impact
    p_imp = subparsers.add_parser("impact", parents=[common_sub], help="Simulate change impact blast radius across downstream specs and code")
    p_imp.add_argument("spec", help="Target specification ID or file path")

    # status
    p_stat = subparsers.add_parser("status", parents=[common_sub], help="Show live pipeline health status dashboard")
    p_stat.add_argument("--domain", default="", help="Filter lineage view for a specific domain slug")

    # record
    p_rec = subparsers.add_parser("record", parents=[common_sub], help="Record stage lifecycle state into state v2")
    p_rec.add_argument("stage", help="Stage ID")
    p_rec.add_argument("--actor", default="user", help="Approver identity")
    p_rec.add_argument("--state", default="approved", choices=["drafting", "generated", "approved", "skipped"], help="Recorded lifecycle state")
    p_rec.add_argument("--force", action="store_true", help="Override upstream or placeholder approval checks")

    # scaffold
    p_scaff = subparsers.add_parser("scaffold", parents=[common_sub], help="Deterministically scaffold a module from a scaffold template")
    p_scaff.add_argument("--module", required=True, help="Module directory name")
    p_scaff.add_argument("--scaffold", required=True, help="Scaffold identifier")
    p_scaff.add_argument("--entities", default="", help="Comma-separated entities")
    p_scaff.add_argument("--force", action="store_true", help="Overwrite existing template entrypoints")
    p_scaff.add_argument("--dry-run", action="store_true", help="Preview scaffold plan without writing files")

    # graph
    subparsers.add_parser("graph", parents=[common_sub], help="Generate specification lineage DAG")

    # check-rules
    subparsers.add_parser("check-rules", parents=[common_sub], help="Verify semantic cross-layer validation rules")

    # drift
    subparsers.add_parser("drift", parents=[common_sub], help="Run CI/CD anti-drift check between LLD and code")

    # rtm
    subparsers.add_parser("rtm", parents=[common_sub], help="Generate Requirements Traceability Matrix")

    # context
    p_ctx = subparsers.add_parser("context", parents=[common_sub], help="Extract upstream DAG lineage slice for a domain")
    p_ctx.add_argument("--domain", required=True, help="Domain slug")
    p_ctx.add_argument("--max-chars", type=int, default=60000, help="Maximum character budget for context output")

    # compact
    subparsers.add_parser("compact", parents=[common_sub], help="Compact living project memory into CONTEXT.md")

    # verify
    subparsers.add_parser("verify", parents=[common_sub], help="Run compiler verification across source modules")

    # report
    p_rep = subparsers.add_parser("report", parents=[common_sub], help="Generate self-contained executive HTML dashboard")
    p_rep.add_argument("--html", default="docs/report.html", help="Output HTML filepath")

    # ingest
    p_ing = subparsers.add_parser("ingest", parents=[common_sub], help="Brownfield codebase reverse engineering")
    p_ing.add_argument("--src", default="src", help="Source directory to analyze")
    p_ing.add_argument("--force", action="store_true", help="Overwrite existing brownfield baseline LLD")
    p_ing.add_argument("--dry-run", action="store_true", help="Preview ingestion result without writing file")

    # explain
    p_exp = subparsers.add_parser("explain", parents=[common_sub], help="Explain a configured stage's prerequisites, outputs, template, skill, and rules")
    p_exp.add_argument("stage", help="Stage ID to explain (e.g. prd, hld, adr, lld, code)")

    # workspace
    p_ws = subparsers.add_parser("workspace", parents=[common_sub], help="Multi-project monorepo orchestration (status, doctor)")
    p_ws.add_argument("action", nargs="?", default="status", choices=["status", "doctor"], help="Workspace action (status or doctor)")

    # rotate-events
    p_rot = subparsers.add_parser("rotate-events", parents=[common_sub], help="Rotate docs/.genops-events.jsonl with a cryptographic checkpoint")
    p_rot.add_argument("--max-events", type=int, default=500, help="Maximum events to keep in active log")

    # mcp
    subparsers.add_parser("mcp", parents=[common_sub], help="Run JSON-RPC stdio MCP server for agent tool-calling")

    # demo
    p_demo = subparsers.add_parser("demo", parents=[common_sub], help="Scaffold a throwaway module and verify it (proves the pipeline end-to-end)")
    p_demo.add_argument("--scaffold", default="go-service", help="Scaffold id (default: go-service)")
    p_demo.add_argument("--module", default="demo-svc", help="Module name (default: demo-svc)")
    p_demo.add_argument("--entities", default="Ping", help="Comma-separated entities")

    args = parser.parse_args()
    if args.verbose and args.quiet:
        parser.error("argument --quiet: not allowed with argument --verbose")
    configure_logging(
        verbose=args.verbose,
        quiet=args.quiet,
        log_format=getattr(args, "log_format", "") or None,
    )

    if args.root:
        root_dir = Path(args.root).resolve()
        if not root_dir.is_dir():
            print(f"[ERROR] Project root directory does not exist: {args.root}", file=sys.stderr)
            sys.exit(EXIT_USAGE_ERROR)
    elif args.command == "mcp":
        server = MCPServer(root_dir=None)
        server.run()
        return
    else:
        curr_dir = Path.cwd().resolve()
        discovered = discover_project_root(curr_dir, allow_git_fallback=(args.command == "init"))
        if discovered is None:
            if args.command == "init":
                root_dir = curr_dir
            else:
                print(
                    "[ERROR] No genops.yaml found in this directory tree.\n"
                    "  Hint: Run from a GenOps project, pass `--root <dir>`, or initialize with `genops init --preset software-spec`.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_USAGE_ERROR)
        else:
            root_dir = discovered

    logger.debug("Executing GenOps command='%s' root='%s'", args.command, root_dir)

    try:
        if args.command == "init":
            cmd_init(args, root_dir)
        elif args.command == "hash":
            target = root_dir / args.target
            if not ScaffoldingService.is_safe_subpath(target, root_dir):
                raise ValueError(f"Target path escapes project root: {args.target}")
            if target.is_file():
                h = DeterministicHasher.hash_file(target)
                if args.json:
                    print(json.dumps({"target": target.relative_to(root_dir).as_posix(), "sha256": h}, indent=2))
                else:
                    print(f"{target.relative_to(root_dir).as_posix()}: {h}")
            elif target.is_dir():
                comb, files = DeterministicHasher.hash_directory(target)
                if args.json:
                    print(json.dumps({"directory": target.relative_to(root_dir).as_posix(), "combined_hash": comb, "files": files}, indent=2))
                else:
                    print(f"Directory: {target.relative_to(root_dir).as_posix()}")
                    for f, h in files.items():
                        print(f"  {f}: {h}")
                    print(f"Combined Hash: {comb}")
            else:
                raise FileNotFoundError(f"Target '{args.target}' does not exist.")
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
            rec = repo.record_stage(args.stage, args.actor, state=args.state, force=bool(getattr(args, "force", False)))
            if args.json:
                print(json.dumps(rec, indent=2))
            else:
                print(f"[OK] Stage '{args.stage}' ({args.state}) recorded safely (lock-protected v2.0 schema).")
        elif args.command == "explain":
            info = ExplainService.explain_stage(
                root_dir, args.stage, ConfigManager, StateRepository, _resolve_asset_dir, _safe_rel
            )
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print(f"\nStage: {info['id']} — {info['name']}")
                print("=" * 70)
                print(f"  Command:      {info['command']}")
                print(f"  Live State:   {info['live_state']}")
                print(f"  Focus:        {info['focus']}")
                print(f"  Requires:     {', '.join(info['requires']) or '(None - root stage)'}")
                print(f"  Outputs:      {', '.join(info['outputs'])}")
                print(f"  File Pattern: {info['file_pattern'] or '(directory output)'}")
                print(f"  Template:     {info['template'] or '(N/A)'}")
                print(f"  Skill:        {info['skill']}")
                print(f"  Next Stages:  {', '.join(info['next']) or '(Terminal stage)'}")
                if info["inbound_validation_rules"]:
                    print("  Inbound Rules:")
                    for r in info["inbound_validation_rules"]:
                        print(f"    - [{r.get('from')} -> {r.get('to')}] {r.get('rule')}")
                if info["outbound_validation_rules"]:
                    print("  Outbound Rules:")
                    for r in info["outbound_validation_rules"]:
                        print(f"    - [{r.get('from')} -> {r.get('to')}] {r.get('rule')}")
        elif args.command == "workspace":
            if args.action == "doctor":
                w_rep = WorkspaceService.workspace_doctor(root_dir, _collect_doctor, _safe_rel)
                if args.json:
                    print(json.dumps(w_rep, indent=2))
                else:
                    print(f"\nGenOps Workspace Doctor ({w_rep['project_count']} project(s))")
                    print("=" * 70)
                    for p in w_rep["projects"]:
                        tag = "[PASS]" if p["healthy"] else "[FAIL]"
                        print(f"  {tag} {p['project']:<32} (errors: {p['total_errors']})")
                if not w_rep["healthy"]:
                    sys.exit(EXIT_GATE_FAILURE)
            else:
                w_stat = WorkspaceService.workspace_status(root_dir, StateRepository, _safe_rel)
                if args.json:
                    print(json.dumps(w_stat, indent=2))
                else:
                    print(f"\nGenOps Workspace Status ({w_stat['project_count']} project(s))")
                    print("=" * 70)
                    for p in w_stat["projects"]:
                        st_summary = ", ".join(f"{k}:{v}" for k, v in p.get("stages", {}).items())
                        print(f"  - {p['project']:<30} | {st_summary}")
        elif args.command == "rotate-events":
            rot = StateRepository(root_dir).rotate_events(max_events=args.max_events, actor="user")
            if args.json:
                print(json.dumps(rot, indent=2))
            elif rot["rotated"]:
                print(f"[OK] Archived {rot['archived_count']} events to {rot['archive_file']} ({rot['remaining_count']} active).")
            else:
                print(f"[OK] No rotation needed ({rot['remaining_count']} events <= {args.max_events}).")
        elif args.command == "scaffold":
            ents = [e.strip() for e in (args.entities or "").split(",") if e.strip()]
            summary = ScaffoldingService.scaffold_module(
                root_dir, args.module, args.scaffold, ents, force=args.force, dry_run=args.dry_run
            )
            if not args.dry_run and is_genops_project(root_dir):
                StateRepository(root_dir).append_event("SCAFFOLDED", "code", "user", {"module": summary["module"], "scaffold": args.scaffold})
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                prefix = "[DRY-RUN] " if args.dry_run else ""
                print(f"[OK] {prefix}Scaffold '{summary['module']}' ({args.scaffold}): {len(summary['created'])} created, {len(summary['overwritten'])} overwritten, {len(summary['skipped'])} skipped.")
                for item in summary["created"]:
                    print(f"  [+] {item}")
                for item in summary["overwritten"]:
                    print(f"  [*] {item}")
                for item in summary["skipped"]:
                    print(f"  [~] Skipped existing: {item} (pass --force to overwrite)")
        elif args.command == "graph":
            specs = MarkdownParser.collect_specs(root_dir)
            graph = LineageGraphService.generate_graph(specs)
            graph_file = root_dir / "docs" / ".genops-graph.json"
            _atomic_write_text(graph_file, json.dumps(graph, indent=2) + "\n")
            print(json.dumps(graph, indent=2) if args.json else "[OK] Lineage graph persisted to docs/.genops-graph.json.")
        elif args.command == "check-rules":
            specs = MarkdownParser.collect_specs(root_dir)
            violations = LineageGraphService.check_rules(specs, root_dir)
            declared = LineageGraphService.get_declared_rules(root_dir)
            if getattr(args, "sarif", False):
                sarif_doc = SarifExporter.build_sarif(
                    __version__, [{"rule_id": "GENOPS-RULES", "name": "check-rules", "errors": violations, "warnings": []}]
                )
                print(json.dumps(sarif_doc, indent=2))
                if violations:
                    sys.exit(EXIT_GATE_FAILURE)
            elif args.json:
                print(json.dumps({"passed": not violations, "violations": violations, "declared_rules": declared}, indent=2))
                if violations:
                    sys.exit(EXIT_GATE_FAILURE)
            elif violations:
                print(f"\n[ERROR] {len(violations)} RULE VIOLATIONS FOUND:", file=sys.stderr)
                for v in violations:
                    print(f"  - {v}", file=sys.stderr)
                sys.exit(EXIT_GATE_FAILURE)
            else:
                print("\n[OK] All cross-layer semantic validation rules PASSED.")
                if declared:
                    print(f"\nDeclared pipeline validation rules ({len(declared)}):")
                    for r in declared:
                        print(f"  - [{r['from']} -> {r['to']}] {r['rule']}")
        elif args.command == "drift":
            drifts = AntiDriftService.check_drift(root_dir)
            if drifts:
                _record_audit_event_safe(
                    root_dir,
                    "DRIFT_DETECTED",
                    "code",
                    "user",
                    {"drift_count": len(drifts), "drifts": drifts[:10]},
                )
            if getattr(args, "sarif", False):
                sarif_doc = SarifExporter.build_sarif(
                    __version__, [{"rule_id": "GENOPS-DRIFT", "name": "drift", "errors": drifts, "warnings": []}]
                )
                print(json.dumps(sarif_doc, indent=2))
                if drifts:
                    sys.exit(EXIT_GATE_FAILURE)
            elif args.json:
                print(json.dumps({"passed": not drifts, "drifts": drifts}, indent=2))
                if drifts:
                    sys.exit(EXIT_GATE_FAILURE)
            elif drifts:
                print(f"\n[ERROR] DRIFT DETECTED ({len(drifts)} issues):", file=sys.stderr)
                for d in drifts:
                    print(f"  - {d}", file=sys.stderr)
                sys.exit(EXIT_GATE_FAILURE)
            else:
                print("\n[OK] Anti-Drift Gate: All LLD modules and entity stubs are synchronized with src/.")
        elif args.command == "rtm":
            specs = MarkdownParser.collect_specs(root_dir)
            rows = TraceabilityService.build_rtm(specs)
            if args.json:
                print(json.dumps(rows, indent=2))
                return
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
            target = LineageGraphService.slice_domain_context(specs, args.domain)
            if not target:
                print(f"[ERROR] No specifications found for domain: '{args.domain}'", file=sys.stderr)
                sys.exit(EXIT_USAGE_ERROR)
            if args.json:
                print(json.dumps({"domain": args.domain, "specs": [{"id": s.id, "stage": s.stage, "path": s.path, "body": s.body} for s in target]}, indent=2))
            else:
                print(f"# Context Lineage Slice for Domain: {args.domain}\n")
                print(LineageGraphService.format_domain_context(target, max_chars=args.max_chars))
        elif args.command == "compact":
            p = ContextCompactor.compact(root_dir)
            print(json.dumps({"context_file": p.relative_to(root_dir).as_posix()}, indent=2) if args.json else f"[OK] Compacted living memory persisted to {p.relative_to(root_dir).as_posix()}")
        elif args.command == "verify":
            res = CompilerVerifier.verify_workspace(root_dir)
            if args.json:
                print(json.dumps(res, indent=2))
                if res.get("errors"):
                    sys.exit(EXIT_GATE_FAILURE)
                return
            for c in res.get("checks", []):
                print(f"  [+] {c}")
            for s in res.get("skipped", []):
                print(f"  [~] {s}")
            if res.get("errors"):
                print("[ERROR] Compiler diagnostics found errors:", file=sys.stderr)
                for err in res["errors"]:
                    print(f"  - {err}", file=sys.stderr)
                sys.exit(EXIT_GATE_FAILURE)
            if not res.get("checks") and res.get("skipped"):
                print("[~] Nothing was verified (toolchains unavailable or no source modules).")
            else:
                print("[OK] Compiler & linter verification passed cleanly.")
        elif args.command == "report":
            out_html = root_dir / args.html
            if not ScaffoldingService.is_safe_subpath(out_html, root_dir):
                raise ValueError(f"Report output path escapes project root: {args.html}")
            ReportService.generate_html_report(root_dir, out_html)
            print(json.dumps({"report": out_html.relative_to(root_dir).as_posix()}, indent=2) if args.json else f"[OK] Self-contained executive report generated at {out_html.relative_to(root_dir).as_posix()}.")
        elif args.command == "ingest":
            lld_dest, count = BrownfieldIngestionService.ingest_codebase(
                root_dir, args.src, force=args.force, dry_run=args.dry_run
            )
            if not args.dry_run and is_genops_project(root_dir):
                StateRepository(root_dir).append_event("INGESTED", "lld", "user", {"src": args.src, "modules": count})
            if args.json:
                print(json.dumps({"output": lld_dest.relative_to(root_dir).as_posix(), "modules": count, "dry_run": args.dry_run}, indent=2))
            else:
                prefix = "[DRY-RUN] " if args.dry_run else ""
                print(f"[OK] {prefix}Brownfield baseline LLD generated at {lld_dest.relative_to(root_dir).as_posix()} with {count} detected modules.")
        elif args.command == "mcp":
            server = MCPServer(root_dir=root_dir)
            server.run()
    except TimeoutError as e:
        if args.verbose:
            logger.exception("Lock acquisition timed out")
        print(f"[ERROR] {e}\n  Hint: Remove stale docs/.genops.lock if no other GenOps process is active.", file=sys.stderr)
        sys.exit(EXIT_LOCK_TIMEOUT)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        if args.verbose:
            logger.exception("Command failed")
        print(f"[ERROR] {e}\n  Hint: Run `python .agents/scripts/genops.py {args.command} --help` to inspect required arguments and flags.", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)


if __name__ == "__main__":
    main()
