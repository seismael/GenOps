"""FastAPI router for PostingLine query endpoints (guarded)."""

from __future__ import annotations

from app.services.posting_line_service import PostingLineService

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]


if APIRouter is not None:

    def create_posting_line_router(service: PostingLineService) -> APIRouter:
        router = APIRouter(prefix="/api/v1", tags=["Posting Lines"])

        @router.get("/accounts/{account_id}/lines")
        def list_account_lines(account_id: str):
            return {"items": [ln.to_dict() for ln in service.list_by_account(account_id)]}

        @router.get("/journals/{journal_id}/lines")
        def list_journal_lines(journal_id: str):
            return {"items": [ln.to_dict() for ln in service.list_by_journal(journal_id)]}

        return router
