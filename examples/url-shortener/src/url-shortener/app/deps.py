"""
FastAPI dependencies: cached application container provider & API-key auth.
"""

from __future__ import annotations

import functools
import logging
import os

from fastapi import Header, HTTPException
from fastapi.responses import JSONResponse

from app.container import ApplicationContainer

logger = logging.getLogger("krypton.auth")


def problem_response(status_code: int, title: str, detail: str, error_type: str = "about:blank") -> JSONResponse:
    """Return an IETF RFC 9457 Problem Details JSON response."""
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": error_type,
            "title": title,
            "status": status_code,
            "detail": detail,
            "error": detail,
        },
    )


@functools.lru_cache(maxsize=None)
def get_container() -> ApplicationContainer:
    """Return a process-wide cached ApplicationContainer (one per KRYPTON_DB_PATH)."""
    return ApplicationContainer(os.getenv("KRYPTON_DB_PATH"))


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    """Validate the ``X-API-Key`` header against the API key repository."""
    if not get_container().api_key_repo.verify_token(x_api_key):
        logger.warning("Rejected unauthorized API request with invalid or missing X-API-Key")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API token")
    return x_api_key


def require_admin_bootstrap_token(x_admin_token: str = Header(default="", alias="X-Admin-Token")) -> None:
    """Guard API key minting with KRYPTON_ADMIN_BOOTSTRAP_TOKEN when configured in production."""
    import hmac

    expected = os.getenv("KRYPTON_ADMIN_BOOTSTRAP_TOKEN", "")
    if expected and not hmac.compare_digest(x_admin_token, expected):
        logger.warning("Rejected API key creation with invalid X-Admin-Token")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid admin bootstrap token")
