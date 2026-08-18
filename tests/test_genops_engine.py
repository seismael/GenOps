"""
Unit and integration tests for GenOps Deterministic Pipeline Engine.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Dynamically import genops.py from .agents/scripts/
GENOPS_SCRIPT_PATH = Path(__file__).resolve().parent.parent / ".agents" / "scripts" / "genops.py"
spec = importlib.util.spec_from_file_location("genops", str(GENOPS_SCRIPT_PATH))
genops = importlib.util.module_from_spec(spec)
sys.modules["genops"] = genops
spec.loader.exec_module(genops)


class TestDeterministicHasher(unittest.TestCase):
    """Tests for DeterministicHasher and LF normalization."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normalize_lf(self) -> None:
        crlf_data = b"line1\r\nline2\r\nline3\r\n"
        lf_data = b"line1\nline2\nline3\n"
        self.assertEqual(genops.DeterministicHasher.normalize_lf(crlf_data), lf_data)

    def test_hash_file_lf_invariant(self) -> None:
        f_crlf = self.base_path / "crlf.txt"
        f_lf = self.base_path / "lf.txt"

        f_crlf.write_bytes(b"hello world\r\nnext line\r\n")
        f_lf.write_bytes(b"hello world\nnext line\n")

        hash_crlf = genops.DeterministicHasher.hash_file(f_crlf)
        hash_lf = genops.DeterministicHasher.hash_file(f_lf)

        self.assertEqual(hash_crlf, hash_lf)
        self.assertEqual(len(hash_crlf), 64)

    def test_hash_directory(self) -> None:
        sub_dir = self.base_path / "subdir"
        sub_dir.mkdir()
        (sub_dir / "a.md").write_text("# Doc A\n", encoding="utf-8")
        (sub_dir / "b.md").write_text("# Doc B\n", encoding="utf-8")

        comb_hash, file_hashes = genops.DeterministicHasher.hash_directory(sub_dir)
        self.assertTrue(bool(comb_hash))
        self.assertIn("a.md", file_hashes)
        self.assertIn("b.md", file_hashes)


class TestMerkleTree(unittest.TestCase):
    """Tests for MerkleTree root calculation."""

    def test_merkle_root_computation(self) -> None:
        hashes = {
            "a.md": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "b.md": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        }
        root = genops.MerkleTree.compute_root(hashes)
        self.assertTrue(bool(root))
        self.assertEqual(len(root), 64)

        # Same hashes in different order should yield identical root
        hashes_reversed = {
            "b.md": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "a.md": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
        root2 = genops.MerkleTree.compute_root(hashes_reversed)
        self.assertEqual(root, root2)

        # Empty map returns empty string
        self.assertEqual(genops.MerkleTree.compute_root({}), "")


class TestJsonSchemaValidator(unittest.TestCase):
    """Tests for zero-dependency JSON Schema Draft-07 validator."""

    def test_valid_schema(self) -> None:
        schema = {
            "type": "object",
            "required": ["name", "version", "stages"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string", "enum": ["1.0", "2.0"]},
                "count": {"type": "integer", "minimum": 1, "maximum": 100},
                "stages": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"}
                }
            }
        }
        data = {
            "name": "Pipeline",
            "version": "2.0",
            "count": 5,
            "stages": ["prd", "hld"]
        }
        errors = genops.JsonSchemaValidator.validate(data, schema)
        self.assertEqual(len(errors), 0)

    def test_invalid_schema_types_and_bounds(self) -> None:
        schema = {
            "type": "object",
            "required": ["name", "count"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "pattern": "^[a-z]+$"},
                "count": {"type": "integer", "minimum": 10},
            }
        }
        data = {
            "name": "INVALID_NAME",
            "count": 3,
            "extra_key": "not allowed"
        }
        errors = genops.JsonSchemaValidator.validate(data, schema)
        self.assertTrue(len(errors) >= 3)
        self.assertTrue(any("pattern" in e for e in errors))
        self.assertTrue(any("minimum" in e for e in errors))
        self.assertTrue(any("additional property" in e for e in errors))


