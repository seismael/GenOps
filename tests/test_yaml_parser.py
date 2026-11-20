"""
Test for embedded Zero-Dependency YAML Parser.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# Dynamically import genops.py from .agents/scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent
GENOPS_SCRIPT_PATH = REPO_ROOT / ".agents" / "scripts" / "genops.py"
spec = importlib.util.spec_from_file_location("genops", str(GENOPS_SCRIPT_PATH))
assert spec is not None and spec.loader is not None
genops = importlib.util.module_from_spec(spec)
sys.modules["genops"] = genops
spec.loader.exec_module(genops)


class TestSimpleYamlParser(unittest.TestCase):
    """Tests for zero-dependency YAML parsing."""

    def test_parse_structure_yaml(self) -> None:
        scaffold_path = REPO_ROOT / ".agents" / "scaffolds" / "go-service" / "STRUCTURE.yaml"
        self.assertTrue(scaffold_path.exists())
        data = genops.ConfigManager.load_yaml(scaffold_path)

        self.assertIn("name", data)
        self.assertIn("templates", data)
        self.assertIn("entity_stubs", data)
        self.assertIn("directories", data)

        self.assertIsInstance(data["templates"], dict)
        self.assertIn("go.mod.template", data["templates"])
        self.assertEqual(data["templates"]["go.mod.template"], "{module_kebab}/go.mod")

        self.assertIsInstance(data["entity_stubs"], dict)
        self.assertIn("domain", data["entity_stubs"])
        self.assertEqual(data["entity_stubs"]["domain"], "internal/domain/{entity_snake}.go")

        schema_path = REPO_ROOT / ".agents" / "schemas" / "scaffold.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = genops.JsonSchemaValidator.validate(data, schema, "STRUCTURE.yaml")
        self.assertEqual(errors, [])

    def test_parse_all_scaffolds(self) -> None:
        schema_path = REPO_ROOT / ".agents" / "schemas" / "scaffold.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for sf in (REPO_ROOT / ".agents" / "scaffolds").glob("*/STRUCTURE.yaml"):
            data = genops.ConfigManager.load_yaml(sf)
            errors = genops.JsonSchemaValidator.validate(data, schema, sf.as_posix())
            self.assertEqual(errors, [], f"Errors in {sf}: {errors}")

    def test_parse_genops_yaml(self) -> None:
        config_path = REPO_ROOT / "genops.yaml"
        self.assertTrue(config_path.exists())
        data = genops.ConfigManager.load_yaml(config_path)

        self.assertIn("pipeline", data)
        self.assertIn("name", data["pipeline"])
        self.assertIn("stages", data["pipeline"])

        stages = data["pipeline"]["stages"]
        self.assertTrue(len(stages) >= 4)
        self.assertEqual(stages[0]["id"], "prd")

        schema_path = REPO_ROOT / ".agents" / "schemas" / "genops.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = genops.JsonSchemaValidator.validate(data, schema, "genops.yaml")
        self.assertEqual(errors, [])

    def test_simple_yaml_colons_quoted_commas_escapes_and_inline_maps(self) -> None:
        raw_yaml = """pipeline:
  name: "Verify \\"Needs ADR\\" #1" # trailing comment
  tags: ["auth, security", "core, api"]
  urls:
    - https://example.com:8080/api
    - "Step 1: Verify"
  matrix:
    - - a
      - b
  inline_map: {a: 1, b: two}
"""
        parsed = genops.SimpleYamlParser.parse(raw_yaml)
        pipe = parsed["pipeline"]
        self.assertEqual(pipe["name"], 'Verify "Needs ADR" #1')
        self.assertEqual(pipe["tags"], ["auth, security", "core, api"])
        self.assertEqual(pipe["urls"], ["https://example.com:8080/api", "Step 1: Verify"])
        self.assertEqual(pipe["matrix"], [["a", "b"]])
        self.assertEqual(pipe["inline_map"], {"a": 1, "b": "two"})

    def test_yaml12_block_scalars_nested_flow_collections_anchors_and_null_keys(self) -> None:
        raw_yaml = """defaults: &def
  timeout: 30
  retries: 3
literal_clip: |
  line 1 # not a comment
  line 2

literal_strip: |-
  alpha
  beta
folded_strip: >-
  first paragraph line 1
  first paragraph line 2

  second paragraph
flow_nested: {a: 1, b: [2, 3, {nested: "x:y"}], c: 'k:v'}
empty_key:
service:
  <<: *def
  name: billing
  alias_ref: *def
"""
        parsed = genops.SimpleYamlParser.parse(raw_yaml)
        self.assertEqual(parsed["literal_clip"], "line 1 # not a comment\nline 2\n")
        self.assertEqual(parsed["literal_strip"], "alpha\nbeta")
        self.assertEqual(
            parsed["folded_strip"],
            "first paragraph line 1 first paragraph line 2\nsecond paragraph",
        )
        self.assertEqual(
            parsed["flow_nested"],
            {"a": 1, "b": [2, 3, {"nested": "x:y"}], "c": "k:v"},
        )
        self.assertIsNone(parsed["empty_key"])
        self.assertEqual(parsed["service"]["timeout"], 30)
        self.assertEqual(parsed["service"]["retries"], 3)
        self.assertEqual(parsed["service"]["name"], "billing")
        self.assertEqual(parsed["service"]["alias_ref"], {"timeout": 30, "retries": 3})


if __name__ == "__main__":
    unittest.main()
