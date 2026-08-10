from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from rag_system_core import (
    ChunkRecord,
    DocumentRecord,
    IngestionProgressRecord,
    IngestResult,
    QueryResult,
)

_PUBLIC_CHUNK_METADATA_KEYS = frozenset({"source"})


class ApiErrorIssue(BaseModel):
    location: list[str | int]
    message: str
    type: str


class ApiErrorResponse(BaseModel):
    code: str
    category: str
    retryable: bool
    message: str
    issues: list[ApiErrorIssue] | None = None


class TextIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)

    @field_validator("text", "source")
    @classmethod
    def fields_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class IngestResponse(BaseModel):
    job_id: str
    doc_id: str
    source: str
    created_at: str
    chunk_count: int

    @classmethod
    def from_application(cls, result: IngestResult) -> IngestResponse:
        return cls(
            job_id=result.job_id,
            doc_id=result.doc_id,
            source=result.source,
            created_at=result.created_at,
            chunk_count=result.chunk_count,
        )


class DocumentResponse(BaseModel):
    doc_id: str
    source: str
    created_at: str

    @classmethod
    def from_application(cls, document: DocumentRecord) -> DocumentResponse:
        return cls(
            doc_id=document.doc_id,
            source=document.source,
            created_at=document.created_at,
        )


class ChunkResponse(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict[str, str]

    @classmethod
    def from_application(cls, chunk: ChunkRecord) -> ChunkResponse:
        return cls(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            content=chunk.content,
            metadata={
                key: value
                for key, value in chunk.metadata.items()
                if key in _PUBLIC_CHUNK_METADATA_KEYS
            },
        )


class IngestionProgressResponse(BaseModel):
    progress_id: str
    job_id: str
    doc_id: str
    source: str
    step_name: str
    step_order: int
    status: str
    created_at: str

    @classmethod
    def from_application(
        cls,
        progress: IngestionProgressRecord,
    ) -> IngestionProgressResponse:
        return cls(
            progress_id=progress.progress_id,
            job_id=progress.job_id,
            doc_id=progress.doc_id,
            source=progress.source,
            step_name=progress.step_name,
            step_order=progress.step_order,
            status=progress.status,
            created_at=progress.created_at,
        )


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=100)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class QueryResponse(BaseModel):
    answer: str
    context_chunks: list[ChunkResponse]

    @classmethod
    def from_application(cls, result: QueryResult) -> QueryResponse:
        return cls(
            answer=result.answer,
            context_chunks=[
                ChunkResponse.from_application(chunk) for chunk in result.context_chunks
            ],
        )


class ServiceHealthResponse(BaseModel):
    service: str
    ok: bool
    duration_seconds: float
    error: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    services: list[ServiceHealthResponse]
