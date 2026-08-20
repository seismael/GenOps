"""
Primary Ingress Adapter: FastAPI application bootstrap & routing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI

from app.container import ApplicationContainer  # re-exported for back-compat / tests
from app.domain.api_key import ApiKey
from app.routers import api_key_router, click_event_router, short_url_router


def create_app() -> FastAPI:
    """Build and configure the Krypton FastAPI application."""
    app = FastAPI(title="Krypton URL Shortener Gateway API", version="1.0.0")

    # Registered before the redirect router so /healthz is never shadowed by /{code}
    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    app.include_router(short_url_router.router)
    app.include_router(click_event_router.router)
    app.include_router(api_key_router.router)

    return app


# Standalone clean handler for direct HTTP / Serverless / Test environments
class KryptonGateway:
    """Main request router and handler."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        self.container = container or ApplicationContainer(":memory:")

    def create_api_key(self, owner_email: str, raw_token: str = "secret-token") -> str:
        api_key, token = ApiKey.create(raw_token, owner_email)
        self.container.api_key_repo.save(api_key)
        return token

    def handle_shorten(self, token: str, target_url: str, custom_alias: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v1/shorten"""
        if not self.container.api_key_repo.verify_token(token):
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
            return {"status": 400, "error": str(e)}

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


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)
