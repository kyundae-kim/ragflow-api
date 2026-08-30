from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import dms
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from rag_system_core import RAGCore
from starlette.exceptions import HTTPException as StarletteHTTPException

from ragflow.api.documents import router as documents_router
from ragflow.api.errors import (
    ApiError,
    api_error_handler,
    dms_error_handler,
    framework_http_error_handler,
    internal_error_handler,
    request_validation_error_handler,
)
from ragflow.api.health import router as health_router
from ragflow.api.middleware import (
    ConfiguredRequestBodyLimitMiddleware,
    RequestBodyTooLarge,
    request_body_limit,
    request_body_too_large_handler,
)
from ragflow.api.query import router as query_router
from ragflow.health import HealthCheckRunner, build_core_health_check_runner
from ragflow.runtime import DEFAULT_MAX_UPLOAD_BYTES, RuntimeFactory, build_runtime


def create_app(
    *,
    core: RAGCore | None = None,
    runtime_factory: RuntimeFactory | None = None,
    max_upload_bytes: int | None = None,
    health_check_runner: HealthCheckRunner | None = None,
) -> FastAPI:
    if max_upload_bytes is not None and max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be positive")
    if core is not None and runtime_factory is not None:
        raise ValueError("runtime_factory cannot be combined with injected components")
    if core is None and runtime_factory is None:
        runtime_factory = build_runtime

    lifespan = None
    if runtime_factory is not None:

        @asynccontextmanager
        async def managed_lifespan(app: FastAPI) -> AsyncIterator[None]:
            with runtime_factory() as components:
                app.state.rag_core = components.core
                effective_upload_limit = max_upload_bytes or components.max_upload_bytes
                app.state.max_upload_bytes = effective_upload_limit
                app.state.max_request_bytes = request_body_limit(effective_upload_limit)
                app.state.health_check_runner = (
                    health_check_runner
                    or components.health_check_runner
                    or build_core_health_check_runner(components.core)
                )
                yield

        lifespan = managed_lifespan

    app = FastAPI(title="RAG Flow API", version="0.1.0", lifespan=lifespan)
    if core is not None:
        effective_upload_limit = max_upload_bytes or DEFAULT_MAX_UPLOAD_BYTES
        app.state.rag_core = core
        app.state.max_upload_bytes = effective_upload_limit
        app.state.max_request_bytes = request_body_limit(effective_upload_limit)
        app.state.health_check_runner = health_check_runner or build_core_health_check_runner(core)
    app.add_middleware(ConfiguredRequestBodyLimitMiddleware)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestBodyTooLarge, request_body_too_large_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, framework_http_error_handler)
    app.add_exception_handler(dms.DmsError, dms_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)
    app.include_router(documents_router)
    app.include_router(query_router)
    app.include_router(health_router)
    return app
