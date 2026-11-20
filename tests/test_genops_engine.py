"""
Unit and integration tests for GenOps Deterministic Pipeline Engine.
"""

import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Dynamically import genops.py from .agents/scripts/
GENOPS_SCRIPT_PATH = Path(__file__).resolve().parent.parent / ".agents" / "scripts" / "genops.py"
spec = importlib.util.spec_from_file_location("genops", str(GENOPS_SCRIPT_PATH))
assert spec is not None and spec.loader is not None
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

    def test_hash_directory_skips_build_artifacts(self) -> None:
        sub_dir = self.base_path / "mod"
        (sub_dir / "__pycache__").mkdir(parents=True)
        (sub_dir / "keep.py").write_text("x = 1\n", encoding="utf-8")
        (sub_dir / "__pycache__" / "keep.cpython-313.pyc").write_bytes(b"\x00\x01\x02\x03")

        _, file_hashes = genops.DeterministicHasher.hash_directory(sub_dir)
        self.assertIn("keep.py", file_hashes)
        self.assertNotIn("__pycache__/keep.cpython-313.pyc", file_hashes)


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

        with genops.StateLock(self.lock_path, timeout=0.5):
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

    def test_mcp_dispatch_ingest(self) -> None:
        (self.root_dir / "src" / "legacy-app").mkdir(parents=True)
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("genops_ingest", {"src": "src"})
        self.assertFalse(is_err)
        self.assertIn("Brownfield baseline LLD generated", out)

    def test_mcp_dispatch_unknown(self) -> None:
        server = genops.MCPServer(self.root_dir)
        out, is_err = server.dispatch("unknown_tool", {})
        self.assertTrue(is_err)
        self.assertIn("Unknown tool", out)


