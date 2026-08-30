from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from dms import StorageError
from fastapi.testclient import TestClient
from rag_system_core import AuthenticatedUser, RAGCore
from rag_system_core.adapters import FixedWindowChunker
from rag_system_core.storage import MetadataStore
from rag_system_core.types import ChunkRecord, DocumentRecord
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from ragflow.app import create_app


class LocalEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


class LocalGenerationClient:
    def generate(self, prompt: str) -> str:
        question = prompt.rsplit("[User Query]", 1)[-1].strip()
        return f"answer: {question}"


class MemoryVectorStore:
    def __init__(self) -> None:
        self.rows: list[ChunkRecord] = []

    def add(
        self,
        chunks: list[ChunkRecord],
        vectors: list[list[float]],
    ) -> list[str]:
        del vectors
        ids = [f"chunk-{len(self.rows) + index + 1}" for index in range(len(chunks))]
        self.rows.extend(
            ChunkRecord(
                chunk_id=chunk_id,
                doc_id=chunk.doc_id,
                user_id=chunk.user_id,
                content=chunk.content,
                metadata=dict(chunk.metadata),
            )
            for chunk_id, chunk in zip(ids, chunks, strict=True)
        )
        return ids

    def search(
        self,
        *,
        user_id: str,
        query_vector: list[float],
        top_k: int,
    ) -> list[ChunkRecord]:
        del query_vector
        return [row for row in self.rows if row.user_id == user_id][:top_k]

    def delete_document(self, doc_id: str) -> None:
        self.rows = [row for row in self.rows if row.doc_id != doc_id]

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        ids = set(chunk_ids)
        self.rows = [row for row in self.rows if row.chunk_id not in ids]


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store_text(
        self,
        *,
        doc_id: str,
        user_id: str,
        text: str,
        source: str,
        idempotency_key: str,
    ) -> str:
        del user_id, source, idempotency_key
        self.values[doc_id] = text
        return doc_id

    def store_file_stream(
        self,
        *,
        doc_id: str,
        user_id: str,
        file_stream: BinaryIO,
        size: int,
        source: str,
        idempotency_key: str,
    ) -> str:
        del user_id, size, source, idempotency_key
        self.values[doc_id] = file_stream.read().decode("utf-8")
        return doc_id

    def store_file_path(
        self,
        *,
        doc_id: str,
        user_id: str,
        file_path: Path,
        source: str | None = None,
        idempotency_key: str,
    ) -> str:
        del user_id, source, idempotency_key
        self.values[doc_id] = file_path.read_text(encoding="utf-8")
        return doc_id

    def load(self, document: DocumentRecord) -> str | None:
        return self.values.get(document.asset_reference or document.doc_id)

    def delete(self, document: DocumentRecord) -> None:
        self.values.pop(document.asset_reference or document.doc_id, None)


def make_user(sub: str = "user-a") -> AuthenticatedUser:
    return AuthenticatedUser(sub=sub)


