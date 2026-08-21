from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import get_settings
from .database import SessionLocal, init_database
from .mafer.configuration import ensure_configuration_snapshots
from .routers import (
    analytics,
    compare,
    data,
    quality,
    records,
    search,
    search_jobs,
    settings,
    sources,
    system,
)
from .services.bootstrap import seed_database
from .services.registry import build_connector_registry
from .services.search_jobs import make_search_job_registry


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=True,
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=get_settings().log_level, handlers=[handler], force=True)


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 65_536) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw_length = headers.get(b"content-length")
            try:
                too_large = raw_length is not None and int(raw_length) > self.max_bytes
            except ValueError:
                too_large = True
            if too_large:
                response = JSONResponse(
                    status_code=413, content={"detail": "Request body is too large"}
                )
                await response(scope, receive, send)
                return
            messages: list[dict] = []
            total = 0
            while True:
                message = await receive()
                messages.append(message)
                if message["type"] != "http.request":
                    break
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    response = JSONResponse(
                        status_code=413, content={"detail": "Request body is too large"}
                    )
                    await response(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break

            async def replay() -> dict:
                if messages:
                    return messages.pop(0)
                # Streaming responses still need a blocking receive channel for disconnects.
                # Returning synthetic request messages forever would starve the SSE producer.
                return await receive()

            await self.app(scope, replay, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def secure_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, secure_send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_database()
    app.state.connectors = build_connector_registry(get_settings())
    app.state.search_jobs = make_search_job_registry(SessionLocal, get_settings())
    with SessionLocal() as db:
        seed_database(db, app.state.connectors)
        ensure_configuration_snapshots(db)
        db.commit()
    try:
        yield
    finally:
        await app.state.search_jobs.shutdown()


settings_config = get_settings()
app = FastAPI(
    title="MIRSAD API",
    description="Local-first public content discovery and explainable analysis",
    version=settings_config.version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings_config.web_origin, "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=65_536)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("mirsad.api").exception(
        "Unhandled request failure", extra={"path": request.url.path}
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


for router in (
    search.router,
    search_jobs.router,
    analytics.router,
    compare.router,
    records.router,
    data.router,
    sources.router,
    settings.router,
    system.router,
    quality.router,
):
    app.include_router(router, prefix="/api/v1")
