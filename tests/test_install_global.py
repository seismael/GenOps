"""
Unit tests for the GenOps global installer (install_global.py).

Focuses on the pure logic that governs the self-healing launcher and MCP
registration, without touching the real home directory or performing an
actual install.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

INSTALL_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / ".agents" / "scripts" / "install_global.py"
)
spec = importlib.util.spec_from_file_location(
    "install_global", str(INSTALL_SCRIPT_PATH)
)
assert spec is not None and spec.loader is not None
install_global = importlib.util.module_from_spec(spec)
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


if __name__ == "__main__":
    unittest.main()
