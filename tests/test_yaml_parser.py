"""
Test for embedded Zero-Dependency YAML Parser.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# Dynamically import genops.py from .agents/scripts/
GENOPS_SCRIPT_PATH = Path(__file__).resolve().parent.parent / ".agents" / "scripts" / "genops.py"
spec = importlib.util.spec_from_file_location("genops", str(GENOPS_SCRIPT_PATH))
genops = importlib.util.module_from_spec(spec)
sys.modules["genops"] = genops
spec.loader.exec_module(genops)


class TestSimpleYamlParser(unittest.TestCase):
    """Tests for zero-dependency YAML parsing."""

    def test_parse_structure_yaml(self) -> None:
        scaffold_path = Path(".agents/scaffolds/go-service/STRUCTURE.yaml")
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

        schema_path = Path(".agents/schemas/scaffold.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = genops.JsonSchemaValidator.validate(data, schema, "STRUCTURE.yaml")
        self.assertEqual(errors, [])

    def test_parse_all_scaffolds(self) -> None:
        schema_path = Path(".agents/schemas/scaffold.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for sf in Path(".agents/scaffolds").glob("*/STRUCTURE.yaml"):
            data = genops.ConfigManager.load_yaml(sf)
            errors = genops.JsonSchemaValidator.validate(data, schema, sf.as_posix())
            self.assertEqual(errors, [], f"Errors in {sf}: {errors}")

    def test_parse_genops_yaml(self) -> None:
        config_path = Path("genops.yaml")
        self.assertTrue(config_path.exists())
        data = genops.ConfigManager.load_yaml(config_path)

        self.assertIn("pipeline", data)
        self.assertIn("name", data["pipeline"])
        self.assertIn("stages", data["pipeline"])

        stages = data["pipeline"]["stages"]
        self.assertTrue(len(stages) >= 4)
        self.assertEqual(stages[0]["id"], "prd")

        schema_path = Path(".agents/schemas/genops.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = genops.JsonSchemaValidator.validate(data, schema, "genops.yaml")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