@contextmanager
def running_api(
    *,
    raise_server_exceptions: bool = True,
    max_upload_bytes: int = 10 * 1024 * 1024,
) -> Iterator[tuple[TestClient, RAGCore]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata_store = MetadataStore(engine)
    core = RAGCore(
        embedding_client=LocalEmbeddingClient(),
        generation_client=LocalGenerationClient(),
        vector_store=MemoryVectorStore(),
        metadata_store=metadata_store,
        document_storage=MemoryDocumentStorage(),
        chunker=FixedWindowChunker(chunk_size=512, chunk_overlap=64),
    )
    app = create_app(
        core=core,
        max_upload_bytes=max_upload_bytes,
    )
    try:
        with TestClient(
            app,
            raise_server_exceptions=raise_server_exceptions,
        ) as client:
            yield client, core
    finally:
        metadata_store.close()
        engine.dispose()


def user_headers(user_id: str = "user-a") -> dict[str, str]:
    return {"X-User-Id": user_id}


def test_ingest_text_uses_rag_core_and_returns_public_result() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/text",
            headers=user_headers(),
            json={"text": "  FastAPI delegates to RAGCore.  ", "source": "guide.txt"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body.keys() == {
            "job_id",
            "doc_id",
            "source",
            "created_at",
            "chunk_count",
        }
        assert body["source"] == "guide.txt"
        assert body["chunk_count"] == 1
        documents = core.list_documents(user=user)
        assert [document.doc_id for document in documents] == [body["doc_id"]]


def test_list_documents_returns_only_requested_user_public_records() -> None:
    user = make_user()
    other_user = make_user("user-b")
    with running_api() as (client, core):
        own = core.ingest_text(user=user, text="owned", source="owned.txt")
        core.ingest_text(user=other_user, text="hidden", source="hidden.txt")

        response = client.get("/documents", headers=user_headers())

        assert response.status_code == 200
        assert response.json() == [
            {
                "doc_id": own.doc_id,
                "source": "owned.txt",
                "created_at": own.created_at,
            }
        ]


def test_get_document_returns_a_public_record() -> None:
    user = make_user()
    with running_api() as (client, core):
        document = core.ingest_text(user=user, text="owned", source="owned.txt")

        response = client.get(
            f"/documents/{document.doc_id}",
            headers=user_headers(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "doc_id": document.doc_id,
            "source": "owned.txt",
            "created_at": document.created_at,
        }


def test_get_document_hides_records_owned_by_another_user() -> None:
    with running_api() as (client, core):
        hidden = core.ingest_text(
            user=make_user("user-b"),
            text="hidden",
            source="hidden.txt",
        )

        response = client.get(
            f"/documents/{hidden.doc_id}",
            headers=user_headers(),
        )

        assert response.status_code == 404
        assert response.json() == {
            "code": "document_not_found",
            "category": "not_found",
            "retryable": False,
            "message": "Document was not found",
        }


def test_list_document_chunks_returns_public_chunk_data() -> None:
    user = make_user()
    with running_api() as (client, core):
        document = core.ingest_text(user=user, text="chunk body", source="owned.txt")

        response = client.get(
            f"/documents/{document.doc_id}/chunks",
            headers=user_headers(),
        )

        assert response.status_code == 200
        assert response.json() == [
            {
                "chunk_id": "chunk-1",
                "doc_id": document.doc_id,
                "content": "chunk body",
                "metadata": {"source": "owned.txt"},
            }
        ]


def test_chunk_response_filters_internal_metadata() -> None:
    from ragflow.api.schemas import ChunkResponse

    chunk = ChunkRecord(
        chunk_id="chunk-1",
        doc_id="doc-1",
        user_id="user-a",
        content="body",
        metadata={
            "source": "public.txt",
            "asset_reference": "private/object/key",
            "token": "must-not-leak",
        },
    )

    response = ChunkResponse.from_application(chunk)

    assert response.metadata == {"source": "public.txt"}


def test_list_document_chunks_hides_another_users_document() -> None:
    with running_api() as (client, core):
        hidden = core.ingest_text(
            user=make_user("user-b"),
            text="hidden",
            source="hidden.txt",
        )

        response = client.get(
            f"/documents/{hidden.doc_id}/chunks",
            headers=user_headers(),
        )

        assert response.status_code == 404
        assert response.json()["code"] == "document_not_found"


def test_list_ingestion_progress_returns_public_pipeline_transitions() -> None:
    user = make_user()
    with running_api() as (client, core):
        document = core.ingest_text(user=user, text="body", source="owned.txt")

        response = client.get(
            f"/documents/{document.doc_id}/ingestion-progress",
            headers=user_headers(),
            params={"job_id": document.job_id},
        )

        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 12
        assert all("user_id" not in row for row in rows)
        assert rows[0] | {"progress_id": "ignored", "created_at": "ignored"} == {
            "progress_id": "ignored",
            "job_id": document.job_id,
            "doc_id": document.doc_id,
            "source": "owned.txt",
            "step_name": "load",
            "step_order": 0,
            "status": "running",
            "created_at": "ignored",
        }
        assert rows[-1]["step_name"] == "chunk_persistence"
        assert rows[-1]["status"] == "completed"


def test_list_ingestion_progress_hides_another_users_document() -> None:
    with running_api() as (client, core):
        hidden = core.ingest_text(
            user=make_user("user-b"),
            text="hidden",
            source="hidden.txt",
        )

        response = client.get(
            f"/documents/{hidden.doc_id}/ingestion-progress",
            headers=user_headers(),
        )

        assert response.status_code == 404
        assert response.json()["code"] == "document_not_found"


def test_delete_document_delegates_to_rag_core() -> None:
    user = make_user()
    with running_api() as (client, core):
        document = core.ingest_text(user=user, text="body", source="owned.txt")

        response = client.delete(
            f"/documents/{document.doc_id}",
            headers=user_headers(),
        )

        assert response.status_code == 204
        assert response.content == b""
        assert core.get_document(document.doc_id, user=user) is None


def test_delete_document_returns_not_found_for_unknown_document() -> None:
    with running_api() as (client, _):
        response = client.delete(
            "/documents/missing",
            headers=user_headers(),
        )

        assert response.status_code == 404
        assert response.json()["code"] == "document_not_found"


def test_delete_document_hides_and_preserves_another_users_document() -> None:
    owner = make_user("owner")
    other_user = make_user("other")
    with running_api() as (client, core):
        document = core.ingest_text(user=owner, text="private", source="owned.txt")

        response = client.delete(
            f"/documents/{document.doc_id}",
            headers=user_headers(other_user.sub),
        )

        assert response.status_code == 404
        assert response.json()["code"] == "document_not_found"
        assert core.get_document(document.doc_id, user=owner) is not None


def test_ingest_file_stream_uses_upload_filename_as_source() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("notes.txt", "파일 본문".encode(), "text/plain")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["source"] == "notes.txt"
        assert body["chunk_count"] == 1
        chunks = core.list_document_chunks(body["doc_id"], user=user)
        assert [chunk.content for chunk in chunks] == ["파일 본문"]


def test_ingest_file_stream_normalizes_explicit_source() -> None:
    with running_api() as (client, _):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            data={"source": "  imported.txt  "},
            files={"file": ("upload.txt", b"body", "text/plain")},
        )

        assert response.status_code == 201
        assert response.json()["source"] == "imported.txt"


def test_ingest_file_stream_rejects_oversized_upload_before_application_call() -> None:
    user = make_user()
    with running_api(max_upload_bytes=4) as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("notes.txt", b"12345", "text/plain")},
        )

        assert response.status_code == 413
        assert response.json() == {
            "code": "upload_too_large",
            "category": "validation",
            "retryable": False,
            "message": "Uploaded file exceeds the 4 byte limit",
        }
        assert core.list_documents(user=user) == []


