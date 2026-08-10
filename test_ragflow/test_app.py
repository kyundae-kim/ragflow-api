from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from starlette.testclient import TestClient

from ragflow.app import create_app
from ragflow.runtime import RuntimeComponents


def test_app_lifespan_installs_and_closes_runtime_components() -> None:
    events: list[str] = []
    core = object()
    authenticator = object()

    @contextmanager
    def runtime_factory() -> Iterator[RuntimeComponents]:
        events.append("started")
        try:
            yield RuntimeComponents(
                core=core,  # type: ignore[arg-type]
                authenticator=authenticator,  # type: ignore[arg-type]
            )
        finally:
            events.append("stopped")

    app = create_app(runtime_factory=runtime_factory)

    with TestClient(app) as client:
        assert events == ["started"]
        assert app.state.rag_core is core
        assert app.state.authenticator is authenticator
        assert client.get("/health/live").status_code == 200

    assert events == ["started", "stopped"]


def test_explicit_upload_limit_overrides_runtime_factory_default() -> None:
    @contextmanager
    def runtime_factory() -> Iterator[RuntimeComponents]:
        yield RuntimeComponents(core=object(), authenticator=object())  # type: ignore[arg-type]

    app = create_app(runtime_factory=runtime_factory, max_upload_bytes=4)

    with TestClient(app):
        assert app.state.max_upload_bytes == 4


def test_main_exports_the_fastapi_application() -> None:
    from fastapi import FastAPI

    from ragflow.main import app

    assert isinstance(app, FastAPI)
    assert app.title == "RAG Flow API"


def test_openapi_protected_operations_use_complete_public_error_contract() -> None:
    schema = create_app().openapi()
    expected_protected_operations = {
        ("get", "/documents"),
        ("post", "/documents/text"),
        ("post", "/documents/file"),
        ("get", "/documents/{doc_id}"),
        ("delete", "/documents/{doc_id}"),
        ("get", "/documents/{doc_id}/chunks"),
        ("get", "/documents/{doc_id}/ingestion-progress"),
        ("post", "/query"),
    }
    documented_protected_operations = {
        (method, path)
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "delete"} and operation.get("security")
    }

    assert documented_protected_operations == expected_protected_operations
    for method, path in expected_protected_operations:
        responses = schema["paths"][path][method]["responses"]
        for status in ("400", "401", "413", "422", "500", "503"):
            assert responses[status]["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ApiErrorResponse"
            }

    assert schema["paths"]["/health/ready"]["get"]["responses"]["503"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReadinessResponse"}
