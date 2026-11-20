"""Application entrypoint, RFC 9457 gateway facade, and FastAPI bootstrap for accounts-service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.container import AccountsContainer
from app.domain.exceptions import LedgerProblemError


class AccountsGateway:
    """Zero-dependency HTTP-status/RFC-9457 adapter for Accounts use cases."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.container = AccountsContainer(db_path)

    def create_policy(
        self,
        name: str,
        allow_overdraft: bool = False,
        max_posting_minor: int = 10_000_000,
        description: str = "",
    ) -> Tuple[int, Dict[str, Any]]:
        try:
            policy = self.container.policy_service.create_policy(
                name=name,
                allow_overdraft=allow_overdraft,
                max_posting_minor=max_posting_minor,
                description=description,
            )
            return 201, policy.to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def open_account(
        self,
        code: str,
        name: str,
        account_type: str,
        currency: str,
        policy_id: str,
        traceparent: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        try:
            acct = self.container.account_service.open_account(
                code=code,
                name=name,
                account_type=account_type,
                currency=currency,
                policy_id=policy_id,
                traceparent=traceparent,
            )
            return 201, acct.to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def get_account(self, account_id: str) -> Tuple[int, Dict[str, Any]]:
        try:
            return 200, self.container.account_service.get_account(account_id).to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def transition_status(
        self, account_id: str, status: str, traceparent: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        try:
            acct = self.container.account_service.transition_status(account_id, status, traceparent=traceparent)
            return 200, acct.to_dict()
        except LedgerProblemError as err:
            return err.status_code, err.to_problem_details()

    def close(self) -> None:
        self.container.close()

    def __enter__(self) -> "AccountsGateway":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from app.routers.account_router import create_account_router
    from app.routers.ledger_policy_router import create_policy_router
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]


def create_app(db_path: str | Path | None = None) -> Any:
    """Create configured FastAPI app with RFC 9457 exception handlers."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Use AccountsGateway or install fastapi>=0.110.")

    resolved_db = db_path or os.getenv("LEDGERFLOW_DB_PATH", "ledgerflow.db")
    container = AccountsContainer(resolved_db)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        container.close()

    application = FastAPI(
        title="accounts-service API",
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
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "traceparent"],
        )

    application.include_router(create_policy_router(container.policy_service))
    application.include_router(create_account_router(container.account_service))

    @application.get("/healthz", tags=["Observability"])
    async def health_check():
        return {"status": "healthy", "service": "accounts-service", "version": "1.0.0"}

    return application


app = create_app(":memory:") if FastAPI is not None else None
