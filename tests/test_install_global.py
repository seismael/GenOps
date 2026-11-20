"""
Unit tests for the GenOps global installer (install_global.py).

Focuses on the pure logic that governs the self-healing launcher and MCP
registration, without touching the real home directory or performing an
actual install.
"""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

INSTALL_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / ".agents" / "scripts" / "install_global.py"
)
spec = importlib.util.spec_from_file_location(
    "install_global", str(INSTALL_SCRIPT_PATH)
)
assert spec is not None and spec.loader is not None
install_global = importlib.util.module_from_spec(spec)
sys.modules["install_global"] = install_global
spec.loader.exec_module(install_global)


class TestLauncherTemplates(unittest.TestCase):
    def test_templates_do_not_bake_sys_executable(self):
        for template in (
            install_global._LAUNCHER_CMD,
            install_global._LAUNCHER_PS1,
            install_global._LAUNCHER_SH,
        ):
            self.assertNotIn("sys.executable", template, template)

    def test_templates_have_engine_placeholder(self):
        for template in (
            install_global._LAUNCHER_CMD,
            install_global._LAUNCHER_PS1,
            install_global._LAUNCHER_SH,
        ):
            self.assertIn("__ENGINE__", template, template)

    def test_launcher_contents_replaces_engine(self):
        out = install_global._launcher_contents(
            install_global._LAUNCHER_CMD, "C:\\home\\.genops\\scripts\\genops.py"
        )
        self.assertNotIn("__ENGINE__", out)
        self.assertIn('set "ENGINE=C:\\home\\.genops\\scripts\\genops.py"', out)

    def test_cmd_launcher_has_py_fallback(self):
        out = install_global._launcher_contents(
            install_global._LAUNCHER_CMD, "C:\\home\\genops.py"
        )
        self.assertIn("py -3", out)
        self.assertIn("python3", out)


class TestEnginePath(unittest.TestCase):
    def test_engine_path_is_stable_home(self):
        p = install_global.engine_path()
        self.assertEqual(p.name, "genops.py")
        self.assertTrue(str(p).replace("\\", "/").endswith(".genops/scripts/genops.py"))


class TestSelfTest(unittest.TestCase):
    def test_engine_present_with_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp) / "genops.py"
            engine.write_text(
                'subparsers.add_parser("mcp", help="...")\n', encoding="utf-8"
            )
            ok, message = install_global._self_test(engine)
            self.assertTrue(ok)
            self.assertIn("engine OK", message)

    def test_engine_missing(self):
        ok, message = install_global._self_test(Path("/nonexistent/genops.py"))
        self.assertFalse(ok)
        self.assertIn("engine missing", message)

    def test_engine_without_mcp_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp) / "genops.py"
            engine.write_text("print('hi')\n", encoding="utf-8")
            ok, message = install_global._self_test(engine)
            self.assertFalse(ok)
            self.assertIn("mcp", message)


class TestRegisterMcp(unittest.TestCase):
    def _launchers(self):
        return {
            "cmd": Path("C:/home/.genops/bin/genops.cmd"),
            "ps1": Path("C:/home/.genops/bin/genops.ps1"),
            "sh": Path("C:/home/.genops/bin/genops"),
        }

    def test_gemini_entry(self):
        data = {}
        install_global.register_mcp(data, self._launchers(), "gemini")
        entry = data["mcpServers"]["genops"]
        self.assertEqual(entry["args"], ["mcp"])
        self.assertIn("command", entry)
        self.assertNotIn("type", entry)

    def test_claude_entry_has_stdio(self):
        data = {}
        install_global.register_mcp(data, self._launchers(), "claude")
        entry = data["mcpServers"]["genops"]
        self.assertEqual(entry["type"], "stdio")
        self.assertEqual(entry["args"], ["mcp"])
        self.assertIn("env", entry)

    def test_cline_entry_has_autoapprove(self):
        data = {}
        install_global.register_mcp(data, self._launchers(), "cline")
        entry = data["mcpServers"]["genops"]
        self.assertFalse(entry["disabled"])
        self.assertIn("genops_status", entry["autoApprove"])

    def test_command_is_a_launcher_not_python(self):
        data = {}
        install_global.register_mcp(data, self._launchers(), "gemini")
        command = data["mcpServers"]["genops"]["command"]
        self.assertIn("genops", command)

    def test_cursor_windsurf_and_antigravity_registration(self):
        for kind in ("cursor", "windsurf", "antigravity"):
            data = {}
            install_global.register_mcp(data, self._launchers(), kind)
            self.assertEqual(data["mcpServers"]["genops"]["args"], ["mcp"])


