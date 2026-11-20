"""Install the GenOps CLI wrapper and MCP server config across common coding agents.

GenOps is a zero-dependency, vendored engine. This installer makes it available
*globally* (to Gemini/Antigravity, Claude Code, OpenCode, Cline) in a way that
survives both interpreter and source-repo churn:

1. Copies the bundled ``.agents/`` tree into a stable home (``~/.genops/``),
   independent of the source repository.
2. Writes a **self-healing launcher** (``~/.genops/bin/genops``) that re-resolves
   and validates a working Python interpreter on every launch, then execs the
   engine. The launcher never bakes ``sys.executable``, so deleting or upgrading
   the system Python does not break the registration.
3. Registers that launcher as the ``genops`` MCP server for every detected
   agent, using an absolute engine path and a stable launcher path.

The failure this prevents is CPython's "Could not find platform independent
libraries <prefix>" error, which occurs when an MCP config points at an
interpreter whose stdlib has been moved or deleted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def _default_genops_home() -> Path:
    """Resolve install root honoring GENOPS_HOME, XDG_DATA_HOME, then ~/.genops."""
    explicit = os.environ.get("GENOPS_HOME", "").strip()
    if explicit:
        return Path(explicit)
    xdg_data = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data:
        return Path(xdg_data) / "genops"
    return Path.home() / ".genops"


# Stable, agent-independent install root. Owned entirely by GenOps.
GENOPS_HOME = _default_genops_home()
BIN_DIR = GENOPS_HOME / "bin"

logger = logging.getLogger("genops.installer")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# Bundled asset folders that make the engine self-contained after copying.
ASSET_FOLDERS = [
    "context",
    "presets",
    "scaffolds",
    "schemas",
    "scripts",
    "skills",
    "templates",
]

# Standard bin directories that are already on PATH (for the CLI wrapper).
CLI_BIN_DIRS = [
    Path.home() / "go" / "bin",
    Path.home() / ".local" / "bin",
    Path.home() / "AppData" / "Roaming" / "npm",  # Windows
]

CLINE_AUTOAPPROVE = [
    "genops_status",
    "genops_validate",
    "genops_verify",
    "genops_drift",
    "genops_compact",
    "genops_report",
    "genops_rtm",
    "genops_doctor",
]


# ---------------------------------------------------------------------------
# Launcher templates (self-healing interpreter resolution).
# ``__ENGINE__`` is replaced with the absolute engine script path.
# ---------------------------------------------------------------------------

_PY_PROBE = "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"

_LAUNCHER_CMD = f"""@echo off
setlocal
set "ENGINE=__ENGINE__"
if "%~1"=="--self-test" goto selftest

python3 -c "{_PY_PROBE}" >nul 2>nul
if errorlevel 1 goto try_python
python3 "%ENGINE%" %*
exit /b %errorlevel%

:try_python
python -c "{_PY_PROBE}" >nul 2>nul
if errorlevel 1 goto try_py
python "%ENGINE%" %*
exit /b %errorlevel%

:try_py
py -3 -c "{_PY_PROBE}" >nul 2>nul
if errorlevel 1 goto no_python
py -3 "%ENGINE%" %*
exit /b %errorlevel%

:no_python
echo [genops] No working Python 3.8+ interpreter found (tried python3, python, py -3). Install Python 3.8+ and retry. 1>&2
exit /b 1

:selftest
if not exist "%ENGINE%" (
  echo [genops] engine MISSING: %ENGINE% 1>&2
  exit /b 1
)
echo [genops] engine OK: %ENGINE%
python3 -c "{_PY_PROBE}" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: python3 & exit /b 0 )
python -c "{_PY_PROBE}" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: python & exit /b 0 )
py -3 -c "{_PY_PROBE}" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: py -3 & exit /b 0 )
echo [genops] no working Python 3.8+ interpreter found 1>&2
exit /b 1
"""

_LAUNCHER_PS1 = f"""$ErrorActionPreference = 'SilentlyContinue'
$engine = '__ENGINE__'

if ($args.Count -gt 0 -and $args[0] -eq '--self-test') {{
    if (-not (Test-Path -LiteralPath $engine)) {{
        Write-Error "[genops] engine MISSING: $engine"
        exit 1
    }}
    Write-Output "[genops] engine OK: $engine"
    foreach ($py in @('python3', 'python')) {{
        & $py -c '{_PY_PROBE}' 2>$null
        if ($LASTEXITCODE -eq 0) {{ Write-Output "[genops] interpreter OK: $py"; exit 0 }}
    }}
    & py -3 -c '{_PY_PROBE}' 2>$null
    if ($LASTEXITCODE -eq 0) {{ Write-Output "[genops] interpreter OK: py -3"; exit 0 }}
    Write-Error "[genops] no working Python 3.8+ interpreter found"
    exit 1
}}

