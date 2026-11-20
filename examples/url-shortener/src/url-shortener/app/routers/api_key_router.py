"""
REST Router: API key management endpoint.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.container import ApplicationContainer
from app.deps import get_container, problem_response, require_admin_bootstrap_token
from app.domain.api_key import ApiKey

router = APIRouter()


class ApiKeyCreateRequest(BaseModel):
    owner_email: str
    raw_token: Optional[str] = None


@router.post("/api/v1/api-keys", status_code=201)
def create_api_key(
    payload: ApiKeyCreateRequest,
    _: None = Depends(require_admin_bootstrap_token),
    container: ApplicationContainer = Depends(get_container),
) -> JSONResponse:
    """Create and persist a new API key. Returns the raw token exactly once."""
    try:
        api_key, token = ApiKey.create(payload.raw_token, payload.owner_email)
        container.api_key_repo.save(api_key)
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            return problem_response(409, "API Key Conflict", msg, "urn:krypton:error:key-conflict")
        return problem_response(400, "Invalid API Key Request", msg, "urn:krypton:error:invalid-request")
    return JSONResponse(
        status_code=201,
        content={"key_id": api_key.key_id, "token": token},
    )
