from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from ragflow import runtime
from ragflow.runtime import RuntimeSettings


def test_runtime_settings_load_host_owned_configuration() -> None:
    settings = RuntimeSettings.from_env(
        {
            "RAGFLOW_METADATA_DATABASE_URL": "sqlite+pysqlite:///./data/test.db",
            "RAGFLOW_CHUNK_SIZE": "1024",
            "RAGFLOW_CHUNK_OVERLAP": "128",
            "RAGFLOW_CHECK_ON_STARTUP": "false",
            "RAGFLOW_MAX_UPLOAD_BYTES": "2048",
        }
    )

    assert settings.metadata_database_url == "sqlite+pysqlite:///./data/test.db"
    assert settings.chunk_size == 1024
    assert settings.chunk_overlap == 128
    assert settings.check_on_startup is False
    assert settings.max_upload_bytes == 2048


def test_runtime_settings_reject_invalid_chunk_window() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RuntimeSettings.from_env(
            {
                "RAGFLOW_CHUNK_SIZE": "64",
                "RAGFLOW_CHUNK_OVERLAP": "64",
            }
        )


def test_explicit_runtime_mapping_builds_rag_service_settings_without_mutating_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://process.example")
    monkeypatch.setenv("MILVUS_ENDPOINT", "process.db")
    monkeypatch.setenv("UNRELATED_SETTING", "preserved")

    settings = runtime._load_rag_service_configs(
        {
            "OLLAMA_HOST": "http://mapping.example",
            "OLLAMA_EMBEDDING_MODEL": "embedding-model",
            "OLLAMA_GENERATION_MODEL": "generation-model",
            "MILVUS_ENDPOINT": "mapping.db",
            "MILVUS_COLLECTION": "mapping_chunks",
        }
    )

    assert settings.ollama is not None
    assert settings.ollama.host == "http://mapping.example"
    assert settings.ollama.embedding_model == "embedding-model"
    assert settings.ollama.generation_model == "generation-model"
    assert settings.milvus is not None
    assert settings.milvus.endpoint == "mapping.db"
    assert settings.milvus.collection == "mapping_chunks"
    assert os.environ["OLLAMA_HOST"] == "http://process.example"
    assert os.environ["MILVUS_ENDPOINT"] == "process.db"
    assert os.environ["UNRELATED_SETTING"] == "preserved"


def test_load_dms_settings_reads_host_owned_configuration() -> None:
    settings = runtime.load_dms_settings(
        {
            "DMS_METADATA_BACKEND": "sqlite",
            "DMS_SQLITE_PATH": ":memory:",
            "DMS_MINIO_ENDPOINT": "minio:9000",
            "DMS_MINIO_ACCESS_KEY": "access",
            "DMS_MINIO_SECRET_KEY": "secret",
            "DMS_MINIO_BUCKET": "documents",
        }
    )

    assert settings.metadata_backend == "sqlite"
    assert settings.sqlite_path == ":memory:"
    assert settings.minio_endpoint == "minio:9000"
    assert settings.minio_bucket == "documents"


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
    raw_ollama_client = object()
    raw_milvus_client = object()
    bundle.get_client = lambda service: {  # type: ignore[attr-defined]
        "ollama": raw_ollama_client,
        "milvus": raw_milvus_client,
    }[service]
    dms_engine = Closeable("dms-engine")
    metadata_engine = Closeable("metadata-engine")
    metadata_store = Closeable("metadata-store")
    core = SimpleNamespace(metadata_store=metadata_store)
    factory = Closeable("factory")
    factory.create_rag_core = lambda **_: core  # type: ignore[attr-defined]
    captured: dict[str, object] = {}
    plan_arguments: dict[str, object] = {}

    class FactoryType:
        @classmethod
        def from_host_clients(
            cls,
            *,
            engine: object,
            metadata_engine: object,
            minio_client: object,
            bucket_name: str,
            ollama_client: object,
            milvus_client: object,
            embedding_model: str,
            generation_model: str,
            collection_name: str,
            timeout: float,
        ) -> Closeable:
            del cls
            captured.update(
                {
                    "engine": engine,
                    "metadata_engine": metadata_engine,
                    "minio_client": minio_client,
                    "bucket_name": bucket_name,
                    "ollama_client": ollama_client,
                    "milvus_client": milvus_client,
                    "embedding_model": embedding_model,
                    "generation_model": generation_model,
                    "collection_name": collection_name,
                    "timeout": timeout,
                }
            )
            return factory

    def build_plan(*, services: set[str]) -> object:
        plan_arguments["services"] = services
        return object()

    monkeypatch.setattr(runtime, "build_docmesh_runtime_plan", build_plan)
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
    monkeypatch.setattr(runtime, "DocmeshRAGServiceFactory", FactoryType)

    env = {
        "OLLAMA_HOST": "http://ollama.example",
        "OLLAMA_EMBEDDING_MODEL": "embedding-model",
        "OLLAMA_GENERATION_MODEL": "generation-model",
        "MILVUS_ENDPOINT": "milvus.example",
        "RAGFLOW_CHECK_ON_STARTUP": "false",
    }
    with runtime.build_runtime(env) as components:
        assert components.core is core
        assert plan_arguments["services"] == {"ollama", "milvus"}
        assert captured["engine"] is dms_engine
        assert captured["metadata_engine"] is metadata_engine
        assert captured["minio_client"] is minio_client
        assert captured["ollama_client"] is raw_ollama_client
        assert captured["milvus_client"] is raw_milvus_client
        assert captured["embedding_model"] == "embedding-model"
        assert captured["generation_model"] == "generation-model"
        assert captured["collection_name"] == "rag_chunks"
        assert captured["timeout"] == 30.0
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
