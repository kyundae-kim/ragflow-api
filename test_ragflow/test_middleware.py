from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import cast

from rag_system_core import RAGCore
from starlette.types import Message, Receive, Scope, Send

from ragflow.api.middleware import ConfiguredRequestBodyLimitMiddleware
from ragflow.app import create_app
from ragflow.auth import Authenticator


def test_request_body_limit_counts_streamed_body_without_content_length() -> None:
    received: list[Message] = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"de", "more_body": False},
    ]
    sent: list[Message] = []
    inner_completed = False

    async def receive() -> Message:
        return received.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    async def inner_app(_: Scope, inner_receive: Receive, __: Send) -> None:
        nonlocal inner_completed
        await inner_receive()
        await inner_receive()
        inner_completed = True

    scope = cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/documents/text",
            "raw_path": b"/documents/text",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "app": SimpleNamespace(state=SimpleNamespace(max_request_bytes=4)),
        },
    )

    middleware = ConfiguredRequestBodyLimitMiddleware(inner_app)
    asyncio.run(middleware(scope, receive, send))

    assert inner_completed is False
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    assert dict(sent[0]["headers"])[b"content-type"] == b"application/json"
    assert json.loads(sent[1]["body"]) == {
        "code": "request_too_large",
        "category": "validation",
        "retryable": False,
        "message": "Request body is too large",
    }


def test_fastapi_preserves_streaming_body_limit_error_contract() -> None:
    app = create_app(
        core=cast(RAGCore, object()),
        authenticator=cast(Authenticator, object()),
    )
    app.state.max_request_bytes = 4
    received: list[Message] = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"de", "more_body": False},
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return received.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    scope = cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/documents/text",
            "raw_path": b"/documents/text",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "app": app,
        },
    )

    asyncio.run(app(scope, receive, send))

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["code"] == "request_too_large"
