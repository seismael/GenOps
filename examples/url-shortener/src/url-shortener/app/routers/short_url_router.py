"""
REST Router: URL shortening & redirection endpoints.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.container import ApplicationContainer
from app.deps import get_container, require_api_key

router = APIRouter()


class ShortenRequest(BaseModel):
    url: str
    custom_alias: Optional[str] = None


@router.post("/api/v1/shorten", status_code=201)
def shorten(
    payload: ShortenRequest,
    _: str = Depends(require_api_key),
    container: ApplicationContainer = Depends(get_container),
) -> JSONResponse:
    """Create a shortened URL. Requires a valid ``X-API-Key`` header."""
    try:
        short_url = container.url_service.shorten_url(payload.url, payload.custom_alias)
    except ValueError as e:
        message = str(e)
        if "already taken" in message:
            return JSONResponse(status_code=409, content={"error": message})
        return JSONResponse(status_code=400, content={"error": message})

    return JSONResponse(
        status_code=201,
        content={
            "code": short_url.code,
            "short_url": f"https://krp.tn/{short_url.code}",
            "target_url": short_url.target_url,
            "created_at": short_url.created_at.isoformat(),
        },
    )


@router.get("/{code}")
def redirect_to_target(
    code: str,
    request: Request,
    container: ApplicationContainer = Depends(get_container),
) -> RedirectResponse:
    """Resolve a short code to its target URL and issue an HTTP 302 redirect."""
    target_url = container.url_service.resolve_url(
        code,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
        referrer=request.headers.get("referer", ""),
    )
    if not target_url:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(url=target_url, status_code=302)