foreach ($py in @('python3', 'python')) {{
    & $py -c '{_PY_PROBE}' 2>$null
    if ($LASTEXITCODE -eq 0) {{ & $py $engine @args; exit $LASTEXITCODE }}
}}
& py -3 -c '{_PY_PROBE}' 2>$null
if ($LASTEXITCODE -eq 0) {{ & py -3 $engine @args; exit $LASTEXITCODE }}

Write-Error "[genops] No working Python 3.8+ interpreter found (tried python3, python, py -3). Install Python 3.8+ and retry."
exit 1
"""

_LAUNCHER_SH = f"""#!/usr/bin/env bash
set -u
ENGINE=__ENGINE__

if [ "${{1:-}}" = "--self-test" ]; then
    if [ ! -f "$ENGINE" ]; then
        echo "[genops] engine MISSING: $ENGINE" >&2
        exit 1
    fi
    echo "[genops] engine OK: $ENGINE"
    for py in python3 python /usr/bin/python3 /usr/local/bin/python3; do
        if command -v "$py" >/dev/null 2>&1 && "$py" -c '{_PY_PROBE}' >/dev/null 2>&1; then
            echo "[genops] interpreter OK: $py"
            exit 0
        fi
    done
    echo "[genops] no working Python 3.8+ interpreter found" >&2
    exit 1
fi

for py in python3 python /usr/bin/python3 /usr/local/bin/python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c '{_PY_PROBE}' >/dev/null 2>&1; then
        exec "$py" "$ENGINE" "$@"
    fi
done

echo "[genops] No working Python 3.8+ interpreter found (tried python3, python)." >&2
exit 1
"""


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Optional[dict]:
    """Load JSON safely. Returns None if an existing file has corrupt JSON so callers never wipe it."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Could not read %s: %s (skipping)", path, e)
        return None
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in %s (%s); skipping to avoid overwriting user config.", path, e)
        return None
    if not isinstance(data, dict):
        logger.warning("Top-level JSON in %s is not an object; skipping.", path)
        return None
    backup_path = path.with_suffix(path.suffix + ".genops-bak")
    shutil.copy2(path, backup_path)
    return data


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    try:
        tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _set_mcp_server(data: dict, entry: dict) -> dict:
    """Register (or replace) the ``genops`` MCP server entry."""
    servers = data.setdefault("mcpServers", {})
    servers["genops"] = entry
    return data


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


def copy_bundle(src_agents: Path, dest_root: Path, dry_run: bool = False) -> None:
    """Copy the self-contained asset folders from ``.agents/`` into ``dest_root`` cleanly."""
    ignore_fn = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    for folder in ASSET_FOLDERS:
        src = src_agents / folder
        if not src.is_dir():
            continue
        dest_folder = dest_root / folder
        if dry_run:
            print(f"[DRY-RUN] Sync bundle folder: {src} -> {dest_folder}")
            continue
        # Clean non-user asset directories so removed templates/scaffolds do not linger across upgrades
        if folder != "context" and dest_folder.exists():
            shutil.rmtree(dest_folder)
        shutil.copytree(src, dest_folder, dirs_exist_ok=True, ignore=ignore_fn)


def engine_path(dest_root: Path = GENOPS_HOME) -> Path:
    """Return the absolute path to the installed engine script."""
    return dest_root / "scripts" / "genops.py"


def _launcher_contents(template: str, engine: str, escape_ps1: bool = False) -> str:
    clean_engine = str(engine).replace("\r", "").replace("\n", "")
    if escape_ps1 or "$engine = '__ENGINE__'" in template:
        val = clean_engine.replace("'", "''")
    elif 'set "ENGINE=__ENGINE__"' in template or "@echo off" in template:
        val = clean_engine.replace('"', "").replace("%", "%%")
    elif "ENGINE=__ENGINE__" in template or "#!/usr/bin/env bash" in template:
        unquoted = clean_engine
        if len(unquoted) >= 2 and unquoted[0] == "'" and unquoted[-1] == "'":
            unquoted = unquoted[1:-1]
        val = "'" + unquoted.replace("'", "'\"'\"'") + "'"
    else:
        val = clean_engine
    return template.replace("__ENGINE__", val)


