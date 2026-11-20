"""Application entrypoint, RFC 9457 gateway facade, and FastAPI bootstrap for transactions-service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.container import TransactionsContainer
from app.domain.exceptions import LedgerProblemError


class TransactionsGateway:
    """Zero-dependency HTTP-status/RFC-9457 adapter for Transactions use cases."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.container = TransactionsContainer(db_path)

    def post_journal(
        self,
        idempotency_key: str,
        description: str,
        currency: str,
        lines: List[Dict[str, Any]],
        traceparent: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        try:
            entry, is_replay = self.container.journal_service.post_journal(
                idempotency_key=idempotency_key,
                description=description,
                currency=currency,
                lines=lines,
                traceparent=traceparent,
            )
            return (200 if is_replay else 201), entry.to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def reverse_journal(
        self,
        journal_id: str,
        idempotency_key: str,
        reason: str = "",
        traceparent: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        try:
            entry, is_replay = self.container.journal_service.reverse_journal(
                journal_id=journal_id,
                idempotency_key=idempotency_key,
                reason=reason,
                traceparent=traceparent,
            )
            return (200 if is_replay else 201), entry.to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def get_journal(self, journal_id: str) -> Tuple[int, Dict[str, Any]]:
        try:
            return 200, self.container.journal_service.get_journal(journal_id).to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def list_account_lines(self, account_id: str) -> Tuple[int, Dict[str, Any]]:
        lines = self.container.line_service.list_by_account(account_id)
        return 200, {"items": [ln.to_dict() for ln in lines]}

    def close(self) -> None:
        self.container.close()

    def __enter__(self) -> "TransactionsGateway":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from app.routers.journal_entry_router import create_journal_router
    from app.routers.posting_line_router import create_posting_line_router
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]


def create_app(db_path: str | Path | None = None) -> Any:
    """Create configured FastAPI app with RFC 9457 exception handlers."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Use TransactionsGateway or install fastapi>=0.110.")

    resolved_db = db_path or os.getenv("LEDGERFLOW_DB_PATH", "ledgerflow.db")
    container = TransactionsContainer(resolved_db)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        container.close()

    application = FastAPI(
        title="transactions-service API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.state.container = container

    @application.exception_handler(LedgerProblemError)
    async def ledger_problem_handler(_request: Request, exc: LedgerProblemError):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_problem_details(),
            media_type="application/problem+json",
        )

    _cors_origins = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if _cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=_cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "traceparent"],
        )

    application.include_router(create_journal_router(container.journal_service))
    application.include_router(create_posting_line_router(container.line_service))

    @application.get("/healthz", tags=["Observability"])
    async def health_check():
        return {"status": "healthy", "service": "transactions-service", "version": "1.0.0"}

    return application


app = create_app(":memory:") if FastAPI is not None else None
