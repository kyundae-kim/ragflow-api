from __future__ import annotations

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragflow.api.errors import error_content

MULTIPART_OVERHEAD_BYTES = 1024 * 1024
DEFAULT_MAX_REQUEST_BYTES = 10 * 1024 * 1024 + MULTIPART_OVERHEAD_BYTES


class RequestBodyTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413, detail="Request body is too large")


class ConfiguredRequestBodyLimitMiddleware:
    """Enforce the app-configured body limit before FastAPI parses the body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        application = scope.get("app")
        state = getattr(application, "state", None)
        max_body_size = getattr(state, "max_request_bytes", DEFAULT_MAX_REQUEST_BYTES)
        content_length = _content_length(scope)
        if content_length is not None and content_length > max_body_size:
            await _too_large_response(scope, receive, send)
            return

        total_size = 0
        response_started = False

        async def receive_with_limit() -> Message:
            nonlocal total_size
            message = await receive()
            if message["type"] == "http.request":
                total_size += len(message.get("body", b""))
                if total_size > max_body_size:
                    raise RequestBodyTooLarge
            return message

        async def track_response(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive_with_limit, track_response)
        except RequestBodyTooLarge:
            if response_started:
                raise
            await _too_large_response(scope, receive, send)


def request_body_limit(max_upload_bytes: int) -> int:
    return max_upload_bytes + MULTIPART_OVERHEAD_BYTES


def _content_length(scope: Scope) -> int | None:
    value = Headers(scope=scope).get("content-length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


async def _too_large_response(scope: Scope, receive: Receive, send: Send) -> None:
    await _too_large_json_response()(scope, receive, send)


def request_body_too_large_handler(
    _: Request,
    __: Exception,
) -> JSONResponse:
    return _too_large_json_response()


def _too_large_json_response() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content=error_content(
            code="request_too_large",
            category="validation",
            retryable=False,
            message="Request body is too large",
        ),
    )
