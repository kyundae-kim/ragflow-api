from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from sqlalchemy import text

DependencyCheck = Callable[[], object]


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    service_name: str
    ok: bool
    duration_seconds: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    ok: bool
    services: tuple[DependencyHealth, ...]


HealthCheckRunner = Callable[[], HealthCheckResult]


def run_health_checks(
    checks: Iterable[tuple[str, DependencyCheck]],
) -> HealthCheckResult:
    """Run host-owned checks independently and return a secret-safe result."""
    services: list[DependencyHealth] = []
    for service_name, check in checks:
        started = perf_counter()
        try:
            check_result = check()
            ok = check_result is not False
        except Exception:
            ok = False
        duration_seconds = max(0.0, perf_counter() - started)
        services.append(
            DependencyHealth(
                service_name=service_name,
                ok=ok,
                duration_seconds=duration_seconds,
                error=None if ok else "Dependency check failed",
            )
        )
    return HealthCheckResult(
        ok=all(service.ok for service in services),
        services=tuple(services),
    )


def build_core_health_check_runner(core: object) -> HealthCheckRunner:
    """Build a readiness runner for a directly injected RAGCore."""

    def check() -> HealthCheckResult:
        return run_health_checks((("metadata", lambda: _check_metadata_store(core)),))

    return check


def build_runtime_health_check_runner(
    *,
    dms_engine: object,
    metadata_engine: object,
    minio_client: object,
    bucket_name: str,
    ollama_client: object,
    milvus_client: object,
) -> HealthCheckRunner:
    """Build readiness checks for resources assembled by the host runtime."""

    def check() -> HealthCheckResult:
        return run_health_checks(
            (
                ("dms_metadata", lambda: _check_sqlalchemy_engine(dms_engine)),
                ("rag_metadata", lambda: _check_sqlalchemy_engine(metadata_engine)),
                ("minio", lambda: _check_minio(minio_client, bucket_name)),
                ("ollama", lambda: _call_health_method(ollama_client, "list")),
                (
                    "milvus",
                    lambda: _call_health_method(milvus_client, "get_server_version"),
                ),
            )
        )

    return check


def failed_health_check_result() -> HealthCheckResult:
    """Return a generic result for an unexpected readiness-runner failure."""
    return HealthCheckResult(
        ok=False,
        services=(
            DependencyHealth(
                service_name="application",
                ok=False,
                duration_seconds=0.0,
                error="Dependency check failed",
            ),
        ),
    )


def _check_metadata_store(core: object) -> object:
    metadata_store = getattr(core, "metadata_store", None)
    if metadata_store is None:
        raise RuntimeError("metadata store is not configured")

    check = getattr(metadata_store, "check", None)
    if callable(check):
        return check()

    return _check_sqlalchemy_engine(getattr(metadata_store, "engine", None))


def _check_sqlalchemy_engine(engine: object) -> None:
    connect = getattr(engine, "connect", None)
    if not callable(connect):
        raise RuntimeError("SQLAlchemy engine is not configured")
    with cast(AbstractContextManager[Any], connect()) as connection:
        connection.execute(text("SELECT 1"))


def _check_minio(client: object, bucket_name: str) -> object:
    bucket_exists = getattr(client, "bucket_exists", None)
    if not callable(bucket_exists):
        raise RuntimeError("MinIO client is not configured")
    return bucket_exists(bucket_name)


def _call_health_method(client: object, method_name: str) -> object:
    method = getattr(client, method_name, None)
    if not callable(method):
        raise RuntimeError(f"Dependency client does not expose {method_name}()")
    return method()
