"""Domain exception hierarchy formatted per IETF RFC 9457 Problem Details (ADR-002)."""

from __future__ import annotations

from typing import Any, Dict, Optional


class LedgerProblemError(Exception):
    """Base domain error serializable as RFC 9457 `application/problem+json`."""

    status_code: int = 400
    problem_type: str = "urn:ledgerflow:problem:domain-error"
    title: str = "Transaction Domain Error"
    error_code: str = "LEDGER_TRANSACTION_ERROR"

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
    title = "Invalid Transaction Request"
    error_code = "TRANSACTION_VALIDATION_ERROR"


class NotFoundProblem(LedgerProblemError):
    status_code = 404
    problem_type = "urn:ledgerflow:problem:not-found"
    title = "Ledger Resource Not Found"
    error_code = "RESOURCE_NOT_FOUND"


class ConflictProblem(LedgerProblemError):
    status_code = 409
    problem_type = "urn:ledgerflow:problem:conflict"
    title = "Ledger Conflict"
    error_code = "TRANSACTION_CONFLICT"


class IdempotencyConflictProblem(ConflictProblem):
    problem_type = "urn:ledgerflow:problem:idempotency-conflict"
    title = "Idempotency Key Payload Mismatch"
    error_code = "IDEMPOTENCY_KEY_CONFLICT"


class UnbalancedJournalProblem(LedgerProblemError):
    status_code = 422
    problem_type = "urn:ledgerflow:problem:unbalanced-journal"
    title = "Unbalanced Double-Entry Journal"
    error_code = "UNBALANCED_JOURNAL"


class PolicyViolationProblem(LedgerProblemError):
    status_code = 422
    problem_type = "urn:ledgerflow:problem:policy-violation"
    title = "Account LedgerPolicy Violation"
    error_code = "POLICY_VIOLATION"


class FrozenAccountProblem(LedgerProblemError):
    status_code = 422
    problem_type = "urn:ledgerflow:problem:account-not-active"
    title = "Account Not Active for Posting"
    error_code = "ACCOUNT_NOT_ACTIVE"
