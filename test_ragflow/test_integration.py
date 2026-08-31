from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from test_ragflow.test_api import running_api, user_headers

TEST_USER_IDS = ("workflow-user", "user-a", "user-b")


def delete_test_documents(client: TestClient) -> None:
    for user_id in TEST_USER_IDS:
        list_response = client.get("/documents", headers=user_headers(user_id))
        assert list_response.status_code == 200
        for document in list_response.json():
            delete_response = client.delete(
                f"/documents/{document['doc_id']}",
                headers=user_headers(user_id),
            )
            assert delete_response.status_code == 204


@contextmanager
def running_default_app() -> Iterator[TestClient]:
    with running_api() as (client, _):
        delete_test_documents(client)
        try:
            yield client
        finally:
            delete_test_documents(client)


def test_document_lifecycle_completes_through_http_boundary() -> None:
    headers = user_headers("workflow-user")

    with running_default_app() as client:
        ingest_response = client.post(
            "/documents/text",
            headers=headers,
            json={
                "text": "FastAPI delegates document retrieval to RAGCore.",
                "source": "workflow.txt",
            },
        )

        assert ingest_response.status_code == 201
        ingest = ingest_response.json()
        assert ingest["source"] == "workflow.txt"
        assert ingest["chunk_count"] == 1

        doc_id = ingest["doc_id"]
        job_id = ingest["job_id"]
        document_response = client.get(f"/documents/{doc_id}", headers=headers)
        assert document_response.status_code == 200
        assert document_response.json() == {
            "doc_id": doc_id,
            "source": "workflow.txt",
            "created_at": ingest["created_at"],
        }

        list_response = client.get("/documents", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json() == [document_response.json()]

        chunks_response = client.get(f"/documents/{doc_id}/chunks", headers=headers)
        assert chunks_response.status_code == 200
        chunks = chunks_response.json()
        assert len(chunks) == 1
        assert chunks[0]["doc_id"] == doc_id
        assert chunks[0]["content"] == "FastAPI delegates document retrieval to RAGCore."
        assert chunks[0]["metadata"] == {"source": "workflow.txt"}

        progress_response = client.get(
            f"/documents/{doc_id}/ingestion-progress",
            headers=headers,
            params={"job_id": job_id},
        )
        assert progress_response.status_code == 200
        progress = progress_response.json()
        assert progress[0]["job_id"] == job_id
        assert progress[0]["doc_id"] == doc_id
        assert progress[-1]["status"] == "completed"

        statuses_response = client.get(
            f"/documents/{doc_id}/ingestion-step-statuses",
            headers=headers,
            params={"job_id": job_id},
        )
        assert statuses_response.status_code == 200
        assert statuses_response.json() == {
            "load": "completed",
            "preprocess": "completed",
            "chunking": "completed",
            "embedding": "completed",
            "vector_store": "completed",
            "chunk_persistence": "completed",
        }

        query_response = client.post(
            "/query",
            headers=headers,
            json={"question": "What does FastAPI delegate?"},
        )
        assert query_response.status_code == 200
        query = query_response.json()
        assert query["answer"]
        assert query["context_chunks"] == chunks

        delete_response = client.delete(f"/documents/{doc_id}", headers=headers)
        assert delete_response.status_code == 204
        assert delete_response.content == b""

        assert client.get("/documents", headers=headers).json() == []
        assert client.get(f"/documents/{doc_id}", headers=headers).status_code == 404
        assert (
            client.post(
                "/query",
                headers=headers,
                json={"question": "What remains?"},
            ).json()["context_chunks"]
            == []
        )


def test_http_user_scope_isolated_for_ingest_query_and_delete() -> None:
    user_a_headers = user_headers("  user-a  ")
    user_b_headers = user_headers("user-b")

    with running_default_app() as client:
        user_a_ingest = client.post(
            "/documents/text",
            headers=user_a_headers,
            json={"text": "private context for user A", "source": "a.txt"},
        )
        user_b_ingest = client.post(
            "/documents/text",
            headers=user_b_headers,
            json={"text": "private context for user B", "source": "b.txt"},
        )

        assert user_a_ingest.status_code == 201
        assert user_b_ingest.status_code == 201
        user_a_doc_id = user_a_ingest.json()["doc_id"]
        user_b_doc_id = user_b_ingest.json()["doc_id"]

        user_a_list = client.get("/documents", headers=user_headers("user-a"))
        user_b_list = client.get("/documents", headers=user_b_headers)
        assert [document["doc_id"] for document in user_a_list.json()] == [user_a_doc_id]
        assert [document["doc_id"] for document in user_b_list.json()] == [user_b_doc_id]

        user_a_query = client.post(
            "/query",
            headers=user_headers("user-a"),
            json={"question": "What is private?"},
        )
        user_b_query = client.post(
            "/query",
            headers=user_b_headers,
            json={"question": "What is private?"},
        )
        assert user_a_query.status_code == 200
        assert user_b_query.status_code == 200
        assert [chunk["doc_id"] for chunk in user_a_query.json()["context_chunks"]] == [
            user_a_doc_id
        ]
        assert [chunk["doc_id"] for chunk in user_b_query.json()["context_chunks"]] == [
            user_b_doc_id
        ]

        cross_user_delete = client.delete(
            f"/documents/{user_a_doc_id}",
            headers=user_b_headers,
        )
        assert cross_user_delete.status_code == 404
        assert (
            client.get(
                f"/documents/{user_a_doc_id}",
                headers=user_headers("user-a"),
            ).status_code
            == 200
        )

        own_delete = client.delete(
            f"/documents/{user_b_doc_id}",
            headers=user_b_headers,
        )
        assert own_delete.status_code == 204
        assert client.get("/documents", headers=user_b_headers).json() == []
        assert [
            document["doc_id"]
            for document in client.get("/documents", headers=user_headers("user-a")).json()
        ] == [user_a_doc_id]
