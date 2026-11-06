"""Domain errors and RFC 9457 problem-details responses."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 400
    title: str = "Bad request"

    def __init__(self, detail: str | None = None, headers: dict[str, str] | None = None) -> None:
        self.detail = detail or self.title
        self.headers = headers
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    title = "Not found"


class UnauthorizedError(AppError):
    status_code = 401
    title = "Unauthorized"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    title = "Forbidden"


class PayloadTooLargeError(AppError):
    status_code = 413
    title = "Upload too large"


class ServiceUnavailableError(AppError):
    status_code = 503
    title = "Service unavailable"


def problem(
    status: int,
    title: str,
    detail: str,
    headers: dict[str, str] | None = None,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        jsonable_encoder(body),
        status_code=status,
        headers=headers,
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return problem(exc.status_code, exc.title, exc.detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type")}
            for err in exc.errors()
        ]
        return problem(
            422,
            "Invalid request",
            "One or more fields are missing or invalid. See 'errors'.",
            extra={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        try:
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "Error"
        return problem(exc.status_code, title, str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return problem(
            500,
            "Internal server error",
            "Something went wrong on our side. Quote the request_id if you report it.",
        )