def test_request_body_limit_rejects_multipart_before_route_processing() -> None:
    user = make_user()
    with running_api(max_upload_bytes=4) as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("notes.txt", b"x" * (1024 * 1024 + 5), "text/plain")},
        )

        assert response.status_code == 413
        assert response.json() == {
            "code": "request_too_large",
            "category": "validation",
            "retryable": False,
            "message": "Request body is too large",
        }
        assert core.list_documents(user=user) == []


def test_ingest_file_stream_rejects_empty_upload_before_application_call() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("notes.txt", b"", "text/plain")},
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": "empty_upload",
            "category": "validation",
            "retryable": False,
            "message": "Uploaded file must not be empty",
        }
        assert core.list_documents(user=user) == []


def test_ingest_file_stream_rejects_whitespace_only_upload_before_application_call() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("empty.txt", b" \n\t", "text/plain")},
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": "invalid_file",
            "category": "validation",
            "retryable": False,
            "message": "Uploaded file must contain non-whitespace UTF-8 text",
        }
        assert core.list_documents(user=user) == []


def test_query_returns_answer_and_public_user_scoped_context() -> None:
    user = make_user()
    with running_api() as (client, core):
        document = core.ingest_text(
            user=user,
            text="FastAPI is the transport layer.",
            source="architecture.txt",
        )
        core.ingest_text(
            user=make_user("user-b"),
            text="other user's secret",
            source="secret.txt",
        )

        response = client.post(
            "/query",
            headers=user_headers(),
            json={"question": "What is FastAPI?", "top_k": 3},
        )

        assert response.status_code == 200
        assert response.json() == {
            "answer": "answer: What is FastAPI?",
            "context_chunks": [
                {
                    "chunk_id": "chunk-1",
                    "doc_id": document.doc_id,
                    "content": "FastAPI is the transport layer.",
                    "metadata": {"source": "architecture.txt"},
                }
            ],
        }


def test_query_rejects_blank_question() -> None:
    with running_api() as (client, _):
        response = client.post(
            "/query",
            headers=user_headers(),
            json={"question": "   "},
        )

        assert response.status_code == 422
        assert response.json()["issues"][0]["location"] == ["body", "question"]


