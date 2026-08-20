"""Install the GenOps CLI wrapper and MCP server config across common coding agents.

Portable: derives the engine path from this script's own location and every
user-config path from the home directory. No machine-specific hardcoded paths.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional


def _load_json(path: Path) -> dict:
    """Load JSON, returning {} on missing/corrupt file after backing the file up."""
    if not path.exists():
        return {}
    shutil.copy2(path, path.with_suffix(path.suffix + ".genops-bak"))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _set_mcp_server(data: dict, command: str, args: list, extra: Optional[dict] = None) -> dict:
    servers = data.setdefault("mcpServers", {})
    entry = {"command": command, "args": args}
    if extra:
        entry.update(extra)
    servers["genops"] = entry
    return data


def install() -> int:
    script = Path(__file__).resolve()
    home = Path.home()

    # 1. CLI wrappers into directories that are already on PATH
    bin_dirs = [
        home / "go" / "bin",
        home / ".local" / "bin",
        home / "AppData" / "Roaming" / "npm",  # Windows
    ]
    installed = 0
    for target in bin_dirs:
        if not target.is_dir():
            continue
        (target / "genops.cmd").write_text(f'@echo off\npython "{script}" %*\n', encoding="utf-8")
        (target / "genops.ps1").write_text(f'& python "{script}" $args\n', encoding="utf-8")
        (target / "genops").write_text(f'#!/usr/bin/env bash\npython "{script.as_posix()}" "$@"\n', encoding="utf-8")
        installed += 1
        print(f"[OK] Installed genops CLI wrapper in {target}")

    if installed == 0:
        print("[!] No standard bin directory found; skipping CLI wrappers.", file=sys.stderr)

    # 2. MCP registrations (JSON-based configs only)
    cline_settings = (
        home / "AppData" / "Roaming" / "Code" / "User" / "globalStorage"
        / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    )
    json_targets = [
        home / ".claude.json",                       # Claude Code
        home / ".config" / "opencode" / "mcp.json",  # OpenCode
        home / ".gemini" / "config" / "mcp_config.json",  # Gemini / Antigravity
        cline_settings,                              # VS Code / Cline
    ]
    for path in json_targets:
        if not path.exists():
            continue
        data = _load_json(path)
        if path == cline_settings:
            _set_mcp_server(
                data,
                sys.executable,
                [str(script), "mcp"],
                {"disabled": False, "autoApprove": [
                    "genops_status", "genops_validate", "genops_verify",
                    "genops_drift", "genops_compact", "genops_report", "genops_rtm",
                ]},
            )
        else:
            _set_mcp_server(data, sys.executable, [str(script), "mcp"])
        _save_json(path, data)
        print(f"[OK] Configured genops MCP in {path}")

    print("\n[SUCCESS] GenOps installed across detected coding tools on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(install())
