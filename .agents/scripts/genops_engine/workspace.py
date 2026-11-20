"""Cross-repository federated lineage, multi-project workspace orchestration, and stage explainability services."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple


class FederationService:
    """Resolves cross-repository ext://<alias>/<SPEC-ID> references against sibling paths or federation lockfiles."""

    _EXT_REF_RE = re.compile(r"^ext://([a-z][a-z0-9_-]*)/([A-Za-z0-9_-]+)$")

    @staticmethod
    def _infer_stage_from_id(spec_id: str) -> str:
        prefix = spec_id.split("-", 1)[0].lower()
        stage_map = {
            "prd": "prd",
            "hld": "hld",
            "adr": "adr",
            "lld": "lld",
            "brief": "brief",
            "wire": "wireframes",
            "mock": "mockups",
            "proto": "prototype",
            "lit": "lit-review",
            "hypoth": "hypothesis",
            "expr": "experiment",
            "rprt": "report",
        }
        return stage_map.get(prefix, prefix)

    @classmethod
    def resolve_external_refs(
        cls,
        root_dir: Path,
        cfg: Dict[str, Any],
        markdown_parser_cls: Any,
        hasher_cls: Any,
    ) -> Tuple[Set[str], Dict[str, str], List[str]]:
        """
        Return (valid_ext_ids, ext_id_to_stage, federation_errors) from pipeline.federation.remotes
        and optional docs/.genops-federation-lock.json.
        """
        valid_ext_ids: Set[str] = set()
        ext_id_to_stage: Dict[str, str] = {}
        errors: List[str] = []

        federation = cfg.get("pipeline", {}).get("federation", {})
        if not isinstance(federation, dict):
            return valid_ext_ids, ext_id_to_stage, errors

        lock_file = root_dir / "docs" / ".genops-federation-lock.json"
        lock_remotes: Dict[str, Any] = {}
        if lock_file.is_file():
            try:
                lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
                if isinstance(lock_data, dict) and isinstance(lock_data.get("remotes"), dict):
                    lock_remotes = lock_data["remotes"]
            except Exception as e:
                errors.append(f"[docs/.genops-federation-lock.json] Invalid federation lockfile JSON: {e}")

        for rem in federation.get("remotes", []):
            if not isinstance(rem, dict) or not rem.get("alias"):
                continue
            alias = str(rem["alias"]).strip()
            allowed_specs = rem.get("allowed_specs", [])
            if isinstance(allowed_specs, list):
                for sp_id in allowed_specs:
                    s_id = str(sp_id).strip()
                    if s_id:
                        ext_uri = f"ext://{alias}/{s_id}"
                        valid_ext_ids.add(ext_uri)
                        ext_id_to_stage[ext_uri] = cls._infer_stage_from_id(s_id)

            if alias in lock_remotes and isinstance(lock_remotes[alias], dict):
                for sp_id, sp_meta in lock_remotes[alias].get("specs", {}).items():
                    ext_uri = f"ext://{alias}/{sp_id}"
                    valid_ext_ids.add(ext_uri)
                    st = sp_meta.get("stage") if isinstance(sp_meta, dict) else None
                    ext_id_to_stage[ext_uri] = str(st or cls._infer_stage_from_id(str(sp_id)))

            rel_path = rem.get("path")
            if rel_path:
                rem_root = (root_dir / str(rel_path)).resolve()
                if not rem_root.is_dir():
                    errors.append(f"[genops.yaml] Federated remote '{alias}' path does not exist: {rel_path}")
                    continue
                expected_sha = rem.get("lock_sha256")
                if expected_sha and (rem_root / "docs").is_dir():
                    live_sha, _ = hasher_cls.hash_directory(rem_root / "docs", "*.md")
                    if live_sha and live_sha != expected_sha:
                        errors.append(
                            f"[genops.yaml] Federated remote '{alias}' lock_sha256 mismatch "
                            f"(expected {str(expected_sha)[:12]}..., got {live_sha[:12]}...)"
                        )
                for sp in markdown_parser_cls.collect_specs(rem_root):
                    ext_uri = f"ext://{alias}/{sp.id}"
                    valid_ext_ids.add(ext_uri)
                    ext_id_to_stage[ext_uri] = sp.stage

        return valid_ext_ids, ext_id_to_stage, errors


