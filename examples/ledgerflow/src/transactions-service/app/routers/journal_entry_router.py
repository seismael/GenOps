"""FastAPI router for JournalEntry posting and reversal endpoints (guarded)."""

from __future__ import annotations

from typing import List, Optional

from app.services.journal_entry_service import JournalEntryService

try:
    from fastapi import APIRouter, Header, Response, status
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]
    Header = Response = Field = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


if APIRouter is not None:

    class PostingLineInput(BaseModel):
        account_id: str
        side: str
        amount_minor: int = Field(..., gt=0)

    class PostJournalRequest(BaseModel):
        idempotency_key: str = Field(..., min_length=1, max_length=128)
        description: str = Field(..., min_length=1)
        currency: str
        lines: List[PostingLineInput]

    class ReverseJournalRequest(BaseModel):
        idempotency_key: str = Field(..., min_length=1, max_length=128)
        reason: str = ""

    def create_journal_router(service: JournalEntryService) -> APIRouter:
        router = APIRouter(prefix="/api/v1/journals", tags=["Journals"])

        @router.post("", status_code=status.HTTP_201_CREATED)
        def post_journal(
            payload: PostJournalRequest,
            response: Response,
            traceparent: Optional[str] = Header(default=None),
        ):
            entry, is_replay = service.post_journal(
                idempotency_key=payload.idempotency_key,
                description=payload.description,
                currency=payload.currency,
                lines=[ln.model_dump() for ln in payload.lines],
                traceparent=traceparent,
            )
            if is_replay:
                response.status_code = status.HTTP_200_OK
            return entry.to_dict()

        @router.get("")
        def list_journals():
            return {"items": [j.to_dict() for j in service.list_journals()]}

        @router.get("/{journal_id}")
        def get_journal(journal_id: str):
            return service.get_journal(journal_id).to_dict()

        @router.post("/{journal_id}/reverse", status_code=status.HTTP_201_CREATED)
        def reverse_journal(
            journal_id: str,
            payload: ReverseJournalRequest,
            response: Response,
            traceparent: Optional[str] = Header(default=None),
        ):
            entry, is_replay = service.reverse_journal(
                journal_id=journal_id,
                idempotency_key=payload.idempotency_key,
                reason=payload.reason,
                traceparent=traceparent,
            )
            if is_replay:
                response.status_code = status.HTTP_200_OK
            return entry.to_dict()

        return router
