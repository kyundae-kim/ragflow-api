from __future__ import annotations

from typing import Any

from ragflow.api.schemas import ApiErrorResponse, ReadinessResponse


def _api_error(description: str) -> dict[str, Any]:
    return {"model": ApiErrorResponse, "description": description}


PROTECTED_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _api_error("The request body could not be parsed"),
    413: _api_error("The request body is too large"),
    422: _api_error("Request validation failed"),
    500: _api_error("Unexpected application failure"),
    503: _api_error("An application dependency is unavailable"),
}

DOCUMENT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **PROTECTED_ERROR_RESPONSES,
    400: _api_error("The uploaded file or request is invalid"),
    403: _api_error("The operation is not allowed"),
    404: _api_error("The document is not visible to the requested user"),
    409: _api_error("The document operation conflicts with current state"),
    413: _api_error("The upload or request body is too large"),
    425: _api_error("The document operation is not ready to retry"),
    502: _api_error("An upstream application dependency returned an invalid response"),
    504: _api_error("An upstream application dependency timed out"),
}

READINESS_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {
        "model": ReadinessResponse,
        "description": "One or more required application dependencies are unavailable",
    }
}
