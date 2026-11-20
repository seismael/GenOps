"""FastAPI router for Account lifecycle endpoints (guarded for zero-dep runtime parity)."""

from __future__ import annotations

from typing import Optional

from app.services.account_service import AccountService

try:
    from fastapi import APIRouter, Header, Query, status
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]
    Header = Query = Field = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


if APIRouter is not None:

    class OpenAccountRequest(BaseModel):
        code: str = Field(..., min_length=3, max_length=32)
        name: str = Field(..., min_length=1, max_length=120)
        account_type: str
        currency: str
        policy_id: str

    class TransitionStatusRequest(BaseModel):
        status: str

    def create_account_router(service: AccountService) -> APIRouter:
        router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])

        @router.post("", status_code=status.HTTP_201_CREATED)
        def open_account(payload: OpenAccountRequest, traceparent: Optional[str] = Header(default=None)):
            return service.open_account(
                code=payload.code,
                name=payload.name,
                account_type=payload.account_type,
                currency=payload.currency,
                policy_id=payload.policy_id,
                traceparent=traceparent,
            ).to_dict()

        @router.get("")
        def list_accounts(currency: Optional[str] = Query(default=None)):
            return {"items": [a.to_dict() for a in service.list_accounts(currency=currency)]}

        @router.get("/{account_id}")
        def get_account(account_id: str):
            return service.get_account(account_id).to_dict()

        @router.patch("/{account_id}/status")
        def transition_status(
            account_id: str,
            payload: TransitionStatusRequest,
            traceparent: Optional[str] = Header(default=None),
        ):
            return service.transition_status(account_id, payload.status, traceparent=traceparent).to_dict()

        return router