def _write_launchers(dest_root: Path, engine: Path, dry_run: bool = False) -> Dict[str, Path]:
    """Write per-platform self-healing launchers into ``<dest_root>/bin/``."""
    bin_dir = dest_root / "bin"
    launchers = {
        "cmd": bin_dir / "genops.cmd",
        "ps1": bin_dir / "genops.ps1",
        "sh": bin_dir / "genops",
    }
    if dry_run:
        print(f"[DRY-RUN] Write launchers into {bin_dir}")
        return launchers
    bin_dir.mkdir(parents=True, exist_ok=True)
    launchers["cmd"].write_text(
        _launcher_contents(_LAUNCHER_CMD, str(engine)), encoding="utf-8"
    )
    launchers["ps1"].write_text(
        _launcher_contents(_LAUNCHER_PS1, str(engine), escape_ps1=True), encoding="utf-8"
    )
    launchers["sh"].write_text(
        _launcher_contents(_LAUNCHER_SH, engine.as_posix()), encoding="utf-8"
    )
    launchers["sh"].chmod(0o755)
    return launchers


def _write_cli_wrappers(launchers: Dict[str, Path], dry_run: bool = False) -> int:
    """Install thin CLI wrappers into PATH directories that already exist."""
    installed = 0
    for target in CLI_BIN_DIRS:
        if not target.is_dir():
            continue
        if dry_run:
            print(f"[DRY-RUN] Install CLI wrapper in {target}")
            installed += 1
            continue
        if sys.platform == "win32":
            (target / "genops.cmd").write_text(
                f'@echo off\ncall "{launchers["cmd"]}" %*\n', encoding="utf-8"
            )
            (target / "genops.ps1").write_text(
                f'& "{launchers["ps1"]}" @args\n', encoding="utf-8"
            )
        sh_wrapper = target / "genops"
        sh_wrapper.write_text(
            f'#!/usr/bin/env bash\nexec "{launchers["sh"].as_posix()}" "$@"\n',
            encoding="utf-8",
        )
        sh_wrapper.chmod(0o755)
        installed += 1
        print(f"[OK] Installed genops CLI wrapper in {target}")
    if installed == 0:
        logger.warning("No standard bin directory found; skipping CLI wrappers.")
    return installed


def mcp_command(launchers: Dict[str, Path]) -> str:
    """Return the launcher path that MCP hosts can spawn on this platform."""
    if sys.platform == "win32":
        return str(launchers["cmd"])
    return str(launchers["sh"])


def _self_test(engine: Path) -> Tuple[bool, str]:
    """Confirm the installed engine is present and exposes the MCP server."""
    if not engine.is_file():
        return False, f"engine missing: {engine}"
    text = engine.read_text(encoding="utf-8", errors="replace")
    if 'add_parser("mcp"' not in text:
        return False, f"engine {engine} does not expose the 'mcp' subcommand"
    return True, f"engine OK: {engine}"


def register_mcp(data: dict, launchers: Dict[str, Path], target_kind: str) -> None:
    """Register the genops MCP server using the agent-appropriate config shape."""
    command = mcp_command(launchers)
    if target_kind in ("claude", "opencode"):
        entry = {"type": "stdio", "command": command, "args": ["mcp"], "env": {}}
    elif target_kind == "cline":
        entry = {
            "command": command,
            "args": ["mcp"],
            "disabled": False,
            "autoApprove": CLINE_AUTOAPPROVE,
        }
    else:  # gemini / antigravity / cursor / windsurf
        entry = {"command": command, "args": ["mcp"]}
    _set_mcp_server(data, entry)


def _cline_settings_path() -> Path:
    """Return the platform-specific Cline MCP settings path."""
    home = Path.home()
    if sys.platform == "win32":
        base = home / "AppData" / "Roaming" / "Code" / "User"
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "Code" / "User"
    else:
        base = home / ".config" / "Code" / "User"
    return base / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"


def _mcp_json_targets() -> List[Tuple[Path, str]]:
    home = Path.home()
    return [
        (home / ".claude.json", "claude"),
        (home / ".config" / "opencode" / "mcp.json", "opencode"),
        (home / ".gemini" / "config" / "mcp_config.json", "gemini"),
        (home / ".gemini" / "antigravity" / "mcp_config.json", "antigravity"),
        (home / ".cursor" / "mcp.json", "cursor"),
        (home / ".codeium" / "windsurf" / "mcp_config.json", "windsurf"),
        (_cline_settings_path(), "cline"),
    ]


