from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from rag_system_core import AuthenticatedUser, RAGCore

from ragflow.api.errors import ApiError
from ragflow.auth import AuthenticationError, AuthenticationUnavailableError, Authenticator

_bearer = HTTPBearer(auto_error=False)


def get_rag_core(request: Request) -> RAGCore:
    return request.app.state.rag_core


def get_max_upload_bytes(request: Request) -> int:
    return request.app.state.max_upload_bytes


def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            category="authentication",
            message="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    authenticator: Authenticator = request.app.state.authenticator
    try:
        return authenticator.authenticate(credentials.credentials)
    except AuthenticationUnavailableError as error:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="authentication_unavailable",
            category="dependency",
            message="Authentication service is unavailable",
            retryable=True,
        ) from error
    except AuthenticationError as error:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            category="authentication",
            message="The bearer token is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


RAGCoreDependency = Annotated[RAGCore, Depends(get_rag_core)]
CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
MaxUploadBytesDependency = Annotated[int, Depends(get_max_upload_bytes)]