class WorkspaceService:
    """Discovers and orchestrates multiple GenOps projects inside a monorepo/workspace."""

    _SKIP_DIRS = {
        ".git", ".agents", ".genops-demo", "__pycache__", "node_modules",
        ".venv", "venv", "dist", "build", "target",
    }

    @classmethod
    def discover_projects(cls, root_dir: Path) -> List[Path]:
        """Return sorted list of directories under *root_dir* containing a `genops.yaml` file."""
        projects: List[Path] = []
        base = root_dir.resolve()
        for cfg in sorted(base.rglob("genops.yaml")):
            try:
                rel_parts = cfg.relative_to(base).parts
            except ValueError:
                continue
            if any(p in cls._SKIP_DIRS or (p.startswith(".") and p != ".") for p in rel_parts[:-1]):
                continue
            projects.append(cfg.parent)
        return projects

    @classmethod
    def workspace_status(
        cls,
        root_dir: Path,
        state_repo_cls: Any,
        rel_fn: Callable[[Path, Path], str],
    ) -> Dict[str, Any]:
        projects = cls.discover_projects(root_dir)
        items: List[Dict[str, Any]] = []
        for proj in projects:
            rel = rel_fn(proj, root_dir) or "."
            try:
                status = state_repo_cls(proj).compute_live_status()
                items.append({
                    "project": rel,
                    "pipeline_name": status.get("pipeline_name", ""),
                    "stages": {k: v.get("state", "absent") for k, v in status.get("stages", {}).items()},
                    "issues_count": len(status.get("issues", [])),
                    "next_action": status.get("next_action", ""),
                })
            except Exception as e:
                items.append({"project": rel, "error": str(e), "issues_count": 1})
        return {
            "workspace_root": root_dir.as_posix(),
            "project_count": len(items),
            "projects": items,
        }

    @classmethod
    def workspace_doctor(
        cls,
        root_dir: Path,
        doctor_fn: Callable[[Path], Dict[str, Any]],
        rel_fn: Callable[[Path, Path], str],
    ) -> Dict[str, Any]:
        projects = cls.discover_projects(root_dir)
        items: List[Dict[str, Any]] = []
        total_errors = 0
        for proj in projects:
            rel = rel_fn(proj, root_dir) or "."
            rep = doctor_fn(proj)
            errs = int(rep.get("total_errors", 0))
            total_errors += errs
            items.append({
                "project": rel,
                "healthy": bool(rep.get("healthy", False)),
                "total_errors": errs,
                "next_action": rep.get("next_action", ""),
            })
        return {
            "workspace_root": root_dir.as_posix(),
            "healthy": total_errors == 0,
            "total_errors": total_errors,
            "project_count": len(items),
            "projects": items,
        }


class ExplainService:
    """Provides interactive CLI/MCP introspection for any configured GenOps stage."""

    @staticmethod
    def explain_stage(
        root_dir: Path,
        stage_id: str,
        config_manager_cls: Any,
        state_repo_cls: Any,
        resolve_asset_fn: Callable[[Path, str], Path],
        rel_fn: Callable[[Path, Path], str],
    ) -> Dict[str, Any]:
        cfg_file = root_dir / "genops.yaml"
        if not cfg_file.is_file():
            raise FileNotFoundError("genops.yaml not found.")
        cfg = config_manager_cls.load_yaml(cfg_file)
        pipeline = cfg.get("pipeline", {})
        stages = pipeline.get("stages", [])
        stg = next((s for s in stages if str(s.get("id", "")) == stage_id), None)
        if not stg:
            valid = ", ".join(str(s.get("id", "")) for s in stages if s.get("id"))
            raise ValueError(f"Unknown stage '{stage_id}'. Configured stages: {valid}")

        rules = pipeline.get("validation_rules", [])
        inbound_rules = [r for r in rules if isinstance(r, dict) and r.get("to") == stage_id]
        outbound_rules = [r for r in rules if isinstance(r, dict) and r.get("from") == stage_id]

        skills_dir = resolve_asset_fn(root_dir, "skills")
        templates_dir = resolve_asset_fn(root_dir, "templates")
        skill_path = skills_dir / f"genops-{stage_id}" / "SKILL.md"
        tmpl_rel = str(stg.get("template", ""))
        tmpl_path = (templates_dir / tmpl_rel) if tmpl_rel else None

        live_state = "absent"
        try:
            status = state_repo_cls(root_dir).compute_live_status()
            live_state = str(status.get("stages", {}).get(stage_id, {}).get("state", "absent"))
        except Exception:
            pass

        return {
            "id": stage_id,
            "name": str(stg.get("name", "")),
            "focus": str(stg.get("focus", "")),
            "command": f"/genops-{stage_id}",
            "live_state": live_state,
            "requires": list(stg.get("requires", [])),
            "outputs": list(stg.get("outputs", [])),
            "file_pattern": str(stg.get("file_pattern", "")),
            "template": rel_fn(tmpl_path, root_dir) if tmpl_path and tmpl_path.exists() else tmpl_rel,
            "skill": rel_fn(skill_path, root_dir) if skill_path.exists() else f".agents/skills/genops-{stage_id}/SKILL.md",
            "next": list(stg.get("next", [])),
            "inbound_validation_rules": inbound_rules,
            "outbound_validation_rules": outbound_rules,
        }
