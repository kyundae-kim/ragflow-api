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
        content={
            "code": error.code,
            "category": error.category,
            "retryable": error.retryable,
            "message": error.message,
        },
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
        content={
            "code": "request_validation_failed",
            "category": "validation",
            "retryable": False,
            "message": "Request validation failed",
            "issues": issues,
        },
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
        content={
            "code": code,
            "category": category,
            "retryable": False,
            "message": message,
        },
        headers=error.headers,
    )


async def dms_error_handler(_: Request, exception: Exception) -> JSONResponse:
    error = cast(dms.DmsError, exception)
    projection = dms.recommended_http_error(error)
    return JSONResponse(
        status_code=projection.status,
        content=projection.body,
        headers=projection.headers,
    )


async def internal_error_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "category": "internal",
            "retryable": False,
            "message": "The request could not be completed",
        },
    )