def test_liveness_does_not_require_user_header() -> None:
    with running_api() as (client, _):
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_readiness_reports_application_dependencies() -> None:
    with running_api() as (client, _):
        response = client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["services"] == [
            {
                "service": "metadata",
                "ok": True,
                "duration_seconds": body["services"][0]["duration_seconds"],
                "error": None,
            }
        ]


def test_readiness_returns_sanitized_service_unavailable() -> None:
    with running_api() as (client, core):

        def fail_health_check() -> None:
            raise RuntimeError("postgresql://user:secret@database")

        core.metadata_store.check = fail_health_check  # type: ignore[method-assign]

        response = client.get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["services"][0]["error"] == "Dependency check failed"
        assert "secret" not in response.text


def test_business_endpoint_requires_direct_user_id() -> None:
    with running_api() as (client, _):
        response = client.get("/documents")

        assert response.status_code == 400
        assert response.json() == {
            "code": "user_id_required",
            "category": "validation",
            "retryable": False,
            "message": "X-User-Id header is required",
        }


def test_text_ingestion_rejects_blank_content_before_application_call() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/text",
            headers=user_headers(),
            json={"text": "   ", "source": "blank.txt"},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "request_validation_failed"
        assert body["category"] == "validation"
        assert body["retryable"] is False
        assert body["message"] == "Request validation failed"
        assert body["issues"][0]["location"] == ["body", "text"]
        assert core.list_documents(user=user) == []


def test_missing_request_body_uses_stable_public_error_contract() -> None:
    with running_api() as (client, _):
        response = client.post(
            "/documents/text",
            headers=user_headers(),
            content=b"",
        )

        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "request_validation_failed"
        assert body["category"] == "validation"
        assert body["retryable"] is False
        assert body["message"] == "Request validation failed"


def test_text_ingestion_rejects_blank_source() -> None:
    with running_api() as (client, _):
        response = client.post(
            "/documents/text",
            headers=user_headers(),
            json={"text": "body", "source": "   "},
        )

        assert response.status_code == 422
        assert response.json()["issues"][0]["location"] == ["body", "source"]


def test_file_ingestion_rejects_non_utf8_content() -> None:
    user = make_user()
    with running_api() as (client, core):
        response = client.post(
            "/documents/file",
            headers=user_headers(),
            files={"file": ("binary.txt", b"\xff\xfe", "text/plain")},
        )

        assert response.status_code == 400
        assert response.json() == {
            "code": "invalid_utf8",
            "category": "validation",
            "retryable": False,
            "message": "Uploaded files must contain UTF-8 text",
        }
        assert core.list_documents(user=user) == []


def test_multipart_parser_error_uses_stable_public_error_contract() -> None:
    with running_api() as (client, _):
        response = client.post(
            "/documents/file",
            headers={
                **user_headers(),
                "Content-Type": "multipart/form-data",
            },
            content=b"not-a-valid-multipart-body",
        )

        assert response.status_code == 400
        assert response.json() == {
            "code": "invalid_request",
            "category": "validation",
            "retryable": False,
            "message": "Request could not be parsed",
        }
        assert "boundary" not in response.text


def test_dms_errors_use_the_host_public_http_projection() -> None:
    with running_api() as (client, core):

        def fail_storage(**_: object) -> str:
            raise StorageError("minio.internal:9000 leaked details")

        core.document_storage.store_text = fail_storage  # type: ignore[method-assign]

        response = client.post(
            "/documents/text",
            headers=user_headers(),
            json={"text": "body", "source": "source.txt"},
        )

        assert response.status_code == 503
        assert response.json() == {
            "code": "object_storage_failed",
            "category": "storage",
            "retryable": True,
            "message": "A storage dependency failed",
        }
        assert "minio.internal" not in response.text


def test_unhandled_application_error_returns_secret_safe_response() -> None:
    user = make_user()
    with running_api(
        raise_server_exceptions=False,
    ) as (client, core):
        core.ingest_text(user=user, text="context", source="source.txt")

        def fail_generation(prompt: str) -> str:
            del prompt
            raise RuntimeError("ollama token=private-value")

        core.generation_client.generate = fail_generation  # type: ignore[method-assign]

        response = client.post(
            "/query",
            headers=user_headers(),
            json={"question": "question"},
        )

        assert response.status_code == 500
        assert response.json() == {
            "code": "internal_error",
            "category": "internal",
            "retryable": False,
            "message": "The request could not be completed",
        }
        assert "private-value" not in response.text
