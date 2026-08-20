from __future__ import annotations

from fastapi import APIRouter, Response, status

from ragflow.api.dependencies import RAGCoreDependency
from ragflow.api.openapi import READINESS_ERROR_RESPONSES
from ragflow.api.schemas import ReadinessResponse, ServiceHealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses=READINESS_ERROR_RESPONSES,
)
def readiness(
    response: Response,
    core: RAGCoreDependency,
) -> ReadinessResponse:
    result = core.health_check()
    ok = bool(getattr(result, "ok", False))
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    services = [
        ServiceHealthResponse(
            service=service.service_name,
            ok=service.ok,
            duration_seconds=service.duration_seconds,
            error=None if service.ok else "Dependency check failed",
        )
        for service in getattr(result, "services", [])
    ]
    return ReadinessResponse(
        status="ready" if ok else "not_ready",
        services=services,
    )