class TestProjectDiscovery(unittest.TestCase):
    """Tests for project-root discovery used by CLI and the MCP server."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        (self.root_dir / "genops.yaml").write_text("pipeline:\n  name: test\n  stages: []\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_is_genops_project(self) -> None:
        self.assertTrue(genops.is_genops_project(self.root_dir))
        sub = self.root_dir / "sub"
        sub.mkdir()
        self.assertFalse(genops.is_genops_project(sub))

    def test_discover_project_root_walks_up(self) -> None:
        nested = self.root_dir / "a" / "b"
        nested.mkdir(parents=True)
        self.assertEqual(genops.discover_project_root(nested).resolve(), self.root_dir.resolve())

    def test_discover_project_root_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as isolated_dir:
            stray = Path(isolated_dir) / "genops-stray-nothing"
            stray.mkdir(exist_ok=True)
            self.assertIsNone(genops.discover_project_root(stray))

    def test_mcp_resolve_root_prefers_explicit_project(self) -> None:
        server = genops.MCPServer(self.root_dir)
        server._capture_roots([{"uri": "file:///C:/somewhere/else"}])
        self.assertEqual(server._resolve_root().resolve(), self.root_dir.resolve())

    def test_mcp_resolve_root_prefers_client_roots_when_global(self) -> None:
        server = genops.MCPServer(root_dir=None)
        server._capture_roots([{"uri": self.root_dir.resolve().as_uri()}])
        self.assertEqual(server._resolve_root().resolve(), self.root_dir.resolve())


class TestAuditRemediationsAndGovernance(unittest.TestCase):
    """Comprehensive tests covering AUD-001 through AUD-065 fixes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.repo_root = Path(__file__).resolve().parent.parent

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_hasher_ignores_dotdirs_thumbs_and_normalizes_cr(self) -> None:
        (self.root_dir / "mod" / ".venv" / "lib").mkdir(parents=True)
        (self.root_dir / "mod" / "a.txt").write_bytes(b"a\rb\r\nc")
        (self.root_dir / "mod" / "b.txt").write_bytes(b"a\nb\nc")
        (self.root_dir / "mod" / "Thumbs.db").write_bytes(b"junk")
        (self.root_dir / "mod" / ".venv" / "lib" / "dep.py").write_text("x=1\n", encoding="utf-8")

        self.assertEqual(
            genops.DeterministicHasher.hash_file(self.root_dir / "mod" / "a.txt"),
            genops.DeterministicHasher.hash_file(self.root_dir / "mod" / "b.txt"),
        )
        _, f_hashes = genops.DeterministicHasher.hash_directory(self.root_dir / "mod")
        self.assertNotIn("Thumbs.db", f_hashes)
        self.assertFalse(any(".venv" in k for k in f_hashes))

    def test_markdown_table_skips_fences_and_escaped_pipes(self) -> None:
        md = """
```markdown
| Fake | Table |
|---|---|
| foo | bar |
```

| Type | Values |
|---|---|
| `Status` | `'DRAFT' | 'ACTIVE'` |
| Pipe | a \\| b |

| NotHeader |
| auth-service |
"""
        tables = genops.MarkdownTable.parse_tables(md)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0][0]["Type"], "`Status`")
        self.assertEqual(tables[0][0]["Values"], "`'DRAFT' | 'ACTIVE'`")
        self.assertEqual(tables[0][1]["Values"], "a | b")

    def test_markdown_frontmatter_handles_dashes_and_quoted_commas(self) -> None:
        doc = self.root_dir / "fm.md"
        doc.write_text("""---
id: PRD-001
title: "Part A --- Part B"
tags: ["auth, security", "core"]
---
# Body
---
Footer
""", encoding="utf-8")
        fm, body = genops.MarkdownParser.parse_frontmatter(doc)
        self.assertEqual(fm["title"], "Part A --- Part B")
        self.assertEqual(fm["tags"], ["auth, security", "core"])
        self.assertIn("# Body", body)

    def test_json_schema_validator_draft07_keywords(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "tag": {"const": "v2"},
                "code": {"type": "string", "minLength": 2, "maxLength": 4},
                "items": {"type": "array", "uniqueItems": True},
                "val": {"oneOf": [{"type": "integer"}, {"type": "string"}]},
            },
        }
        self.assertEqual(
            genops.JsonSchemaValidator.validate(
                {"tag": "v2", "code": "ab", "items": ["x", "y"], "val": 1}, schema
            ),
            [],
        )
        errs = genops.JsonSchemaValidator.validate(
            {"tag": "v1", "code": "a", "items": ["x", "x"], "val": True}, schema
        )
        self.assertTrue(any("const" in e for e in errs))
        self.assertTrue(any("minLength" in e for e in errs))
        self.assertTrue(any("duplicate" in e for e in errs))
        self.assertTrue(any("oneOf" in e for e in errs))

    def test_state_lifecycle_live_status_transitive_and_event_chain(self) -> None:
        for d in ["docs/prd", "docs/hld", "docs/adr"]:
            (self.root_dir / d).mkdir(parents=True)
        (self.root_dir / "genops.yaml").write_text("""pipeline:
  name: "Test Chain"
  stages:
    - id: prd
      name: "PRD"
      focus: "Reqs"
      requires: []
      outputs: ["docs/prd/"]
      next: ["hld"]
    - id: hld
      name: "HLD"
      focus: "Topo"
      requires: ["docs/prd/"]
      outputs: ["docs/hld/"]
      next: ["adr"]
    - id: adr
      name: "ADR"
      focus: "Dec"
      requires: ["docs/hld/"]
      outputs: ["docs/adr/"]
      next: []
""", encoding="utf-8")
        prd = self.root_dir / "docs" / "prd" / "PRD-001-auth.md"
        hld = self.root_dir / "docs" / "hld" / "HLD-001-auth.md"
        adr = self.root_dir / "docs" / "adr" / "ADR-001-jwt.md"
        prd.write_text("---\nid: PRD-001-auth\nstage: prd\ndomain: auth\nstatus: draft\n---\n# PRD\n", encoding="utf-8")
        hld.write_text("---\nid: HLD-001-auth\nstage: hld\ndomain: auth\nstatus: draft\nupstream_refs: [PRD-001-auth]\n---\n# HLD\n", encoding="utf-8")
        adr.write_text("---\nid: ADR-001-jwt\nstage: adr\ndomain: storage\nstatus: draft\nupstream_refs: [HLD-001-auth]\n---\n# ADR\n", encoding="utf-8")

        repo = genops.StateRepository(self.root_dir)
        # Zero-file rejection test
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        res = repo.record_stage("prd", actor="tester")
        self.assertEqual(res["state"], "approved")
        self.assertIn("status: approved", prd.read_text(encoding="utf-8"))

        repo.record_stage("hld", actor="tester")
        repo.record_stage("adr", actor="tester")
        self.assertIn("status: accepted", adr.read_text(encoding="utf-8"))
        self.assertEqual(repo.verify_event_chain(), [])

        # Unchanged re-record must not invalidate hld/adr
        res_same = repo.record_stage("prd", actor="tester")
        self.assertEqual(res_same["invalidated"], [])
        self.assertEqual(repo.load_state()["stages"]["adr"]["state"], "approved")

        # Direct unrecorded edit to prd flags prd, hld, adr as stale in live status
        prd.write_text("---\nid: PRD-001-auth\nstage: prd\ndomain: auth\nstatus: approved\n---\n# PRD UPDATED\n", encoding="utf-8")
        live = repo.compute_live_status()
        self.assertEqual(live["stages"]["prd"]["state"], "stale")
        self.assertEqual(live["stages"]["hld"]["state"], "stale")
        self.assertEqual(live["stages"]["adr"]["state"], "stale")
        self.assertIn("auth", live["stages"]["prd"]["affected_domains"])

        # Transitive invalidation persisted when prd is re-recorded
        res_changed = repo.record_stage("prd", actor="tester")
        self.assertEqual(set(res_changed["invalidated"]), {"hld", "adr"})
        saved = repo.load_state()
        self.assertEqual(saved["stages"]["adr"]["state"], "stale")

        # Event chain tamper detection
        ev_lines = repo.event_file.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(ev_lines[0])
        tampered["actor"] = "attacker"
        ev_lines[0] = json.dumps(tampered)
        repo.event_file.write_text("\n".join(ev_lines) + "\n", encoding="utf-8")
        self.assertTrue(len(repo.verify_event_chain()) > 0)

    def test_empty_stage_approval_rejected(self) -> None:
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "genops.yaml").write_text("pipeline:\n  name: T\n  stages:\n    - id: prd\n      name: P\n      focus: F\n      requires: []\n      outputs: ['docs/prd/']\n      next: []\n", encoding="utf-8")
        repo = genops.StateRepository(self.root_dir)
        with self.assertRaises(ValueError):
            repo.record_stage("prd")

    def test_lineage_check_rules_and_domain_context_slice(self) -> None:
        specs = [
            genops.SpecDocument("PRD-001-auth", "docs/prd/PRD-001-auth.md", "prd", "auth", "1.0.0", "approved", [], ["HLD-001-auth"], {"id": "PRD-001-auth", "stage": "prd", "status": "approved"}, "# Auth"),
            genops.SpecDocument("PRD-002-authoring", "docs/prd/PRD-002-authoring.md", "prd", "authoring", "1.0.0", "approved", [], [], {"id": "PRD-002-authoring", "stage": "prd", "status": "approved"}, "# Authoring"),
            genops.SpecDocument("HLD-001-auth", "docs/hld/HLD-001-auth.md", "hld", "auth", "1.0.0", "approved", ["PRD-001-auth"], ["LLD-001-auth"], {"id": "HLD-001-auth", "stage": "hld", "status": "approved"}, "# HLD Auth"),
            genops.SpecDocument("ADR-001-pg", "docs/architecture/ADR-001-pg.md", "adr", "storage", "1.0.0", "superseded", [], ["LLD-001-auth"], {"id": "ADR-001-pg", "stage": "adr", "status": "superseded"}, "# PG"),
            genops.SpecDocument("LLD-001-auth", "docs/lld/LLD-001-auth.md", "lld", "auth", "1.0.0", "approved", ["HLD-001-auth", "ADR-001-pg"], [], {"id": "LLD-001-auth", "stage": "lld", "status": "approved"}, "# LLD Auth"),
        ]
        # Superseded ADR with downstream ref must be flagged
        violations = genops.LineageGraphService.check_rules(specs)
        self.assertTrue(any("superseded" in v.lower() for v in violations))

        # Slice for `auth` must include transitive ADR-001-pg, exclude PRD-002-authoring, sorted PRD->HLD->ADR->LLD
        sliced = genops.LineageGraphService.slice_domain_context(specs, "auth")
        ids = [s.id for s in sliced]
        self.assertEqual(ids, ["PRD-001-auth", "HLD-001-auth", "ADR-001-pg", "LLD-001-auth"])

    def test_scaffolding_all_6_stacks_and_safety(self) -> None:
        import shutil
        import io
        shutil.copytree(self.repo_root / ".agents" / "scaffolds", self.root_dir / ".agents" / "scaffolds")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for sc in ["go-service", "go-library", "python-fastapi", "node-service", "rust-service", "react-vite"]:
                summary = genops.ScaffoldingService.scaffold_module(self.root_dir, f"demo-{sc}", sc, ["OrderItem"])
                self.assertTrue(len(summary["created"]) > 0)
        self.assertEqual(buf.getvalue(), "")

        go_dom = (self.root_dir / "src" / "demo-go-service" / "internal" / "domain" / "order_item.go").read_text(encoding="utf-8")
        go_test = (self.root_dir / "src" / "demo-go-service" / "internal" / "domain" / "order_item_test.go").read_text(encoding="utf-8")
        self.assertIn("type OrderItem struct", go_dom)
        self.assertNotIn("type OrderItem struct", go_test)
        self.assertIn("func TestOrderItem", go_test)

        html_index = (self.root_dir / "src" / "demo-react-vite" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div id="root"></div>', html_index)

        rust_main = (self.root_dir / "src" / "demo-rust-service" / "src" / "main.rs").read_text(encoding="utf-8")
        self.assertIn("mod domain;", rust_main)

        # Non-destructive default vs --force
        main_py = self.root_dir / "src" / "demo-python-fastapi" / "app" / "main.py"
        main_py.write_text("# custom route\n", encoding="utf-8")
        sum_skip = genops.ScaffoldingService.scaffold_module(self.root_dir, "demo-python-fastapi", "python-fastapi", ["OrderItem"], force=False)
        self.assertIn("src/demo-python-fastapi/app/main.py", sum_skip["skipped"])
        self.assertEqual(main_py.read_text(encoding="utf-8"), "# custom route\n")
        genops.ScaffoldingService.scaffold_module(self.root_dir, "demo-python-fastapi", "python-fastapi", ["OrderItem"], force=True)
        self.assertNotEqual(main_py.read_text(encoding="utf-8"), "# custom route\n")

        with self.assertRaises(ValueError):
            genops.ScaffoldingService.scaffold_module(self.root_dir, "../../escape", "go-service", ["Item"])

    def test_heading_rtm_report_wcag_print_and_brownfield_filtering(self) -> None:
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "hld").mkdir(parents=True)
        (self.root_dir / "docs" / "architecture").mkdir(parents=True)
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        (self.root_dir / "src" / "orders").mkdir(parents=True)
        (self.root_dir / "genops.yaml").write_text((self.repo_root / "genops.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        (self.root_dir / "docs" / "prd" / "PRD-001-orders.md").write_text("""---
id: PRD-001-orders
domain: orders
stage: prd
status: approved
downstream_refs: [HLD-001-orders]
---
### US-001-01: Checkout Flow
* **Story:** As a buyer, I want checkout.
* **Priority:** `P1`
""", encoding="utf-8")
        (self.root_dir / "docs" / "hld" / "HLD-001-orders.md").write_text("---\nid: HLD-001-orders\nstage: hld\nstatus: approved\nupstream_refs: [PRD-001-orders]\ndownstream_refs: [LLD-001-orders]\n---\n# HLD\n", encoding="utf-8")
        (self.root_dir / "docs" / "lld" / "LLD-001-orders.md").write_text("---\nid: LLD-001-orders\nstage: lld\nstatus: approved\nupstream_refs: [HLD-001-orders]\ndownstream_refs: []\n---\n### Modules\n| Module | Scaffold | Entities | Description |\n|---|---|---|---|\n| orders | python-fastapi | Order | Order module |\n", encoding="utf-8")

        specs = genops.MarkdownParser.collect_specs(self.root_dir)
        rtm = genops.TraceabilityService.build_rtm(specs)
        self.assertEqual(len(rtm), 1)
        self.assertEqual(rtm[0]["priority"], "P1")
        self.assertIn("HLD-001-orders", rtm[0]["downstream"])
        self.assertIn("LLD-001-orders", rtm[0]["downstream"])

        report_out = self.root_dir / "docs" / "report.html"
        genops.ReportService.generate_html_report(self.root_dir, report_out)
        html_txt = report_out.read_text(encoding="utf-8")
        self.assertIn('<th scope="col">', html_txt)
        self.assertIn("@media print", html_txt)
        self.assertIn("US-001-01", html_txt)

        # Brownfield filter ignores non-source & boilerplate files and respects --force
        (self.root_dir / "src" / "orders" / "__init__.py").write_text("", encoding="utf-8")
        (self.root_dir / "src" / "orders" / "order.py").write_text("class Order: pass\n", encoding="utf-8")
        (self.root_dir / "docs" / "lld" / "LLD-001-brownfield-baseline.md").write_text("# existing", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            genops.BrownfieldIngestionService.ingest_codebase(self.root_dir, "src", force=False)
        _, mod_cnt = genops.BrownfieldIngestionService.ingest_codebase(self.root_dir, "src", force=True)
        self.assertEqual(mod_cnt, 1)
        bf_txt = (self.root_dir / "docs" / "lld" / "LLD-001-brownfield-baseline.md").read_text(encoding="utf-8")
        self.assertIn("`Order`", bf_txt)
        self.assertNotIn("Init", bf_txt)

    def test_cli_json_root_and_exit_codes(self) -> None:
        script = str(GENOPS_SCRIPT_PATH)
        ok_proc = subprocess.run(
            [sys.executable, script, "--root", str(self.repo_root), "--json", "status"],
            capture_output=True, text=True,
        )
        self.assertEqual(ok_proc.returncode, 0, ok_proc.stderr)
        payload = json.loads(ok_proc.stdout)
        self.assertIn("stages", payload)
        self.assertIn("next_action", payload)

        # Non-GenOps git directory must fail with exit code 2
        (self.root_dir / ".git").mkdir()
        err_proc = subprocess.run(
            [sys.executable, script, "status"],
            cwd=str(self.root_dir), capture_output=True, text=True,
        )
        self.assertEqual(err_proc.returncode, 2)

    def test_mcp_protocol_jsonrpc_notifications_content_length_and_capabilities(self) -> None:
        import io
        import shutil
        shutil.copytree(self.repo_root / ".agents" / "schemas", self.root_dir / ".agents" / "schemas")
        shutil.copytree(self.repo_root / ".agents" / "presets", self.root_dir / ".agents" / "presets")
        shutil.copytree(self.repo_root / ".agents" / "templates", self.root_dir / ".agents" / "templates")
        shutil.copytree(self.repo_root / ".agents" / "scaffolds", self.root_dir / ".agents" / "scaffolds")
        shutil.copytree(self.repo_root / ".agents" / "skills", self.root_dir / ".agents" / "skills")
        shutil.copy2(self.repo_root / "genops.yaml", self.root_dir / "genops.yaml")
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "src").mkdir(parents=True)

        # Tool annotations
        server = genops.MCPServer(self.root_dir)
        for tool in server.TOOLS_SPEC:
            self.assertIn("annotations", tool)
            self.assertFalse(tool["annotations"]["openWorldHint"])

        # Path traversal guards
        _, is_err = server.dispatch("genops_hash", {"target": "../../etc/passwd"})
        self.assertTrue(is_err)
        _, is_err2 = server.dispatch("genops_report", {"html": "../outside.html"})
        self.assertTrue(is_err2)

        # Stdio JSON-RPC: malformed JSON (-32700), notification silence, Content-Length, -32602, resources/prompts
        init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        framed = f"Content-Length: {len(init_req)}\r\n\r\n{init_req}"
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled"}) + "\n"
        bad_params = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "genops_impact", "arguments": {}}}) + "\n"
        res_list = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "resources/list"}) + "\n"
        pr_list = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "prompts/list"}) + "\n"
        stream_in = io.StringIO("not-json\n" + framed + notif + bad_params + res_list + pr_list)
        stream_out = io.StringIO()
        server.run(stdin=stream_in, stdout=stream_out)

        responses = [json.loads(ln) for ln in stream_out.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(responses), 5)  # Notification produced NO reply
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[1]["id"], 1)
        self.assertIn("resources", responses[1]["result"]["capabilities"])
        self.assertIn("prompts", responses[1]["result"]["capabilities"])
        self.assertEqual(responses[2]["id"], 2)
        self.assertEqual(responses[2]["error"]["code"], -32602)
        self.assertEqual(responses[3]["id"], 3)
        self.assertTrue(any(r["uri"] == "genops://context" for r in responses[3]["result"]["resources"]))
        self.assertEqual(responses[4]["id"], 4)
        self.assertTrue(len(responses[4]["result"]["prompts"]) >= 5)

    def test_examples_pass_all_governance_gates(self) -> None:
        for example_name in ["url-shortener", "url-shortener-cluster", "ledgerflow", "pulsegate"]:
            ex_root = self.repo_root / "examples" / example_name
            specs = genops.MarkdownParser.collect_specs(ex_root)
            self.assertEqual(genops.LineageGraphService.check_rules(specs, ex_root), [], f"Rule violations in {example_name}")
            self.assertEqual(genops.AntiDriftService.check_drift(ex_root), [], f"Drift in {example_name}")
            rtm = genops.TraceabilityService.build_rtm(specs)
            self.assertTrue(len(rtm) >= 3, f"Expected >= 3 RTM rows in {example_name}, got {len(rtm)}")

        for full_ex in ["ledgerflow", "pulsegate"]:
            ex_doc = genops._collect_doctor(self.repo_root / "examples" / full_ex)
            self.assertTrue(ex_doc["healthy"], ex_doc)
            self.assertTrue(ex_doc["next_action"])

    def test_bundled_asset_fallback_single_service_ingest_and_report_kpis(self) -> None:
        import shutil
        shutil.copy2(self.repo_root / ".agents" / "presets" / "software-spec.yaml", self.root_dir / "genops.yaml")
        (self.root_dir / "docs" / "prd").mkdir(parents=True)
        (self.root_dir / "docs" / "hld").mkdir(parents=True)
        (self.root_dir / "docs" / "architecture").mkdir(parents=True)
        (self.root_dir / "docs" / "lld").mkdir(parents=True)

        # Subproject without local .agents/ must resolve bundled assets cleanly
        self.assertEqual(genops._resolve_asset_dir(self.root_dir, "scaffolds"), self.repo_root / ".agents" / "scaffolds")
        declared = genops.LineageGraphService.get_declared_rules(self.root_dir)
        self.assertEqual(len(declared), 5)

        doc_report = genops._collect_doctor(self.root_dir)
        self.assertTrue(doc_report["healthy"], doc_report)
        self.assertIn("/genops-prd", doc_report["next_action"])

        # Single-service layer layout (domain, services, ports) folds into one module
        (self.root_dir / "src" / "domain").mkdir(parents=True)
        (self.root_dir / "src" / "services").mkdir(parents=True)
        (self.root_dir / "src" / "ports").mkdir(parents=True)
        (self.root_dir / "src" / "domain" / "invoice.py").write_text("class Invoice: pass\n", encoding="utf-8")
        (self.root_dir / "src" / "services" / "billing_service.py").write_text("pass\n", encoding="utf-8")
        _, mod_count = genops.BrownfieldIngestionService.ingest_codebase(self.root_dir, "src")
        self.assertEqual(mod_count, 1)
        bf_lld = (self.root_dir / "docs" / "lld" / "LLD-001-brownfield-baseline.md").read_text(encoding="utf-8")
        self.assertIn("`Invoice`", bf_lld)

        # HTML report surfaces RTM Coverage % and Next Step banner
        rep_path = self.root_dir / "docs" / "report.html"
        genops.ReportService.generate_html_report(self.root_dir, rep_path)
        html_out = rep_path.read_text(encoding="utf-8")
        self.assertIn("RTM Coverage", html_out)
        self.assertIn("Next Step:", html_out)

    def test_multi_domain_context_isolation_and_audit_failure_events(self) -> None:
        import shutil
        specs = [
            genops.SpecDocument("PRD-001-accounts", "docs/prd/PRD-001-accounts.md", "prd", "accounts", "1.0.0", "approved", [], ["HLD-001-accounts"], {"id": "PRD-001-accounts", "stage": "prd", "status": "approved"}, "# Accounts PRD"),
            genops.SpecDocument("PRD-002-transactions", "docs/prd/PRD-002-transactions.md", "prd", "transactions", "1.0.0", "approved", [], ["HLD-002-transactions"], {"id": "PRD-002-transactions", "stage": "prd", "status": "approved"}, "# Transactions PRD"),
            genops.SpecDocument("HLD-001-accounts", "docs/hld/HLD-001-accounts.md", "hld", "accounts", "1.0.0", "approved", ["PRD-001-accounts"], ["ADR-001-db", "LLD-001-accounts"], {"id": "HLD-001-accounts", "stage": "hld", "status": "approved"}, "# Accounts HLD"),
            genops.SpecDocument("HLD-002-transactions", "docs/hld/HLD-002-transactions.md", "hld", "transactions", "1.0.0", "approved", ["PRD-002-transactions"], ["ADR-001-db", "LLD-002-transactions"], {"id": "HLD-002-transactions", "stage": "hld", "status": "approved"}, "# Transactions HLD"),
            genops.SpecDocument("ADR-001-db", "docs/architecture/ADR-001-db.md", "adr", "core", "1.0.0", "accepted", ["HLD-001-accounts", "HLD-002-transactions"], ["LLD-001-accounts", "LLD-002-transactions"], {"id": "ADR-001-db", "stage": "adr", "status": "accepted"}, "# Shared DB ADR"),
            genops.SpecDocument("LLD-001-accounts", "docs/lld/LLD-001-accounts.md", "lld", "accounts", "1.0.0", "approved", ["HLD-001-accounts", "ADR-001-db"], [], {"id": "LLD-001-accounts", "stage": "lld", "status": "approved"}, "# Accounts LLD"),
            genops.SpecDocument("LLD-002-transactions", "docs/lld/LLD-002-transactions.md", "lld", "transactions", "1.0.0", "approved", ["HLD-002-transactions", "ADR-001-db"], [], {"id": "LLD-002-transactions", "stage": "lld", "status": "approved"}, "# Transactions LLD"),
        ]
        sliced_ids = [s.id for s in genops.LineageGraphService.slice_domain_context(specs, "accounts")]
        self.assertEqual(sliced_ids, ["PRD-001-accounts", "HLD-001-accounts", "ADR-001-db", "LLD-001-accounts"])

        # MCP failure gate calls emit VALIDATE_FAILED / DRIFT_DETECTED into hash-chained log
        shutil.copy2(self.repo_root / "genops.yaml", self.root_dir / "genops.yaml")
        (self.root_dir / "docs" / "lld").mkdir(parents=True)
        (self.root_dir / "src").mkdir(parents=True)
        (self.root_dir / "docs" / "lld" / "LLD-001-mod.md").write_text(
            "---\nid: LLD-001-mod\ndomain: mod\nstage: lld\nversion: 1.0.0\nstatus: approved\n---\n\n### Modules\n| Module | Scaffold | Entities | Description |\n|---|---|---|---|\n| billing | python-fastapi | Invoice | Billing |\n",
            encoding="utf-8",
        )
        server = genops.MCPServer(self.root_dir)
        _, is_drift_err = server.dispatch("genops_drift", {})
        self.assertTrue(is_drift_err)
        (self.root_dir / "genops.yaml").write_text("pipeline: {}\n", encoding="utf-8")
        _, is_val_err = server.dispatch("genops_validate", {})
        self.assertTrue(is_val_err)
        ev_lines = [json.loads(ln) for ln in (self.root_dir / "docs" / ".genops-events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        actions = [e["action"] for e in ev_lines]
        self.assertIn("DRIFT_DETECTED", actions)
        self.assertIn("VALIDATE_FAILED", actions)
        self.assertEqual(genops.StateRepository(self.root_dir).verify_event_chain(), [])

        # Real git repo attaches short SHA in git_commit field
        repo_ev = genops.StateRepository(self.repo_root)._last_event_hash()
        self.assertTrue(isinstance(repo_ev, str))
        sha = genops._git_head_short(self.repo_root)
        if sha:
            subprocess.run(["git", "init"], cwd=str(self.root_dir), capture_output=True, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=t@e.st", "commit", "--allow-empty", "-m", "init"], cwd=str(self.root_dir), capture_output=True, check=True)
            ev_with_git = genops.StateRepository(self.root_dir).append_event("INIT", "pipeline", "user")
            self.assertIn("git_commit", ev_with_git)
            self.assertEqual(genops.StateRepository(self.root_dir).verify_event_chain(), [])

    def test_cli_subcommands_exit_codes_json_logging_no_color_and_empty_entity_map(self) -> None:
        empty_map = genops.ScaffoldingService.build_casing_map("auth-svc", "")
        self.assertEqual(empty_map["entity"], "AuthSvc")
        self.assertEqual(empty_map["entity_snake"], "auth_svc")

        script = str(GENOPS_SCRIPT_PATH)
        ledger = str(self.repo_root / "examples" / "ledgerflow")

        for subcmd in [
            ["--json", "validate"],
            ["--json", "doctor"],
            ["--json", "check-rules"],
            ["--json", "drift"],
            ["--json", "rtm"],
            ["--json", "impact", "PRD-001-accounts"],
        ]:
            proc = subprocess.run([sys.executable, script, "--root", ledger, *subcmd], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, (subcmd, proc.stderr))
            parsed = json.loads(proc.stdout)
            if subcmd[1] == "doctor":
                self.assertTrue(parsed["healthy"])
            elif subcmd[1] == "check-rules":
                self.assertTrue(parsed["passed"])
                self.assertEqual(len(parsed["declared_rules"]), 5)

        # CLI `record nonexistent-stage` exits cleanly with code 2 and zero Python traceback
        bad_rec = subprocess.run([sys.executable, script, "--root", ledger, "record", "nonexistent-stage"], capture_output=True, text=True)
        self.assertEqual(bad_rec.returncode, 2)
        self.assertIn("[ERROR]", bad_rec.stderr)
        self.assertNotIn("Traceback", bad_rec.stderr)

        # --verbose --log-format json emits valid structured JSON log lines to stderr, NO_COLOR suppresses ANSI codes
        env = dict(os.environ, NO_COLOR="1")
        env.pop("FORCE_COLOR", None)
        v_proc = subprocess.run(
            [sys.executable, script, "--root", ledger, "--verbose", "--log-format", "json", "status"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(v_proc.returncode, 0, v_proc.stderr)
        self.assertNotIn("\033[", v_proc.stdout)
        stderr_lines = [ln for ln in v_proc.stderr.splitlines() if ln.strip()]
        self.assertTrue(len(stderr_lines) >= 1)
        log_obj = json.loads(stderr_lines[0])
        self.assertEqual(log_obj["level"], "DEBUG")
        self.assertIn("status", log_obj["message"])

        # CLI `demo` runs isolated inside self.root_dir (initialized with copied scaffolds)
        import shutil
        shutil.copytree(self.repo_root / ".agents" / "scaffolds", self.root_dir / ".agents" / "scaffolds")
        demo_proc = subprocess.run(
            [sys.executable, script, "--root", str(self.root_dir), "demo", "--scaffold", "python-fastapi", "--module", "demo-py", "--entities", "Ping"],
            capture_output=True, text=True,
        )
        self.assertEqual(demo_proc.returncode, 0, demo_proc.stderr)
        self.assertFalse((self.root_dir / ".genops-demo").exists())

    def test_phase2_aud066_to_aud078_comprehensive_verification(self) -> None:
        import io
        import shutil

        # 1. AUD-066: Markdown frontmatter supports YAML 1.2 block scalars, nested flow collections, and null keys
        fm_doc = self.root_dir / "block_fm.md"
        fm_doc.write_text(
            "---\n"
            "id: PRD-099-block\n"
            "stage: prd\n"
            "status: approved\n"
            "summary: |-\n"
            "  Multi-line frontmatter summary\n"
            "  with # hash preserved\n"
            "meta: {owner: team-a, tags: [core, v2]}\n"
            "optional_note:\n"
            "---\n"
            "# Body\n",
            encoding="utf-8",
        )
        fm_data, _ = genops.MarkdownParser.parse_frontmatter(fm_doc)
        self.assertEqual(fm_data["summary"], "Multi-line frontmatter summary\nwith # hash preserved")
        self.assertEqual(fm_data["meta"], {"owner": "team-a", "tags": ["core", "v2"]})
        self.assertIsNone(fm_data["optional_note"])

        # 2. AUD-067: Full JSON Schema Draft-07 ($ref, minProperties, maxProperties, exclusiveMin/Max, multipleOf, not, patternProperties, dependencies, format)
        self.assertEqual(genops._UNSUPPORTED_SCHEMA_KEYWORDS, set())
        full_schema = {
            "definitions": {
                "positiveEven": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 100, "multipleOf": 0.5}
            },
            "type": "object",
            "minProperties": 2,
            "maxProperties": 5,
            "not": {"required": ["forbidden"]},
            "properties": {
                "score": {"$ref": "#/definitions/positiveEven"},
                "created": {"type": "string", "format": "date-time"},
                "credit_card": {"type": "string"},
            },
            "patternProperties": {"^x-": {"type": "string", "minLength": 2}},
            "dependencies": {"credit_card": ["billing_address"]},
            "additionalProperties": False,
        }
        valid_payload = {
            "score": 12.5,
            "created": "2026-11-20T15:00:00Z",
            "x-trace": "ok",
        }
        self.assertEqual(genops.JsonSchemaValidator.validate(valid_payload, full_schema), [])
        bad_payload = {
            "score": 0,
            "created": "not-a-date",
            "credit_card": "4111",
            "x-trace": "a",
            "forbidden": True,
        }
        schema_errs = genops.JsonSchemaValidator.validate(bad_payload, full_schema)
        self.assertTrue(any("exclusiveMinimum" in e for e in schema_errs), schema_errs)
        self.assertTrue(any("date-time" in e for e in schema_errs), schema_errs)
        self.assertTrue(any("billing_address" in e for e in schema_errs), schema_errs)
        self.assertTrue(any("minLength" in e for e in schema_errs), schema_errs)
        self.assertTrue(any("not" in e for e in schema_errs), schema_errs)

        # 3. AUD-068 & AUD-069: Federated ext:// lineage, empty-upstream prerequisite rejection, TODO/template/Mermaid body lints, and record_stage gates
        proj_a = self.root_dir / "platform-core"
        proj_b = self.root_dir / "consumer-app"
        (proj_a / "docs" / "prd").mkdir(parents=True)
        (proj_a / "genops.yaml").write_text(
            (self.repo_root / "genops.yaml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (proj_a / "docs" / "prd" / "PRD-001-iam.md").write_text(
            "---\nid: PRD-001-iam\nstage: prd\ndomain: iam\nversion: 1.0.0\nstatus: approved\n---\n# IAM Core\n",
            encoding="utf-8",
        )
        for sub in ["docs/prd", "docs/hld", "docs/architecture", "docs/lld"]:
            (proj_b / sub).mkdir(parents=True)
        (proj_b / "genops.yaml").write_text(
            """pipeline:
  name: "Federated Pipeline"
  federation:
    remotes:
      - alias: core
        path: "../platform-core"
  stages:
    - id: prd
      name: "PRD"
      focus: "Reqs"
      requires: []
      outputs: ["docs/prd/"]
      next: ["hld"]
    - id: hld
      name: "HLD"
      focus: "Topo"
      requires: ["docs/prd/"]
      outputs: ["docs/hld/"]
      next: []
""",
            encoding="utf-8",
        )
        # Valid federated ref ext://core/PRD-001-iam satisfies HLD's requirement for stage 'prd'
        (proj_b / "docs" / "hld" / "HLD-001-app.md").write_text(
            "---\nid: HLD-001-app\nstage: hld\ndomain: app\nversion: 1.0.0\nstatus: approved\nupstream_refs: [ext://core/PRD-001-iam]\n---\n"
            "# App HLD\n```mermaid\nflowchart TD\n  A --> B\n```\n",
            encoding="utf-8",
        )
        b_specs = genops.MarkdownParser.collect_specs(proj_b)
        self.assertEqual(genops.LineageGraphService.check_rules(b_specs, proj_b), [])

        # Out-of-order record_stage("hld") when local docs/prd/ is empty must raise ValueError unless force=True
        repo_b = genops.StateRepository(proj_b)
        with self.assertRaises(ValueError):
            repo_b.record_stage("hld")

        # Unresolved TODO, template token {Domain}, and invalid mermaid diagram type must be caught by check_rules & record_stage
        (proj_b / "docs" / "prd" / "PRD-001-bad.md").write_text(
            "---\nid: PRD-001-bad\nstage: prd\ndomain: app\nversion: 1.0.0\nstatus: draft\n---\n"
            "# {Domain} Spec\nTODO: finish requirements\n```mermaid\nnotADiagramType TD\n```\n",
            encoding="utf-8",
        )
        bad_specs = genops.MarkdownParser.collect_specs(proj_b)
        rule_errs = genops.LineageGraphService.check_rules(bad_specs, proj_b)
        self.assertTrue(any("Unexpanded template token" in e for e in rule_errs), rule_errs)
        self.assertTrue(any("Unresolved placeholder" in e for e in rule_errs), rule_errs)
        self.assertTrue(any("Invalid Mermaid diagram type" in e for e in rule_errs), rule_errs)
        with self.assertRaises(ValueError):
            repo_b.record_stage("prd")

        # 4. AUD-070: AST symbol check, comment-stripped regex, reverse drift, and SQL contract drift
        drift_proj = self.root_dir / "drift-check"
        (drift_proj / "docs" / "lld").mkdir(parents=True)
        (drift_proj / "src" / "auth-svc").mkdir(parents=True)
        (drift_proj / "src" / "shadow-undeclared").mkdir(parents=True)
        (drift_proj / "docs" / "lld" / "LLD-001-auth.md").write_text(
            "---\nid: LLD-001-auth\nstage: lld\ndomain: auth\nstatus: approved\n---\n"
            "### Modules\n| Module | Scaffold | Entities | Description |\n|---|---|---|---|\n"
            "| auth-svc | python-fastapi | TokenClaim | Auth |\n\n"
            "```sql\nCREATE TABLE IF NOT EXISTS token_claims (id TEXT PRIMARY KEY);\nCREATE TABLE IF NOT EXISTS audit_trail (id TEXT PRIMARY KEY);\n```\n",
            encoding="utf-8",
        )
        # File matches name token_claim.py but only has a comment — AST check must flag missing symbol!
        (drift_proj / "src" / "auth-svc" / "token_claim.py").write_text(
            "# class TokenClaim: commented out!\nCREATE_SQL = 'CREATE TABLE token_claims (id TEXT)'\n",
            encoding="utf-8",
        )
        drifts = genops.AntiDriftService.check_drift(drift_proj)
        self.assertTrue(any("lacks AST/type symbol 'TokenClaim'" in d for d in drifts), drifts)
        self.assertTrue(any("Undeclared source module directory: src/shadow-undeclared/" in d for d in drifts), drifts)
        self.assertTrue(any("table 'audit_trail'" in d for d in drifts), drifts)

        # Adding real AST class, audit_trail DDL, and .genopsignore resolves all 3 drift classes
        (drift_proj / "src" / "auth-svc" / "token_claim.py").write_text(
            "class TokenClaim:\n    pass\nSQL = 'CREATE TABLE token_claims (id TEXT); CREATE TABLE audit_trail (id TEXT);'\n",
            encoding="utf-8",
        )
        (drift_proj / ".genopsignore").write_text("src/shadow-undeclared\n", encoding="utf-8")
        self.assertEqual(genops.AntiDriftService.check_drift(drift_proj), [])

        # 5. AUD-071: Multi-byte UTF-8 Content-Length framing + resources/templates/list + logging/setLevel
        utf8_req1 = json.dumps(
            {"jsonrpc": "2.0", "id": 10, "method": "resources/templates/list", "params": {"note": "stages: prd → hld — 日本語 🚀"}},
            ensure_ascii=False,
        )
        utf8_bytes_len = len(utf8_req1.encode("utf-8"))
        self.assertGreater(utf8_bytes_len, len(utf8_req1))
        utf8_req2 = json.dumps({"jsonrpc": "2.0", "id": 11, "method": "logging/setLevel", "params": {"level": "info"}})
        utf8_stream_in = io.StringIO(
            f"Content-Length: {utf8_bytes_len}\r\n\r\n{utf8_req1}"
            f"Content-Length: {len(utf8_req2.encode('utf-8'))}\r\n\r\n{utf8_req2}"
        )
        utf8_stream_out = io.StringIO()
        genops.MCPServer(proj_a).run(stdin=utf8_stream_in, stdout=utf8_stream_out)
        utf8_resps = [json.loads(ln) for ln in utf8_stream_out.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(utf8_resps), 2)
        self.assertEqual(utf8_resps[0]["id"], 10)
        self.assertEqual(
            utf8_resps[0]["result"]["resourceTemplates"][0]["uriTemplate"], "genops://spec/{id}"
        )
        self.assertEqual(utf8_resps[1]["id"], 11)

        # 6. AUD-075: Design & Research presets have validation_rules, preset-aware next_action, and RTM support
        design_proj = self.root_dir / "design-app"
        design_proj.mkdir()
        shutil.copy2(self.repo_root / ".agents" / "presets" / "design.yaml", design_proj / "genops.yaml")
        self.assertEqual(len(genops.LineageGraphService.get_declared_rules(design_proj)), 3)
        design_status = genops.StateRepository(design_proj).compute_live_status()
        self.assertIn("/genops-brief", design_status["next_action"])
        self.assertNotIn("genops demo", design_status["next_action"])
        (design_proj / "docs" / "brief").mkdir(parents=True)
        (design_proj / "docs" / "wireframes").mkdir(parents=True)
        (design_proj / "docs" / "brief" / "BRIEF-001-ui.md").write_text(
            "---\nid: BRIEF-001-ui\nstage: brief\ndomain: ui\nstatus: approved\ndownstream_refs: [WIRE-001-ui]\n---\n"
            "### GOAL-01: Accessible Checkout\n* **Priority:** `P0`\n",
            encoding="utf-8",
        )
        (design_proj / "docs" / "wireframes" / "WIRE-001-ui.md").write_text(
            "---\nid: WIRE-001-ui\nstage: wireframes\ndomain: ui\nstatus: approved\nupstream_refs: [BRIEF-001-ui]\n---\n# Wireframes\n",
            encoding="utf-8",
        )
        design_rtm = genops.TraceabilityService.build_rtm(genops.MarkdownParser.collect_specs(design_proj))
        self.assertEqual(len(design_rtm), 1)
        self.assertIn("WIRE-001-ui", design_rtm[0]["downstream"])

        # 7. AUD-076: O(1) tail seek & rotate_events with cryptographic checkpoint
        rot_repo = genops.StateRepository(proj_a)
        for idx in range(6):
            rot_repo.append_event("STEP", "prd", "tester", {"seq": idx})
        rot_res = rot_repo.rotate_events(max_events=2, actor="tester")
        self.assertTrue(rot_res["rotated"])
        self.assertEqual(rot_res["archived_count"], 4)
        self.assertEqual(rot_res["remaining_count"], 3)  # 1 checkpoint + 2 kept
        self.assertEqual(rot_repo.verify_event_chain(), [])

        # 8. AUD-078: SARIF 2.1.0 output, explain stage, and multi-project workspace status/doctor
        sarif_doc = genops.SarifExporter.build_sarif(
            genops.__version__, [{"rule_id": "GENOPS-DRIFT", "name": "drift", "errors": drifts, "warnings": []}]
        )
        self.assertEqual(sarif_doc["version"], "2.1.0")
        self.assertEqual(len(sarif_doc["runs"][0]["results"]), len(drifts))

        explained = genops.ExplainService.explain_stage(
            self.repo_root, "lld", genops.ConfigManager, genops.StateRepository, genops._resolve_asset_dir, genops._safe_rel
        )
        self.assertEqual(explained["id"], "lld")
        self.assertIn("docs/hld/", explained["requires"])

        ws_stat = genops.WorkspaceService.workspace_status(
            self.root_dir, genops.StateRepository, genops._safe_rel
        )
        self.assertEqual(ws_stat["project_count"], 3)


if __name__ == "__main__":
    unittest.main()
