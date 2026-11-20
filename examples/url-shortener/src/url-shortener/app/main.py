"""
Primary Ingress Adapter: FastAPI application bootstrap & routing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.container import ApplicationContainer  # re-exported for back-compat / tests
from app.domain.api_key import ApiKey

logger = logging.getLogger("krypton")

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from app.routers import api_key_router, click_event_router, short_url_router
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - allows stdlib-only gateway unit tests
    FastAPI = None  # type: ignore[assignment,misc]
    _FASTAPI_AVAILABLE = False


def create_app() -> "FastAPI":
    """Build and configure the Krypton FastAPI application."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is required to run the ASGI HTTP server.")
    app = FastAPI(title="Krypton URL Shortener Gateway API", version="1.0.0")

    @app.exception_handler(HTTPException)
    def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content={
                "type": "about:blank",
                "title": "Request Error",
                "status": exc.status_code,
                "detail": str(exc.detail),
                "error": str(exc.detail),
                "instance": str(request.url.path),
            },
        )

    # Registered before the redirect router so /healthz is never shadowed by /{code}
    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "healthy", "service": "url-shortener", "version": "1.0.0"}

    app.include_router(short_url_router.router)
    app.include_router(click_event_router.router)
    app.include_router(api_key_router.router)

    return app


# Standalone clean handler for direct HTTP / Serverless / Test environments
class KryptonGateway:
    """Main request router and handler."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        self.container = container or ApplicationContainer(":memory:")

    def create_api_key(self, owner_email: str, raw_token: Optional[str] = "secret-token") -> str:
        api_key, token = ApiKey.create(raw_token, owner_email)
        self.container.api_key_repo.save(api_key)
        return token

    def handle_shorten(self, token: str, target_url: str, custom_alias: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v1/shorten"""
        if not self.container.api_key_repo.verify_token(token):
            logger.warning("Gateway rejected unauthorized shorten request")
            return {"status": 401, "error": "Unauthorized: Invalid API token"}

        try:
            short_url = self.container.url_service.shorten_url(target_url, custom_alias)
            return {
                "status": 201,
                "data": {
                    "code": short_url.code,
                    "short_url": f"https://krp.tn/{short_url.code}",
                    "target_url": short_url.target_url,
                    "created_at": short_url.created_at.isoformat(),
                },
            }
        except ValueError as e:
            msg = str(e)
            if "already taken" in msg:
                return {"status": 409, "error": msg}
            logger.warning("Gateway rejected target URL: %s", msg)
            return {"status": 400, "error": msg}

    def handle_redirect(self, code: str, ip: str = "", user_agent: str = "", referrer: str = "") -> Dict[str, Any]:
        """GET /{code}"""
        target_url = self.container.url_service.resolve_url(code, ip, user_agent, referrer)
        if not target_url:
            return {"status": 404, "error": "Short URL not found"}
        return {"status": 302, "location": target_url}

    def handle_analytics(self, token: str, code: str) -> Dict[str, Any]:
        """GET /api/v1/analytics/{code}"""
        if not self.container.api_key_repo.verify_token(token):
            return {"status": 401, "error": "Unauthorized: Invalid API token"}

        try:
            analytics = self.container.url_service.get_analytics(code)
            return {"status": 200, "data": analytics}
        except FileNotFoundError as e:
            return {"status": 404, "error": str(e)}


app = create_app() if _FASTAPI_AVAILABLE else None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
