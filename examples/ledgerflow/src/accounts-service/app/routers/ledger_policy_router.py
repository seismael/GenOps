"""FastAPI router for LedgerPolicy governance endpoints (guarded for zero-dep runtime parity)."""

from __future__ import annotations

from app.services.ledger_policy_service import LedgerPolicyService

try:
    from fastapi import APIRouter, status
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]
    Field = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


if APIRouter is not None:

    class CreatePolicyRequest(BaseModel):
        name: str = Field(..., min_length=1, max_length=80)
        allow_overdraft: bool = False
        max_posting_minor: int = Field(default=10_000_000, gt=0)
        description: str = ""

    def create_policy_router(service: LedgerPolicyService) -> APIRouter:
        router = APIRouter(prefix="/api/v1/policies", tags=["Ledger Policies"])

        @router.post("", status_code=status.HTTP_201_CREATED)
        def create_policy(payload: CreatePolicyRequest):
            return service.create_policy(
                name=payload.name,
                allow_overdraft=payload.allow_overdraft,
                max_posting_minor=payload.max_posting_minor,
                description=payload.description,
            ).to_dict()

        @router.get("")
        def list_policies():
            return {"items": [p.to_dict() for p in service.list_policies()]}

        @router.get("/{policy_id}")
        def get_policy(policy_id: str):
            return service.get_policy(policy_id).to_dict()

        return router
