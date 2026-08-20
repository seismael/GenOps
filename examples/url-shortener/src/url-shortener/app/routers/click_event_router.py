"""
REST Router: clickstream analytics endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.container import ApplicationContainer
from app.deps import get_container, require_api_key

router = APIRouter()


@router.get("/api/v1/analytics/{code}", status_code=200)
def get_click_analytics(
    code: str,
    _: str = Depends(require_api_key),
    container: ApplicationContainer = Depends(get_container),
) -> JSONResponse:
    """Return aggregated click analytics for a short code. Requires a valid ``X-API-Key``."""
    try:
        analytics = container.url_service.get_analytics(code)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return JSONResponse(status_code=200, content=analytics)
