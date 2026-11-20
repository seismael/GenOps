"""OASIS Static Analysis Results Interchange Format (SARIF v2.1.0) exporter for GenOps governance gates."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class SarifExporter:
    """Formats GenOps validation, rule-check, anti-drift, and compiler errors into OASIS SARIF v2.1.0 JSON."""

    _BRACKET_PATH_RE = re.compile(r"^\[([^\]]+)\]\s*(.+)$")
    _INLINE_PATH_RE = re.compile(r"\b((?:docs|src|\.agents)/[A-Za-z0-9_./-]+|[A-Za-z0-9_.-]+\.(?:yaml|json|md))\b")

    @classmethod
    def _extract_location(cls, message: str) -> str:
        m = cls._BRACKET_PATH_RE.match(message.strip())
        if m:
            return m.group(1).strip()
        m2 = cls._INLINE_PATH_RE.search(message)
        if m2:
            return m2.group(1).strip().rstrip("/")
        return "genops.yaml"

    @classmethod
    def build_sarif(
        cls,
        version: str,
        gates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build an OASIS SARIF 2.1.0 payload from a list of {'rule_id', 'name', 'errors', 'warnings'} gates."""
        rules: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []

        for gate in gates:
            rule_id = str(gate.get("rule_id") or gate.get("name", "GENOPS001")).split()[0].upper()
            if not rule_id.startswith("GENOPS"):
                rule_id = f"GENOPS-{rule_id}"
            desc = str(gate.get("name", "GenOps governance gate"))
            rules.append({
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": desc},
            })

            for err in gate.get("errors", []):
                uri = cls._extract_location(str(err))
                results.append({
                    "ruleId": rule_id,
                    "level": "error",
                    "message": {"text": str(err)},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri},
                                "region": {"startLine": 1},
                            }
                        }
                    ],
                })

            for warn in gate.get("warnings", []):
                uri = cls._extract_location(str(warn))
                results.append({
                    "ruleId": rule_id,
                    "level": "warning",
                    "message": {"text": str(warn)},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri},
                                "region": {"startLine": 1},
                            }
                        }
                    ],
                })

        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "GenOps Deterministic Pipeline Engine",
                            "version": version,
                            "informationUri": "https://github.com/genops/genops",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }
