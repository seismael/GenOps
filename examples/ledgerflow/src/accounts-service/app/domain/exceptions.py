"""Domain exception hierarchy formatted per IETF RFC 9457 Problem Details (ADR-002)."""

from __future__ import annotations

from typing import Any, Dict, Optional


class LedgerProblemError(Exception):
    """Base domain error serializable as RFC 9457 `application/problem+json`."""

    status_code: int = 400
    problem_type: str = "urn:ledgerflow:problem:domain-error"
    title: str = "Ledger Domain Error"
    error_code: str = "LEDGER_DOMAIN_ERROR"

    def __init__(self, detail: str, instance: Optional[str] = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.instance = instance

    def to_problem_details(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.problem_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "error_code": self.error_code,
        }
        if self.instance:
            payload["instance"] = self.instance
        return payload


class ValidationProblem(LedgerProblemError):
    status_code = 400
    problem_type = "urn:ledgerflow:problem:validation-error"
    title = "Invalid Request Parameter"
    error_code = "ACCOUNT_VALIDATION_ERROR"


class NotFoundProblem(LedgerProblemError):
    status_code = 404
    problem_type = "urn:ledgerflow:problem:not-found"
    title = "Resource Not Found"
    error_code = "RESOURCE_NOT_FOUND"


class ConflictProblem(LedgerProblemError):
    status_code = 409
    problem_type = "urn:ledgerflow:problem:conflict"
    title = "State or Resource Conflict"
    error_code = "ACCOUNT_CONFLICT"


class PolicyViolationProblem(LedgerProblemError):
    status_code = 422
    problem_type = "urn:ledgerflow:problem:policy-violation"
    title = "Ledger Policy Violation"
    error_code = "POLICY_VIOLATION"
