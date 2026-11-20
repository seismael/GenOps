"""GenOps modular engine subpackage (pure Python 3.8+ standard library)."""

from __future__ import annotations

from .antidrift import AntiDriftService
from .sarif import SarifExporter
from .schema import JsonSchemaValidator
from .workspace import ExplainService, FederationService, WorkspaceService
from .yaml_parser import (
    SimpleYamlParser,
    _find_unquoted_colon,
    _split_unquoted,
    _unquote_scalar,
)

__all__ = [
    "AntiDriftService",
    "ExplainService",
    "FederationService",
    "JsonSchemaValidator",
    "SarifExporter",
    "SimpleYamlParser",
    "WorkspaceService",
    "_find_unquoted_colon",
    "_split_unquoted",
    "_unquote_scalar",
]