def status(home: Path = GENOPS_HOME) -> int:
    """Report current global GenOps installation and MCP registration status."""
    engine = engine_path(home)
    ok, msg = _self_test(engine)
    print(f"GenOps Home: {home}")
    print(f"Engine:      {msg}")
    for p, kind in _mcp_json_targets():
        if not p.exists():
            continue
        data = _load_json(p)
        registered = bool(data and isinstance(data.get("mcpServers"), dict) and "genops" in data["mcpServers"])
        state = "registered" if registered else "not registered"
        print(f"MCP ({kind:<11}): {p} [{state}]")
    return 0 if ok else 1


def uninstall(home: Path = GENOPS_HOME, dry_run: bool = False) -> int:
    """Remove global GenOps bundle, CLI wrappers, and MCP server entries."""
    for p, kind in _mcp_json_targets():
        if not p.exists():
            continue
        data = _load_json(p)
        if data and isinstance(data.get("mcpServers"), dict) and "genops" in data["mcpServers"]:
            if dry_run:
                print(f"[DRY-RUN] Remove genops MCP entry from {p} ({kind})")
            else:
                del data["mcpServers"]["genops"]
                _save_json(p, data)
                print(f"[OK] Removed genops MCP entry from {p}")

    for target in CLI_BIN_DIRS:
        if not target.is_dir():
            continue
        for fname in ("genops", "genops.cmd", "genops.ps1"):
            fp = target / fname
            if fp.exists():
                if dry_run:
                    print(f"[DRY-RUN] Remove CLI wrapper {fp}")
                else:
                    fp.unlink()
                    print(f"[OK] Removed CLI wrapper {fp}")

    if home.exists():
        if dry_run:
            print(f"[DRY-RUN] Remove bundle directory {home}")
        else:
            shutil.rmtree(home)
            print(f"[OK] Removed {home}")
    print("[SUCCESS] GenOps uninstalled.")
    return 0


def install(home: Path = GENOPS_HOME, dry_run: bool = False) -> int:
    src_agents = Path(__file__).resolve().parent.parent
    engine = engine_path(home)

    # 1. Bundle the engine + assets into a stable home, independent of the repo.
    copy_bundle(src_agents, home, dry_run=dry_run)
    if not dry_run:
        print(f"[OK] Bundled GenOps engine into {home}")

    # 2. Write the self-healing launchers.
    launchers = _write_launchers(home, engine, dry_run=dry_run)
    if not dry_run:
        print(f"[OK] Wrote self-healing launcher in {home / 'bin'}")

    # 3. CLI wrappers into directories that are already on PATH.
    _write_cli_wrappers(launchers, dry_run=dry_run)

    # 4. MCP registrations (JSON-based configs only).
    for path, kind in _mcp_json_targets():
        if not path.exists():
            continue
        data = _load_json(path)
        if data is None:
            continue
        if dry_run:
            print(f"[DRY-RUN] Register genops MCP ({kind}) in {path}")
            continue
        register_mcp(data, launchers, kind)
        _save_json(path, data)
        print(f"[OK] Configured genops MCP in {path}")

    if dry_run:
        print("\n[DRY-RUN] No files modified.")
        return 0

    # 5. Self-test: confirm the engine is intact and reachable.
    ok, message = _self_test(engine)
    if ok:
        print(f"[OK] {message}")
    else:
        logger.error("Self-test failed: %s", message)
        return 1

    print("\n[SUCCESS] GenOps installed across detected coding tools on this machine.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GenOps Global Installer & MCP Registrar")
    parser.add_argument("--home", type=Path, default=None, help="Install directory (default: $GENOPS_HOME, $XDG_DATA_HOME/genops, or ~/.genops)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--install", action="store_true", help="Install or upgrade GenOps globally (default)")
    group.add_argument("--uninstall", action="store_true", help="Remove GenOps global install and MCP registrations")
    group.add_argument("--status", action="store_true", help="Check installation and MCP registration status")
    args = parser.parse_args(argv)

    target_home = (args.home or _default_genops_home()).expanduser().resolve()
    if args.uninstall:
        return uninstall(home=target_home, dry_run=args.dry_run)
    if args.status:
        return status(home=target_home)
    return install(home=target_home, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