class TestStateLock(unittest.TestCase):
    """Tests for atomic StateLock."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_path = Path(self.temp_dir.name) / ".genops.lock"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_lock_acquire_and_release(self) -> None:
        self.assertFalse(self.lock_path.exists())
        with genops.StateLock(self.lock_path, timeout=2.0) as lock:
            self.assertTrue(self.lock_path.exists())
            self.assertIsNotNone(lock.fd)
        self.assertFalse(self.lock_path.exists())

    def test_stale_lock_recovery(self) -> None:
        # Create an artificial stale lock with old mtime
        self.lock_path.write_text("stale", encoding="utf-8")
        old_time = os.path.getmtime(self.lock_path) - 100
        os.utime(self.lock_path, (old_time, old_time))

        with genops.StateLock(self.lock_path, timeout=0.5) as lock:
            self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.lock_path.exists())


class TestMarkdownTableAndParser(unittest.TestCase):
    """Tests for MarkdownTable AST parser and frontmatter extraction."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_markdown_tables(self) -> None:
        md = """# Title
Some text here.

| Module | Description | Entities |
|---|---|---|
| auth-service | Handles user authentication | User, Session, Token |
| billing-svc | Payment processing | Invoice, Subscription |

More text here.
"""
        tables = genops.MarkdownTable.parse_tables(md)
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]), 2)
        self.assertEqual(tables[0][0]["Module"], "auth-service")
        self.assertEqual(tables[0][1]["Entities"], "Invoice, Subscription")

    def test_parse_frontmatter(self) -> None:
        doc = self.base_path / "spec.md"
        doc.write_text("""---
id: PRD-001-auth
stage: prd
domain: auth
version: 1.0.0
status: approved
upstream_refs: []
downstream_refs: [HLD-001-auth]
---

# PRD Document
""", encoding="utf-8")

        fm, body = genops.MarkdownParser.parse_frontmatter(doc)
        self.assertEqual(fm["id"], "PRD-001-auth")
        self.assertEqual(fm["stage"], "prd")
        self.assertEqual(fm["status"], "approved")
        self.assertEqual(fm["downstream_refs"], ["HLD-001-auth"])
        self.assertIn("# PRD Document", body)


class TestScaffoldingService(unittest.TestCase):
    """Tests for casing transformations and path safety."""

    def test_split_words(self) -> None:
        self.assertEqual(genops.ScaffoldingService.split_words("auth-service"), ["auth", "service"])
        self.assertEqual(genops.ScaffoldingService.split_words("AuthService"), ["Auth", "Service"])
        self.assertEqual(genops.ScaffoldingService.split_words("auth_service_v2"), ["auth", "service", "v2"])

    def test_build_casing_map(self) -> None:
        casing = genops.ScaffoldingService.build_casing_map("order-processing", "PaymentTransaction")
        self.assertEqual(casing["module_kebab"], "order-processing")
        self.assertEqual(casing["module_snake"], "order_processing")
        self.assertEqual(casing["module_pascal"], "OrderProcessing")
        self.assertEqual(casing["entity_kebab"], "payment-transaction")
        self.assertEqual(casing["entity_snake"], "payment_transaction")
        self.assertEqual(casing["entity"], "PaymentTransaction")

    def test_is_safe_subpath(self) -> None:
        base = Path("/root/project/src")
        child = Path("/root/project/src/auth/service.go")
        escape = Path("/root/project/src/../../etc/passwd")

        self.assertTrue(genops.ScaffoldingService.is_safe_subpath(child, base))
        self.assertFalse(genops.ScaffoldingService.is_safe_subpath(escape, base))


class TestStateRepositoryAndGraph(unittest.TestCase):
    """Tests for StateRepository persistence, selective invalidation, and LineageGraph."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        # Setup minimal valid workspace
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "hld").mkdir(parents=True)
        (self.root_dir / "genops.yaml").write_text("""pipeline:
  name: "Test Pipeline"
  stages:
    - id: prd
      name: "PRD"
      requires: []
      outputs: ["docs/prd/"]
      next: ["hld"]
    - id: hld
      name: "HLD"
      requires: ["docs/prd/"]
      outputs: ["docs/hld/"]
      next: []
""", encoding="utf-8")

        (self.root_dir / "docs" / "prd" / "PRD-001.md").write_text("""---
id: PRD-001
stage: prd
domain: auth
version: 1.0.0
status: approved
upstream_refs: []
downstream_refs: [HLD-001]
---
# PRD
""", encoding="utf-8")

        (self.root_dir / "docs" / "hld" / "HLD-001.md").write_text("""---
