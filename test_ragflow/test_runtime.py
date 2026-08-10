from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from ragflow import runtime
from ragflow.runtime import RuntimeSettings


def test_runtime_settings_load_host_owned_api_configuration() -> None:
    settings = RuntimeSettings.from_env(
        {
            "KEYCLOAK__HTTP_URL": "https://identity.example/",
            "KEYCLOAK__REALM": "docmesh",
            "KEYCLOAK__CLIENT_ID": "rag-api",
            "KEYCLOAK_ALLOW_INSECURE_HTTP": "true",
            "RAGFLOW_METADATA_DATABASE_URL": "sqlite+pysqlite:///./data/test.db",
            "RAGFLOW_CHUNK_SIZE": "1024",
            "RAGFLOW_CHUNK_OVERLAP": "128",
            "RAGFLOW_CHECK_ON_STARTUP": "false",
            "RAGFLOW_MAX_UPLOAD_BYTES": "2048",
        }
    )

    assert settings.keycloak.base_url == "https://identity.example/"
    assert settings.keycloak.realm == "docmesh"
    assert settings.keycloak.client_id == "rag-api"
    assert settings.keycloak.allow_insecure_http is True
    assert settings.metadata_database_url == "sqlite+pysqlite:///./data/test.db"
    assert settings.chunk_size == 1024
    assert settings.chunk_overlap == 128
    assert settings.check_on_startup is False
    assert settings.max_upload_bytes == 2048


def test_runtime_settings_reject_invalid_chunk_window() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RuntimeSettings.from_env(
            {
                "KEYCLOAK_URL": "https://identity.example/",
                "KEYCLOAK_REALM": "docmesh",
                "KEYCLOAK_CLIENT_ID": "rag-api",
                "RAGFLOW_CHUNK_SIZE": "64",
                "RAGFLOW_CHUNK_OVERLAP": "64",
            }
        )


def test_explicit_runtime_mapping_temporarily_drives_docmesh_loaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://process.example")
    monkeypatch.setenv("MILVUS_ENDPOINT", "process.db")
    monkeypatch.setenv("UNRELATED_SETTING", "preserved")

    with runtime._docmesh_configuration_environment(
        {
            "OLLAMA_HOST": "http://mapping.example",
            "MILVUS_ENDPOINT": "mapping.db",
        }
    ):
        assert os.environ["OLLAMA_HOST"] == "http://mapping.example"
        assert os.environ["MILVUS_ENDPOINT"] == "mapping.db"
        assert os.environ["UNRELATED_SETTING"] == "preserved"

    assert os.environ["OLLAMA_HOST"] == "http://process.example"
    assert os.environ["MILVUS_ENDPOINT"] == "process.db"


def test_build_runtime_closes_every_host_owned_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class Closeable:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            events.append(self.name)

        def dispose(self) -> None:
            events.append(self.name)

    bundle = Closeable("bundle")
    bundle.configs = object()  # type: ignore[attr-defined]
    dms_engine = Closeable("dms-engine")
    metadata_engine = Closeable("metadata-engine")
    metadata_store = Closeable("metadata-store")
    core = SimpleNamespace(metadata_store=metadata_store)
    factory = Closeable("factory")
    factory.create_rag_core = lambda **_: core  # type: ignore[attr-defined]
    captured: dict[str, object] = {}

    class FactoryType:
        @classmethod
        def from_clients(cls, **kwargs: object) -> Closeable:
            captured.update(kwargs)
            return factory

    monkeypatch.setattr(runtime, "build_docmesh_runtime_plan", lambda **_: object())
    monkeypatch.setattr(runtime, "assemble_docmesh_services", lambda **_: bundle)
    monkeypatch.setattr(
        runtime,
        "load_dms_settings",
        lambda _: SimpleNamespace(
            minio_endpoint="minio:9000",
            minio_access_key="access",
            minio_secret_key="secret",
            minio_bucket="documents",
            minio_secure=False,
        ),
    )
    monkeypatch.setattr(runtime, "_create_dms_engine", lambda _: dms_engine)
    monkeypatch.setattr(runtime, "_create_metadata_engine", lambda _: metadata_engine)

    class HttpPool:
        def clear(self) -> None:
            events.append("minio-http")

    minio_client = SimpleNamespace(_http=HttpPool())
    monkeypatch.setattr(runtime, "Minio", lambda **_: minio_client)
    embedding = object()
    generation = object()
    vectors = object()
    monkeypatch.setattr(runtime, "create_rag_embedding_client", lambda **_: embedding)
    monkeypatch.setattr(runtime, "create_rag_generation_client", lambda **_: generation)
    monkeypatch.setattr(runtime, "create_rag_vector_store", lambda **_: vectors)
    monkeypatch.setattr(runtime, "DocmeshRAGServiceFactory", FactoryType)

    env = {
        "KEYCLOAK_URL": "https://identity.example/",
        "KEYCLOAK_REALM": "docmesh",
        "KEYCLOAK_CLIENT_ID": "rag-api",
    }
    with runtime.build_runtime(env) as components:
        assert components.core is core
        assert captured["engine"] is dms_engine
        assert captured["metadata_engine"] is metadata_engine
        assert captured["minio_client"] is minio_client
        assert captured["embedding_client"] is embedding
        assert captured["generation_client"] is generation
        assert captured["vector_store"] is vectors
        assert events == []

    assert events == [
        "metadata-store",
        "factory",
        "minio-http",
        "metadata-engine",
        "dms-engine",
        "bundle",
    ]


def test_in_memory_metadata_database_is_shared_with_fastapi_worker_threads() -> None:
    engine = runtime._create_metadata_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (value INTEGER NOT NULL)"))
            connection.execute(text("INSERT INTO probe (value) VALUES (1)"))

        def read_from_worker() -> int:
            with engine.connect() as connection:
                return connection.execute(text("SELECT value FROM probe")).scalar_one()

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(read_from_worker).result() == 1
    finally:
        engine.dispose()
