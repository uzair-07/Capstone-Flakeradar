import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, log_fields, request_id_var
from app.health.router import router as health_router
from app.ingest.router import router as ingest_router
from app.runs.router import router as runs_router

logger = logging.getLogger("app.request")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info(
            "request",
            extra=log_fields(
                method=request.method,
                path=request.url.path,
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            ),
        )
        request_id_var.reset(token)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="FlakeRadar API",
        version=__version__,
        description="Collects JUnit reports from CI and tracks test reliability.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.middleware("http")(request_context)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(health_router, prefix="/api", include_in_schema=False)
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(runs_router, prefix="/api/v1")
    return app


app = create_app()
