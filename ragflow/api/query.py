from __future__ import annotations

from fastapi import APIRouter

from ragflow.api.dependencies import CurrentUserDependency, RAGCoreDependency
from ragflow.api.openapi import PROTECTED_ERROR_RESPONSES
from ragflow.api.schemas import QueryRequest, QueryResponse

router = APIRouter(tags=["query"], responses=PROTECTED_ERROR_RESPONSES)


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> QueryResponse:
    result = core.query(
        user=user,
        question=request.question,
        top_k=request.top_k,
    )
    return QueryResponse.from_application(result)
