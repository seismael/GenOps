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

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Tuple

# Stable, agent-independent install root. Owned entirely by GenOps.
GENOPS_HOME = Path.home() / ".genops"
BIN_DIR = GENOPS_HOME / "bin"

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
]


# ---------------------------------------------------------------------------
# Launcher templates (self-healing interpreter resolution).
# ``__ENGINE__`` is replaced with the absolute engine script path.
# ---------------------------------------------------------------------------

_LAUNCHER_CMD = """@echo off
setlocal
set "ENGINE=__ENGINE__"
if "%~1"=="--self-test" goto selftest

python3 -c "import sys" >nul 2>nul
if errorlevel 1 goto try_python
python3 "%ENGINE%" %*
exit /b %errorlevel%

:try_python
python -c "import sys" >nul 2>nul
if errorlevel 1 goto try_py
python "%ENGINE%" %*
exit /b %errorlevel%

:try_py
py -3 -c "import sys" >nul 2>nul
if errorlevel 1 goto no_python
py -3 "%ENGINE%" %*
exit /b %errorlevel%

:no_python
echo [genops] No working Python interpreter found (tried python3, python, py -3). Install Python 3.8+ and retry. 1>&2
exit /b 1

:selftest
if not exist "%ENGINE%" (
  echo [genops] engine MISSING: %ENGINE% 1>&2
  exit /b 1
)
echo [genops] engine OK: %ENGINE%
python3 -c "import sys" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: python3 & exit /b 0 )
python -c "import sys" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: python & exit /b 0 )
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 ( echo [genops] interpreter OK: py -3 & exit /b 0 )
echo [genops] no working Python interpreter found 1>&2
exit /b 1
"""

_LAUNCHER_PS1 = """$ErrorActionPreference = 'SilentlyContinue'
$engine = '__ENGINE__'

if ($args.Count -gt 0 -and $args[0] -eq '--self-test') {
    if (-not (Test-Path -LiteralPath $engine)) {
        Write-Error "[genops] engine MISSING: $engine"
        exit 1
    }
    Write-Output "[genops] engine OK: $engine"
    foreach ($py in @('python3', 'python')) {
        & $py -c 'import sys' 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Output "[genops] interpreter OK: $py"; exit 0 }
    }
    & py -3 -c 'import sys' 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Output "[genops] interpreter OK: py -3"; exit 0 }
    Write-Error "[genops] no working Python interpreter found"
    exit 1
}

foreach ($py in @('python3', 'python')) {
    & $py -c 'import sys' 2>$null
    if ($LASTEXITCODE -eq 0) { & $py $engine @args; exit $LASTEXITCODE }
}
& py -3 -c 'import sys' 2>$null
if ($LASTEXITCODE -eq 0) { & py -3 $engine @args; exit $LASTEXITCODE }

Write-Error "[genops] No working Python interpreter found (tried python3, python, py -3). Install Python 3.8+ and retry."
exit 1
"""

_LAUNCHER_SH = """#!/usr/bin/env bash
set -u
ENGINE="__ENGINE__"

if [ "${1:-}" = "--self-test" ]; then
    if [ ! -f "$ENGINE" ]; then
        echo "[genops] engine MISSING: $ENGINE" >&2
        exit 1
    fi
    echo "[genops] engine OK: $ENGINE"
    for py in python3 python /usr/bin/python3 /usr/local/bin/python3; do
        if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys' >/dev/null 2>&1; then
            echo "[genops] interpreter OK: $py"
            exit 0
        fi
    done
    echo "[genops] no working Python interpreter found" >&2
    exit 1
fi

for py in python3 python /usr/bin/python3 /usr/local/bin/python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys' >/dev/null 2>&1; then
        exec "$py" "$ENGINE" "$@"
    fi
done

echo "[genops] No working Python interpreter found (tried python3, python)." >&2
exit 1
"""


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


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


def _set_mcp_server(data: dict, entry: dict) -> dict:
    """Register (or replace) the ``genops`` MCP server entry."""
    servers = data.setdefault("mcpServers", {})
    servers["genops"] = entry
    return data


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


