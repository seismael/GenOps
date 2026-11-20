"""AST, symbol, SQL contract, and bidirectional reverse anti-drift verification between LLD specs and source code."""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path
from typing import Any, List, Set


class AntiDriftService:
    """Enforces AST/symbol, filename, reverse-module, and SQL contract anti-drift between LLD and src/."""

    _SOURCE_EXTS = {".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".rs", ".java"}
    _BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
    _LINE_COMMENT_RE = re.compile(r"(?://|#).*$", re.MULTILINE)
    _SQL_FENCE_RE = re.compile(r"```sql[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
    _CREATE_TABLE_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?([A-Za-z0-9_]+)[`\"']?",
        re.IGNORECASE,
    )

    @classmethod
    def _strip_comments(cls, text: str) -> str:
        """Strip C-style /* ... */, //..., and #... comments before regex symbol matching."""
        no_block = cls._BLOCK_COMMENT_RE.sub("", text)
        return cls._LINE_COMMENT_RE.sub("", no_block)

    @staticmethod
    def _python_has_symbol(text: str, ent_pascal: str, raw_ent: str) -> bool:
        """Use Python stdlib ast.parse to verify actual class, type alias, or function symbol declaration."""
        targets = {ent_pascal, raw_ent, ent_pascal.lower(), raw_ent.lower()}
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in (ent_pascal, raw_ent) or node.name.lower() in targets:
                    return True
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and (tgt.id in (ent_pascal, raw_ent)):
                        return True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in (ent_pascal, raw_ent):
                    return True
        return False

    @classmethod
    def _entity_symbol_in_module(
        cls,
        mod_path: Path,
        ent_pascal: str,
        raw_ent: str = "",
        should_skip_fn: Any = None,
    ) -> bool:
        """Scan module source files via AST (Python) or comment-stripped regex (Go/TS/Rust/Java) for *ent_pascal*."""
        names = [re.escape(ent_pascal)]
        if raw_ent and raw_ent != ent_pascal:
            names.append(re.escape(raw_ent))
        name_group = "|".join(names)
        sym_re = re.compile(
            rf"\b(?:class|struct|interface|type|enum|trait|record)\s+(?:{name_group})\b"
            rf"|\b(?:{name_group})\s+struct\b"
        )
        for p in sorted(mod_path.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in cls._SOURCE_EXTS:
                continue
            if should_skip_fn is not None and should_skip_fn(p, mod_path):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if p.suffix.lower() == ".py":
                if cls._python_has_symbol(text, ent_pascal, raw_ent or ent_pascal):
                    return True
            else:
                cleaned = cls._strip_comments(text)
                if sym_re.search(cleaned):
                    return True
        return False

    @staticmethod
    def _load_genopsignore(root_dir: Path) -> List[str]:
        """Load optional .genopsignore glob patterns from *root_dir*."""
        ignore_file = root_dir / ".genopsignore"
        if not ignore_file.is_file():
            return []
        patterns: List[str] = []
        try:
            for line in ignore_file.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    patterns.append(s.rstrip("/"))
        except OSError:
            pass
        return patterns

    @classmethod
    def _is_ignored(cls, rel_posix: str, mod_name: str, patterns: List[str]) -> bool:
        for pat in patterns:
            if fnmatch.fnmatch(rel_posix, pat) or fnmatch.fnmatch(mod_name, pat):
                return True
        return False

    @classmethod
    def _collect_module_sql_tables(cls, mod_path: Path, should_skip_fn: Any = None) -> Set[str]:
        """Collect all SQL CREATE TABLE names present inside *mod_path* source or .sql files."""
        found: Set[str] = set()
        sql_exts = cls._SOURCE_EXTS | {".sql"}
        for p in sorted(mod_path.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in sql_exts:
                continue
            if should_skip_fn is not None and should_skip_fn(p, mod_path):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in cls._CREATE_TABLE_RE.finditer(text):
                found.add(m.group(1).lower())
        return found

    @classmethod
    def check_drift(
        cls,
        root_dir: Path,
        table_parser_cls: Any,
        scaffolding_cls: Any,
        hasher_cls: Any,
    ) -> List[str]:
        """CI/CD Anti-Drift Gate: Verify forward module/entity symbol parity, reverse module parity, and SQL tables."""
        lld_dir = root_dir / "docs" / "lld"
        src_dir = root_dir / "src"

        if not lld_dir.exists():
            return []

        ignore_patterns = cls._load_genopsignore(root_dir)
        drift_items: List[str] = []
        declared_modules: Set[str] = set()

        for lld_file in sorted(lld_dir.glob("*.md")):
            try:
                content = lld_file.read_text(encoding="utf-8")
            except OSError:
                continue

            lld_modules_in_file: List[str] = []
            tables = table_parser_cls.parse_tables(content)
            for table in tables:
                for row in table:
                    m_name = row.get("Module", "").strip().strip("`")
                    m_entities = row.get("Entities", "").strip()

                    if not m_name or m_name.lower() in ("module", "---", "name"):
                        continue

                    declared_modules.add(m_name)
                    lld_modules_in_file.append(m_name)
                    mod_path = src_dir / m_name
                    if not mod_path.exists():
                        drift_items.append(
                            f"Missing scaffolded module directory: src/{m_name}/ (declared in {lld_file.name})"
                        )
                        continue

                    if m_entities and m_entities != "-":
                        ents = [e.strip().strip("`") for e in m_entities.split(",") if e.strip()]
                        for ent in ents:
                            words = scaffolding_cls.split_words(ent)
                            ent_kebab = "-".join(w.lower() for w in words)
                            ent_snake = "_".join(w.lower() for w in words)
                            ent_pascal = "".join(w.capitalize() for w in words)

                            matched_files = [
                                p
                                for p in (
                                    list(mod_path.rglob(f"*{ent_snake}*"))
                                    + list(mod_path.rglob(f"*{ent_kebab}*"))
                                    + list(mod_path.rglob(f"*{ent_pascal}*"))
                                )
                                if p.is_file() and not hasher_cls._should_skip(p, mod_path)
                            ]
                            has_symbol = cls._entity_symbol_in_module(
                                mod_path, ent_pascal, raw_ent=ent, should_skip_fn=hasher_cls._should_skip
                            )
                            if not matched_files and not has_symbol:
                                drift_items.append(
                                    f"Module src/{m_name}/ missing implementation stub or symbol '{ent}' (declared in {lld_file.name})"
                                )
                            elif matched_files and not has_symbol:
                                drift_items.append(
                                    f"Module src/{m_name}/ has matching filename for '{ent}' but lacks AST/type symbol '{ent_pascal}' (declared in {lld_file.name})"
                                )

            # SQL DDL contract drift check when LLD defines ```sql CREATE TABLE blocks
            lld_sql_tables: List[str] = []
            for sql_block in cls._SQL_FENCE_RE.findall(content):
                for m in cls._CREATE_TABLE_RE.finditer(sql_block):
                    tbl = m.group(1).strip()
                    if tbl and tbl.lower() not in [t.lower() for t in lld_sql_tables]:
                        lld_sql_tables.append(tbl)

            if lld_sql_tables and lld_modules_in_file:
                code_sql_tables: Set[str] = set()
                for m_name in lld_modules_in_file:
                    mp = src_dir / m_name
                    if mp.is_dir():
                        code_sql_tables |= cls._collect_module_sql_tables(mp, hasher_cls._should_skip)
                # Only enforce SQL table parity if the code module actually embeds SQL DDL
                if code_sql_tables:
                    for tbl in lld_sql_tables:
                        if tbl.lower() not in code_sql_tables:
                            drift_items.append(
                                f"SQL contract drift: table '{tbl}' declared in {lld_file.name} is missing from src/ DDL ({', '.join(lld_modules_in_file)})"
                            )

        # Bidirectional reverse-drift check: detect undeclared top-level directories in src/
        if declared_modules and src_dir.is_dir():
            for child in sorted(src_dir.iterdir()):
                if not child.is_dir():
                    continue
                if child.name.startswith(".") or child.name in hasher_cls.EXCLUDED_DIR_NAMES:
                    continue
                if child.name not in declared_modules:
                    rel_p = f"src/{child.name}"
                    if not cls._is_ignored(rel_p, child.name, ignore_patterns):
                        drift_items.append(
                            f"Undeclared source module directory: src/{child.name}/ is not documented in any LLD Modules table"
                        )

        return drift_items
