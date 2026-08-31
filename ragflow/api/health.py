from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from ragflow.api.dependencies import RAGCoreDependency
from ragflow.api.openapi import READINESS_ERROR_RESPONSES
from ragflow.api.schemas import ReadinessResponse, ServiceHealthResponse
from ragflow.health import failed_health_check_result

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
    request: Request,
    _: RAGCoreDependency,
) -> ReadinessResponse:
    health_check_runner = getattr(request.app.state, "health_check_runner", None)
    if not callable(health_check_runner):
        result = failed_health_check_result()
    else:
        try:
            result = health_check_runner()
        except Exception:
            result = failed_health_check_result()
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