def copy_bundle(src_agents: Path, dest_root: Path) -> None:
    """Copy the self-contained asset folders from ``.agents/`` into ``~/.genops/``."""
    for folder in ASSET_FOLDERS:
        src = src_agents / folder
        if not src.is_dir():
            continue
        shutil.copytree(src, dest_root / folder, dirs_exist_ok=True)


def engine_path(dest_root: Path = GENOPS_HOME) -> Path:
    """Return the absolute path to the installed engine script."""
    return dest_root / "scripts" / "genops.py"


def _launcher_contents(template: str, engine: str) -> str:
    return template.replace("__ENGINE__", engine)


def _write_launchers(dest_root: Path, engine: Path) -> Dict[str, Path]:
    """Write per-platform self-healing launchers into ``~/.genops/bin/``."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    launchers = {
        "cmd": BIN_DIR / "genops.cmd",
        "ps1": BIN_DIR / "genops.ps1",
        "sh": BIN_DIR / "genops",
    }
    launchers["cmd"].write_text(
        _launcher_contents(_LAUNCHER_CMD, str(engine)), encoding="utf-8"
    )
    launchers["ps1"].write_text(
        _launcher_contents(_LAUNCHER_PS1, str(engine)), encoding="utf-8"
    )
    launchers["sh"].write_text(
        _launcher_contents(_LAUNCHER_SH, engine.as_posix()), encoding="utf-8"
    )
    launchers["sh"].chmod(0o755)
    return launchers


def _write_cli_wrappers(launchers: Dict[str, Path]) -> int:
    """Install thin CLI wrappers into PATH directories that already exist."""
    installed = 0
    for target in CLI_BIN_DIRS:
        if not target.is_dir():
            continue
        (target / "genops.cmd").write_text(
            f'@echo off\ncall "{launchers["cmd"]}" %*\n', encoding="utf-8"
        )
        (target / "genops.ps1").write_text(
            f'& "{launchers["ps1"]}" @args\n', encoding="utf-8"
        )
        (target / "genops").write_text(
            f'#!/usr/bin/env bash\nexec "{launchers["sh"].as_posix()}" "$@"\n',
            encoding="utf-8",
        )
        installed += 1
        print(f"[OK] Installed genops CLI wrapper in {target}")
    if installed == 0:
        print(
            "[!] No standard bin directory found; skipping CLI wrappers.",
            file=sys.stderr,
        )
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
    else:  # gemini / antigravity
        entry = {"command": command, "args": ["mcp"]}
    _set_mcp_server(data, entry)


def install() -> int:
    src_agents = Path(__file__).resolve().parent.parent
    engine = engine_path()

    # 1. Bundle the engine + assets into a stable home, independent of the repo.
    copy_bundle(src_agents, GENOPS_HOME)
    print(f"[OK] Bundled GenOps engine into {GENOPS_HOME}")

    # 2. Write the self-healing launchers.
    launchers = _write_launchers(GENOPS_HOME, engine)
    print(f"[OK] Wrote self-healing launcher in {BIN_DIR}")

    # 3. CLI wrappers into directories that are already on PATH.
    _write_cli_wrappers(launchers)

    # 4. MCP registrations (JSON-based configs only).
    cline_settings = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Code"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json"
    )
    json_targets = [
        (Path.home() / ".claude.json", "claude"),
        (Path.home() / ".config" / "opencode" / "mcp.json", "opencode"),
        (Path.home() / ".gemini" / "config" / "mcp_config.json", "gemini"),
        (cline_settings, "cline"),
    ]
    for path, kind in json_targets:
        if not path.exists():
            continue
        data = _load_json(path)
        register_mcp(data, launchers, kind)
        _save_json(path, data)
        print(f"[OK] Configured genops MCP in {path}")

    # 5. Self-test: confirm the engine is intact and reachable.
    ok, message = _self_test(engine)
    if ok:
        print(f"[OK] {message}")
    else:
        print(f"[!] Self-test failed: {message}", file=sys.stderr)
        return 1

    print("\n[SUCCESS] GenOps installed across detected coding tools on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(install())
