from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request, status
from rag_system_core import AuthenticatedUser, RAGCore

from ragflow.api.errors import ApiError


def get_rag_core(request: Request) -> RAGCore:
    return request.app.state.rag_core


def get_max_upload_bytes(request: Request) -> int:
    return request.app.state.max_upload_bytes


def get_current_user(
    user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AuthenticatedUser:
    if user_id is None or not user_id.strip():
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="user_id_required",
            category="validation",
            message="X-User-Id header is required",
        )
    return AuthenticatedUser(sub=user_id.strip())


RAGCoreDependency = Annotated[RAGCore, Depends(get_rag_core)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
MaxUploadBytesDependency = Annotated[int, Depends(get_max_upload_bytes)]
