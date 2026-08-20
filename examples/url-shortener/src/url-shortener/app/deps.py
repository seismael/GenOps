"""
FastAPI dependencies: cached application container provider & API-key auth.
"""

from __future__ import annotations

import functools
import os

from fastapi import Header, HTTPException

from app.container import ApplicationContainer


@functools.lru_cache(maxsize=None)
def get_container() -> ApplicationContainer:
    """Return a process-wide cached ApplicationContainer (one per KRYPTON_DB_PATH)."""
    return ApplicationContainer(os.getenv("KRYPTON_DB_PATH"))


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    """Validate the ``X-API-Key`` header against the API key repository."""
    if not get_container().api_key_repo.verify_token(x_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API token")
    return x_api_key
