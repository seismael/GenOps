import json
import os
import shutil
import sys
from pathlib import Path

def install():
    plugin_script = Path(r"C:\Users\firas\.gemini\config\plugins\genops\scripts\genops.py")
    
    # 1. Install CLI wrappers
    cmd_content = f'@echo off\npython "{plugin_script}" %*\n'
    ps1_content = f'& python "{plugin_script}" $args\n'
    sh_content = f'#!/usr/bin/env bash\npython "{plugin_script.as_posix()}" "$@"\n'

    for target in [Path(r"C:\Users\firas\go\bin"), Path(r"C:\Users\firas\AppData\Roaming\npm")]:
        if target.exists():
            (target / "genops.cmd").write_text(cmd_content, encoding="utf-8")
            (target / "genops.ps1").write_text(ps1_content, encoding="utf-8")
            (target / "genops").write_text(sh_content, encoding="utf-8")
            print(f"[OK] Installed global genops CLI wrapper in {target}")

    # 2. Update Claude Code
    claude_json = Path(r"C:\Users\firas\.claude.json")
    if claude_json.exists():
        with open(claude_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("mcpServers", {})
        data["mcpServers"]["genops"] = {
            "type": "stdio",
            "command": "python",
            "args": [str(plugin_script), "mcp"],
            "env": {}
        }
        with open(claude_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[OK] Configured genops MCP in .claude.json")

    # 3. Update OpenCode
    opencode_mcp = Path(r"C:\Users\firas\.config\opencode\mcp.json")
    if opencode_mcp.exists():
        with open(opencode_mcp, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("mcpServers", {})
        data["mcpServers"]["genops"] = {
            "command": "python",
            "args": [str(plugin_script), "mcp"]
        }
        with open(opencode_mcp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[OK] Configured genops MCP in OpenCode mcp.json")

    opencode_skills = Path(r"C:\Users\firas\.config\opencode\skills")
    if opencode_skills.exists():
        src_skills = Path(r"C:\Users\firas\.gemini\config\plugins\genops\skills")
        for s in src_skills.iterdir():
            if s.is_dir():
                dest = opencode_skills / s.name
                if not dest.exists():
                    shutil.copytree(s, dest)
        print("[OK] Copied GenOps skills into OpenCode skills directory")

    # 4. Update VS Code / Cline
    cline_mcp = Path(r"C:\Users\firas\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json")
    if cline_mcp.exists():
        with open(cline_mcp, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("mcpServers", {})
        data["mcpServers"]["genops"] = {
            "command": "python",
            "args": [str(plugin_script), "mcp"],
            "disabled": False,
            "autoApprove": [
                "genops_status", "genops_validate", "genops_verify", 
                "genops_drift", "genops_compact", "genops_report", "genops_rtm"
            ]
        }
        with open(cline_mcp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[OK] Configured genops MCP in VS Code / Cline")

    # 5. Gemini / Antigravity
    gemini_mcp = Path(r"C:\Users\firas\.gemini\config\mcp_config.json")
    if gemini_mcp.exists():
        with open(gemini_mcp, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("mcpServers", {})
        data["mcpServers"]["genops"] = {
            "command": "python",
            "args": [str(plugin_script), "mcp"]
        }
        with open(gemini_mcp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[OK] Configured genops MCP in Gemini mcp_config.json")

    print("\n[SUCCESS] GenOps successfully installed across all AI coding tools and environments on this machine!")

if __name__ == "__main__":
    install()
