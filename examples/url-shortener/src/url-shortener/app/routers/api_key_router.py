"""
REST Router: API key management endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.container import ApplicationContainer
from app.deps import get_container
from app.domain.api_key import ApiKey

router = APIRouter()


class ApiKeyCreateRequest(BaseModel):
    owner_email: str
    raw_token: str


@router.post("/api/v1/api-keys", status_code=201)
def create_api_key(
    payload: ApiKeyCreateRequest,
    container: ApplicationContainer = Depends(get_container),
) -> JSONResponse:
    """Create and persist a new API key. Returns the raw token exactly once."""
    api_key, token = ApiKey.create(payload.raw_token, payload.owner_email)
    container.api_key_repo.save(api_key)
    return JSONResponse(
        status_code=201,
        content={"key_id": api_key.key_id, "token": token},
    )