id: HLD-001
stage: hld
domain: auth
version: 1.0.0
status: approved
upstream_refs: [PRD-001]
downstream_refs: []
---
# HLD
""", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_stage_and_load_state(self) -> None:
        repo = genops.StateRepository(self.root_dir)
        repo.record_stage("prd", actor="test-user")

        state = repo.load_state()
        self.assertIn("prd", state["stages"])
        self.assertEqual(state["stages"]["prd"]["state"], "approved")
        self.assertEqual(state["stages"]["prd"]["approved_by"], "test-user")
        self.assertTrue(bool(state["stages"]["prd"]["combined_hash"]))

        # Check event log
        event_file = self.root_dir / "docs" / ".genops-events.jsonl"
        self.assertTrue(event_file.exists())
        events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["stage"], "prd")

    def test_lineage_graph_and_rules(self) -> None:
        specs = genops.MarkdownParser.collect_specs(self.root_dir)
        self.assertEqual(len(specs), 2)

        graph = genops.LineageGraphService.generate_graph(specs)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["from"], "PRD-001")
        self.assertEqual(graph["edges"][0]["to"], "HLD-001")

        violations = genops.LineageGraphService.check_rules(specs)
        self.assertEqual(len(violations), 0)


class TestImpactSimulator(unittest.TestCase):
    """Tests for Change-Impact Simulator."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "hld").mkdir(parents=True)
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        (self.root_dir / "src" / "billing-svc").mkdir(parents=True)

        (self.root_dir / "docs" / "prd" / "PRD-001-billing.md").write_text("""---
id: PRD-001-billing
stage: prd
domain: billing
version: 1.0.0
status: approved
upstream_refs: []
downstream_refs: [HLD-001-billing]
---
# PRD
""", encoding="utf-8")

        (self.root_dir / "docs" / "hld" / "HLD-001-billing.md").write_text("""---
id: HLD-001-billing
stage: hld
domain: billing
version: 1.0.0
status: approved
upstream_refs: [PRD-001-billing]
downstream_refs: [LLD-001-billing]
---
# HLD
""", encoding="utf-8")

        (self.root_dir / "docs" / "lld" / "LLD-001-billing.md").write_text("""---
id: LLD-001-billing
stage: lld
domain: billing
version: 1.0.0
status: approved
upstream_refs: [HLD-001-billing]
downstream_refs: []
---
# LLD

### Modules
| Module | Scaffold | Entities | Description |
|---|---|---|---|
| billing-svc | go-service | Invoice, Payment | Core billing service |
""", encoding="utf-8")

        (self.root_dir / "src" / "billing-svc" / "invoice.go").write_text("package billing\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_impact_simulation(self) -> None:
        impact = genops.ImpactSimulator.simulate(self.root_dir, "PRD-001-billing")
        self.assertEqual(impact["target"]["id"], "PRD-001-billing")
        self.assertEqual(impact["downstream_specs_count"], 2)
        downstream_ids = [s["id"] for s in impact["downstream_specs"]]
        self.assertIn("HLD-001-billing", downstream_ids)
        self.assertIn("LLD-001-billing", downstream_ids)
        self.assertIn("billing-svc", impact["affected_modules"])
        self.assertIn("Invoice", impact["affected_entities"])
        self.assertIn("Payment", impact["affected_entities"])
        self.assertTrue(any("invoice.go" in f for f in impact["affected_source_files"]))


class TestServicesAndBrownfield(unittest.TestCase):
    """Tests for AntiDrift, Traceability, Report, and Brownfield Ingestion."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        (self.root_dir / "src" / "auth-svc").mkdir(parents=True)

        (self.root_dir / "docs" / "prd" / "PRD-001.md").write_text("""---
id: PRD-001
stage: prd
domain: auth
status: approved
---
# PRD
| User Story | I want to... | Priority |
|---|---|---|
| US-01 | Login securely | P0 |
""", encoding="utf-8")

        (self.root_dir / "docs" / "lld" / "LLD-001.md").write_text("""---
id: LLD-001
stage: lld
domain: auth
status: approved
---
# LLD
### Modules
| Module | Description | Entities |
|---|---|---|
| auth-svc | Auth service | UserSession |
""", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_anti_drift_check(self) -> None:
        # Initially missing entity stub
        drifts = genops.AntiDriftService.check_drift(self.root_dir)
        self.assertEqual(len(drifts), 1)
        self.assertIn("UserSession", drifts[0])

        # Add stub and verify drift resolves
        stub_file = self.root_dir / "src" / "auth-svc" / "user_session.go"
        stub_file.write_text("package auth\ntype UserSession struct {}\n", encoding="utf-8")

        drifts_resolved = genops.AntiDriftService.check_drift(self.root_dir)
        self.assertEqual(len(drifts_resolved), 0)

    def test_traceability_matrix(self) -> None:
        specs = genops.MarkdownParser.collect_specs(self.root_dir)
        rtm = genops.TraceabilityService.build_rtm(specs)
        self.assertEqual(len(rtm), 1)
        self.assertEqual(rtm[0]["prd"], "PRD-001")
        self.assertEqual(rtm[0]["priority"], "P0")

    def test_report_generation(self) -> None:
        report_file = self.root_dir / "docs" / "report.html"
        genops.ReportService.generate_html_report(self.root_dir, report_file)
        self.assertTrue(report_file.exists())
        content = report_file.read_text(encoding="utf-8")
        self.assertIn("GenOps Specification Pipeline & Audit Dashboard", content)

    def test_brownfield_ingestion(self) -> None:
        (self.root_dir / "src" / "payment-gateway").mkdir(parents=True)
        (self.root_dir / "src" / "payment-gateway" / "charge.go").write_text("package payment\n", encoding="utf-8")

        dest, count = genops.BrownfieldIngestionService.ingest_codebase(self.root_dir, "src")
        self.assertTrue(dest.exists())
        self.assertEqual(count, 2)
        content = dest.read_text(encoding="utf-8")
        self.assertIn("payment-gateway", content)


class TestContextCompactorAndCompilerVerifier(unittest.TestCase):
    """Tests for ContextCompactor and CompilerVerifier."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "adr").mkdir(parents=True)
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        (self.root_dir / "src" / "test-module").mkdir(parents=True)

        (self.root_dir / "docs" / "prd" / "PRD-001.md").write_text("""---
id: PRD-001
domain: e-commerce
stage: prd
status: approved
---
# PRD
| Persona | Role Description |
|---|---|
| Shopper | End user purchasing products online |
""", encoding="utf-8")

        (self.root_dir / "docs" / "adr" / "ADR-001.md").write_text("""---
id: ADR-001-postgres
domain: storage
stage: adr
status: accepted
---
# ADR-001
## 6. Downstream Directives
- Use UUIDv7 for all primary keys
- Encrypt PII at rest
""", encoding="utf-8")

        (self.root_dir / "docs" / "lld" / "LLD-001.md").write_text("""---
id: LLD-001
domain: checkout
stage: lld
status: approved
---
# LLD
### Modules
| Module | Scaffold | Entities | Description |
|---|---|---|---|
| checkout-svc | go-service | Cart, Order | Core checkout service |
""", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_context_compactor(self) -> None:
        ctx_file = genops.ContextCompactor.compact(self.root_dir)
        self.assertTrue(ctx_file.exists())
        content = ctx_file.read_text(encoding="utf-8")

        self.assertIn("Living Project Context", content)
        self.assertIn("Shopper", content)
        self.assertIn("ADR-001-postgres", content)
        self.assertIn("Use UUIDv7 for all primary keys", content)
        self.assertIn("`Cart`", content)
        self.assertIn("`Order`", content)

    def test_compiler_verifier(self) -> None:
        # Create valid python file
        py_file = self.root_dir / "src" / "test-module" / "valid.py"
        py_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

        res = genops.CompilerVerifier.verify_workspace(self.root_dir)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["errors"]), 0)


