from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    Response,
    UploadFile,
    status,
)

from ragflow.api.dependencies import (
    CurrentUserDependency,
    MaxUploadBytesDependency,
    RAGCoreDependency,
)
from ragflow.api.errors import ApiError
from ragflow.api.openapi import DOCUMENT_ERROR_RESPONSES
from ragflow.api.schemas import (
    ChunkResponse,
    DocumentResponse,
    IngestionProgressResponse,
    IngestResponse,
    TextIngestRequest,
)

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses=DOCUMENT_ERROR_RESPONSES,
)


def _document_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="document_not_found",
        category="not_found",
        message="Document was not found",
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> list[DocumentResponse]:
    return [
        DocumentResponse.from_application(document) for document in core.list_documents(user=user)
    ]


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: str,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> DocumentResponse:
    document = core.get_document(doc_id, user=user)
    if document is None:
        raise _document_not_found()
    return DocumentResponse.from_application(document)


@router.get("/{doc_id}/chunks", response_model=list[ChunkResponse])
def list_document_chunks(
    doc_id: str,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> list[ChunkResponse]:
    if core.get_document(doc_id, user=user) is None:
        raise _document_not_found()
    return [
        ChunkResponse.from_application(chunk)
        for chunk in core.list_document_chunks(doc_id, user=user)
    ]


@router.get(
    "/{doc_id}/ingestion-progress",
    response_model=list[IngestionProgressResponse],
)
def list_ingestion_progress(
    doc_id: str,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
    job_id: str | None = None,
) -> list[IngestionProgressResponse]:
    if core.get_document(doc_id, user=user) is None:
        raise _document_not_found()
    return [
        IngestionProgressResponse.from_application(progress)
        for progress in core.list_ingestion_progress(
            doc_id,
            user=user,
            job_id=job_id,
        )
    ]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> Response:
    if not core.delete_document(doc_id, user=user):
        raise _document_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/text",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_text(
    request: TextIngestRequest,
    core: RAGCoreDependency,
    user: CurrentUserDependency,
) -> IngestResponse:
    result = core.ingest_text(user=user, text=request.text, source=request.source)
    return IngestResponse.from_application(result)


@router.post(
    "/file",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_file(
    file: Annotated[UploadFile, File()],
    core: RAGCoreDependency,
    user: CurrentUserDependency,
    max_upload_bytes: MaxUploadBytesDependency,
    source: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    upload_size = file.size
    if upload_size is None:
        position = file.file.tell()
        file.file.seek(0, 2)
        upload_size = file.file.tell()
        file.file.seek(position)
    if upload_size == 0:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="empty_upload",
            category="validation",
            message="Uploaded file must not be empty",
        )
    if upload_size > max_upload_bytes:
        raise ApiError(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            code="upload_too_large",
            category="validation",
            message=f"Uploaded file exceeds the {max_upload_bytes} byte limit",
        )

    raw_content = file.file.read()
    file.file.seek(0)
    try:
        decoded_content = raw_content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_utf8",
            category="validation",
            message="Uploaded files must contain UTF-8 text",
        ) from error
    if not decoded_content.strip():
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_file",
            category="validation",
            message="Uploaded file must contain non-whitespace UTF-8 text",
        )
    del raw_content, decoded_content

    resolved_source = (source or "").strip() or (file.filename or "").strip()
    if not resolved_source:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_source",
            category="validation",
            message="A non-empty source or filename is required",
        )
    result = core.ingest_file_stream(
        user=user,
        file_stream=file.file,
        source=resolved_source,
    )
    return IngestResponse.from_application(result)
