"""Application entrypoint and dependency injection bootstrap for Ratelimit Engine."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup: initialize database pools & event listeners
    yield
    # Application shutdown: close connections cleanly


app = FastAPI(
    title="Ratelimit Engine API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )


@app.get("/healthz", tags=["Observability"])
async def health_check():
    return {"status": "healthy", "service": "ratelimit-engine", "version": "1.0.0"}