class TestMCPServer(unittest.TestCase):
    """Tests for MCP JSON-RPC Server dispatching."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "src").mkdir(parents=True)

        (self.root_dir / "genops.yaml").write_text("""pipeline:
  name: "MCP Test Pipeline"
  stages:
    - id: prd
      name: "PRD"
      focus: "Requirements"
      requires: []
      outputs: ["docs/prd/"]
      next: []
""", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_mcp_dispatch_validate_and_status(self) -> None:
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("genops_validate", {})
        self.assertFalse(is_err)
        self.assertIn("Valid", out)

        status_out, status_err = server.dispatch("genops_status", {})
        self.assertFalse(status_err)
        self.assertIn("stages", status_out)

    def test_mcp_dispatch_report_and_drift(self) -> None:
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("genops_report", {"html": "docs/report.html"})
        self.assertFalse(is_err)
        self.assertTrue((self.root_dir / "docs" / "report.html").exists())

        drift_out, drift_err = server.dispatch("genops_drift", {})
        self.assertFalse(drift_err)
        self.assertIn("Anti-Drift Gate", drift_out)

    def test_mcp_dispatch_compact_and_verify(self) -> None:
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("genops_compact", {})
        self.assertFalse(is_err)
        self.assertIn("Compacted living memory", out)

        v_out, v_err = server.dispatch("genops_verify", {})
        self.assertFalse(v_err)

    def test_mcp_dispatch_unknown(self) -> None:
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("unknown_tool", {})
        self.assertTrue(is_err)
        self.assertIn("Unknown tool", out)


if __name__ == "__main__":
    unittest.main()