class TestInstallerSafetyAndLifecycle(unittest.TestCase):
    def test_ps1_apostrophe_escaping_and_py38_probe(self):
        out = install_global._launcher_contents(
            install_global._LAUNCHER_PS1, "C:\\O'Malley\\.genops\\scripts\\genops.py", escape_ps1=True
        )
        self.assertIn("O''Malley", out)
        self.assertIn("(3, 8)", out)

    def test_corrupt_json_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "broken.json"
            cfg.write_text("{ invalid json,", encoding="utf-8")
            with mock.patch("install_global.logger") as mock_log:
                loaded = install_global._load_json(cfg)
            self.assertIsNone(loaded)
            mock_log.warning.assert_called_once()
            self.assertEqual(cfg.read_text(encoding="utf-8"), "{ invalid json,")

    def test_copy_bundle_cleans_stale_and_skips_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_agents = Path(tmp) / "src_agents"
            dest_home = Path(tmp) / "dest_home"
            (src_agents / "templates" / "__pycache__").mkdir(parents=True)
            (src_agents / "templates" / "__pycache__" / "x.pyc").write_bytes(b"123")
            (src_agents / "templates" / "keep.md").write_text("ok", encoding="utf-8")
            (dest_home / "templates").mkdir(parents=True)
            (dest_home / "templates" / "obsolete.md").write_text("old", encoding="utf-8")

            install_global.copy_bundle(src_agents, dest_home)
            self.assertTrue((dest_home / "templates" / "keep.md").exists())
            self.assertFalse((dest_home / "templates" / "obsolete.md").exists())
            self.assertFalse((dest_home / "templates" / "__pycache__").exists())

    def test_install_status_dry_run_and_uninstall_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "genops-home"
            fake_mcp_cfg = Path(tmp) / "cursor_mcp.json"
            fake_mcp_cfg.write_text('{"other": 1}\n', encoding="utf-8")
            with mock.patch("install_global._mcp_json_targets", return_value=[(fake_mcp_cfg, "cursor")]), \
                 mock.patch("install_global.CLI_BIN_DIRS", []):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc_dry = install_global.main(["--home", str(fake_home), "--dry-run"])
                self.assertEqual(rc_dry, 0)
                self.assertFalse(fake_home.exists())

                with contextlib.redirect_stdout(io.StringIO()):
                    rc_inst = install_global.main(["--home", str(fake_home), "--install"])
                    rc_stat = install_global.main(["--home", str(fake_home), "--status"])
                self.assertEqual(rc_inst, 0)
                self.assertEqual(rc_stat, 0)
                self.assertTrue((fake_home / "scripts" / "genops.py").is_file())
                self.assertIn("genops", fake_mcp_cfg.read_text(encoding="utf-8"))

                with contextlib.redirect_stdout(io.StringIO()):
                    rc_uninst = install_global.main(["--home", str(fake_home), "--uninstall"])
                self.assertEqual(rc_uninst, 0)
                self.assertFalse(fake_home.exists())
                self.assertNotIn("genops", fake_mcp_cfg.read_text(encoding="utf-8"))

    def test_default_home_respects_xdg_data_home_and_genops_home(self) -> None:
        orig_genops = os.environ.get("GENOPS_HOME")
        orig_xdg = os.environ.get("XDG_DATA_HOME")
        try:
            os.environ.pop("GENOPS_HOME", None)
            os.environ["XDG_DATA_HOME"] = "/tmp/xdg-custom"
            self.assertEqual(install_global._default_genops_home(), Path("/tmp/xdg-custom") / "genops")

            os.environ["GENOPS_HOME"] = "/tmp/genops-explicit"
            self.assertEqual(install_global._default_genops_home(), Path("/tmp/genops-explicit"))
        finally:
            if orig_genops is None:
                os.environ.pop("GENOPS_HOME", None)
            else:
                os.environ["GENOPS_HOME"] = orig_genops
            if orig_xdg is None:
                os.environ.pop("XDG_DATA_HOME", None)
            else:
                os.environ["XDG_DATA_HOME"] = orig_xdg

    def test_shell_cmd_ps1_escaping_neutralizes_metacharacters(self) -> None:
        sh_out = install_global._launcher_contents(
            install_global._LAUNCHER_SH, "/Users/dev$1`id`\"q's/.genops/scripts/genops.py"
        )
        self.assertIn("ENGINE='/Users/dev$1`id`\"q'\"'\"'s/.genops/scripts/genops.py'", sh_out)

        cmd_out = install_global._launcher_contents(
            install_global._LAUNCHER_CMD, 'C:\\Users\\%USERNAME%\\"evil"\\genops.py'
        )
        self.assertIn('set "ENGINE=C:\\Users\\%%USERNAME%%\\evil\\genops.py"', cmd_out)

        ps1_out = install_global._launcher_contents(
            install_global._LAUNCHER_PS1, "C:\\Users\\O'Brien$HOME\\genops.py"
        )
        self.assertIn("$engine = 'C:\\Users\\O''Brien$HOME\\genops.py'", ps1_out)


if __name__ == "__main__":
    unittest.main()
