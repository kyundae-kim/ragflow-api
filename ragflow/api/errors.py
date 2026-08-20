from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import dms
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    category: str
    message: str
    retryable: bool = False
    headers: dict[str, str] = field(default_factory=dict)


async def api_error_handler(_: Request, exception: Exception) -> JSONResponse:
    error = cast(ApiError, exception)
    return JSONResponse(
        status_code=error.status_code,
        content=error_content(
            code=error.code,
            category=error.category,
            retryable=error.retryable,
            message=error.message,
        ),
        headers=error.headers,
    )


async def request_validation_error_handler(
    _: Request,
    exception: Exception,
) -> JSONResponse:
    error = cast(RequestValidationError, exception)
    issues = [
        {
            "location": list(issue["loc"]),
            "message": issue["msg"],
            "type": issue["type"],
        }
        for issue in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_content(
            code="request_validation_failed",
            category="validation",
            retryable=False,
            message="Request validation failed",
            issues=issues,
        ),
    )


async def framework_http_error_handler(_: Request, exception: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exception)
    projections = {
        400: ("invalid_request", "validation", "Request could not be parsed"),
        401: ("authentication_required", "authentication", "Authentication is required"),
        403: ("operation_forbidden", "authorization", "The operation is not allowed"),
        404: ("route_not_found", "routing", "Route not found"),
        405: ("method_not_allowed", "routing", "Method not allowed"),
        413: ("request_too_large", "validation", "Request body is too large"),
    }
    code, category, message = projections.get(
        error.status_code,
        ("http_error", "http", "The HTTP request could not be completed"),
    )
    return JSONResponse(
        status_code=error.status_code,
        content=error_content(
            code=code,
            category=category,
            retryable=False,
            message=message,
        ),
        headers=error.headers,
    )


async def dms_error_handler(_: Request, exception: Exception) -> JSONResponse:
    error = cast(dms.DmsError, exception)
    projection = _project_dms_error(error)
    return JSONResponse(
        status_code=projection.status,
        content=projection.body,
        headers=projection.headers,
    )


@dataclass(frozen=True, slots=True)
class _DmsHttpProjection:
    status: int
    body: dict[str, object]
    headers: dict[str, str] = field(default_factory=dict)


def _project_dms_error(error: dms.DmsError) -> _DmsHttpProjection:
    code = str(getattr(error, "code", "dms_error"))
    category = str(getattr(error, "category", "internal"))
    retryable = bool(getattr(error, "retryable", False))
    return _DmsHttpProjection(
        status=_dms_status(code=code, category=category),
        body=error_content(
            code=code,
            category=category,
            retryable=retryable,
            message=_dms_message(code=code, category=category),
        ),
    )


def _dms_status(*, code: str, category: str) -> int:
    if code == "idempotency_in_progress":
        return 425
    if code == "document_too_large":
        return 413
    if category == "access":
        return 403
    if category == "validation":
        return 400
    if category == "not_found":
        return 404
    if category in {"conflict", "unavailable"}:
        return 409
    if category in {"storage", "health"}:
        return 503
    return 500


def _dms_message(*, code: str, category: str) -> str:
    if category == "access":
        return "The operation is not allowed"
    if code == "document_too_large":
        return "Document is too large"
    if category == "validation":
        return "The request failed validation"
    if category == "not_found":
        return "Document was not found"
    if category in {"conflict", "unavailable"}:
        return "The document is not available for this operation"
    if category == "storage":
        return "A storage dependency failed"
    if category == "health":
        return "A dependency health check failed"
    return "The request could not be completed"


async def internal_error_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_content(
            code="internal_error",
            category="internal",
            retryable=False,
            message="The request could not be completed",
        ),
    )


def error_content(
    *,
    code: str,
    category: str,
    retryable: bool,
    message: str,
    issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    content: dict[str, object] = {
        "code": code,
        "category": category,
        "retryable": retryable,
        "message": message,
    }
    if issues is not None:
        content["issues"] = issues
    return content
