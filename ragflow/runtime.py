from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minio import Minio
from ollama import Client as OllamaClient
from pymilvus import MilvusClient
from rag_system_core import DocmeshRAGServiceFactory, RAGCore
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    ServiceConfigs,
)
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import StaticPool

from ragflow.health import (
    HealthCheckRunner,
    build_runtime_health_check_runner,
)

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    core: RAGCore
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    health_check_runner: HealthCheckRunner | None = None


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    metadata_database_url: str = "sqlite+pysqlite:///./data/rag-metadata.db"
    chunk_size: int = 512
    chunk_overlap: int = 64
    check_on_startup: bool = True
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES

    def __post_init__(self) -> None:
        if not self.metadata_database_url.strip():
            raise ValueError("metadata_database_url is required")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be non-negative and less than chunk_size")
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be positive")

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        values = os.environ if env is None else env
        return cls(
            metadata_database_url=values.get(
                "RAGFLOW_METADATA_DATABASE_URL",
                "sqlite+pysqlite:///./data/rag-metadata.db",
            ),
            chunk_size=_integer(values, "RAGFLOW_CHUNK_SIZE", default=512),
            chunk_overlap=_integer(values, "RAGFLOW_CHUNK_OVERLAP", default=64),
            check_on_startup=_boolean(
                values.get("RAGFLOW_CHECK_ON_STARTUP"),
                default=True,
            ),
            max_upload_bytes=_integer(
                values,
                "RAGFLOW_MAX_UPLOAD_BYTES",
                default=DEFAULT_MAX_UPLOAD_BYTES,
            ),
        )


@dataclass(frozen=True, slots=True)
class DmsRuntimeSettings:
    metadata_backend: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = False
    sqlite_path: str | None = None
    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_database: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None


RuntimeFactory = Callable[[], AbstractContextManager[RuntimeComponents]]


@contextmanager
def build_runtime(
    env: Mapping[str, str] | None = None,
) -> Iterator[RuntimeComponents]:
    settings = RuntimeSettings.from_env(env)
    rag_settings = _load_rag_service_configs(env)
    dms_settings = load_dms_settings(env)

    with ExitStack() as resources:
        plan = build_docmesh_runtime_plan(
            services={"ollama", "milvus"},
        )
        bundle = assemble_docmesh_services(plan=plan, settings=rag_settings)
        resources.callback(bundle.close)

        dms_engine = _create_dms_engine(dms_settings)
        resources.callback(dms_engine.dispose)
        metadata_engine = _create_metadata_engine(settings.metadata_database_url)
        resources.callback(metadata_engine.dispose)

        minio_client = Minio(
            endpoint=dms_settings.minio_endpoint,
            access_key=dms_settings.minio_access_key,
            secret_key=dms_settings.minio_secret_key,
            secure=dms_settings.minio_secure,
        )
        resources.callback(_close_minio_client, minio_client)

        ollama_settings = rag_settings.ollama
        milvus_settings = rag_settings.milvus
        if ollama_settings is None or milvus_settings is None:
            raise ValueError("Ollama and Milvus settings are required")
        factory = DocmeshRAGServiceFactory.from_host_clients(
            engine=dms_engine,
            metadata_engine=metadata_engine,
            minio_client=minio_client,
            bucket_name=dms_settings.minio_bucket,
            ollama_client=cast(OllamaClient, bundle.get_client("ollama")),
            milvus_client=cast(MilvusClient, bundle.get_client("milvus")),
            embedding_model=_required_value(
                ollama_settings.embedding_model,
                "OLLAMA_EMBEDDING_MODEL",
            ),
            generation_model=_required_value(
                ollama_settings.generation_model,
                "OLLAMA_GENERATION_MODEL",
            ),
            collection_name=milvus_settings.collection or "rag_chunks",
            timeout=float(milvus_settings.request_timeout_seconds),
        )
        resources.callback(factory.close)
        core = factory.create_rag_core(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        close_metadata_store = getattr(core.metadata_store, "close", None)
        if not callable(close_metadata_store):
            raise TypeError("RAG metadata store does not expose close()")
        resources.callback(close_metadata_store)

        health_check_runner = build_runtime_health_check_runner(
            dms_engine=dms_engine,
            metadata_engine=metadata_engine,
            minio_client=minio_client,
            bucket_name=dms_settings.minio_bucket,
            ollama_client=bundle.get_client("ollama"),
            milvus_client=bundle.get_client("milvus"),
        )
        if settings.check_on_startup and not health_check_runner().ok:
            raise RuntimeError("Application dependency health check failed")

        yield RuntimeComponents(
            core=core,
            max_upload_bytes=settings.max_upload_bytes,
            health_check_runner=health_check_runner,
        )


def _load_rag_service_configs(env: Mapping[str, str] | None = None) -> ServiceConfigs:
    values = os.environ if env is None else env
    return ServiceConfigs(
        milvus=MilvusConfig(
            endpoint=_required(values, "MILVUS_ENDPOINT"),
            token=_optional(values, "MILVUS_TOKEN"),
            db_name=values.get("MILVUS_DB_NAME", "default"),
            collection=_optional(values, "MILVUS_COLLECTION"),
            secure=_boolean(values.get("MILVUS_SECURE"), default=False),
            connect_timeout_seconds=_integer(
                values,
                "MILVUS_CONNECT_TIMEOUT_SECONDS",
                default=10,
            ),
            request_timeout_seconds=_integer(
                values,
                "MILVUS_REQUEST_TIMEOUT_SECONDS",
                default=30,
            ),
            max_retries=_integer(values, "MILVUS_MAX_RETRIES", default=3),
        ),
        ollama=OllamaConfig(
            host=_required(values, "OLLAMA_HOST"),
            verify_ssl=_boolean(values.get("OLLAMA_VERIFY_SSL"), default=True),
            follow_redirects=_boolean(
                values.get("OLLAMA_FOLLOW_REDIRECTS"),
                default=True,
            ),
            generation_model=_optional(values, "OLLAMA_GENERATION_MODEL"),
            embedding_model=_optional(values, "OLLAMA_EMBEDDING_MODEL"),
            request_timeout_seconds=_integer(
                values,
                "OLLAMA_REQUEST_TIMEOUT_SECONDS",
                default=120,
            ),
            max_retries=_integer(values, "OLLAMA_MAX_RETRIES", default=2),
        ),
    )


def load_dms_settings(env: Mapping[str, str] | None = None) -> DmsRuntimeSettings:
    """Load host-owned DMS settings; dms-core 0.9 has no environment loader."""
    values = os.environ if env is None else env
    sqlite_path = _optional(values, "DMS_SQLITE_PATH")
    postgres_host = _optional(values, "DMS_POSTGRES_HOST")
    postgres_database = _optional(values, "DMS_POSTGRES_DB")
    postgres_user = _optional(values, "DMS_POSTGRES_USER")
    postgres_password = _optional(values, "DMS_POSTGRES_PASSWORD")
    postgres_configured = any(
        value is not None
        for value in (postgres_host, postgres_database, postgres_user, postgres_password)
    )
    requested_backend = _optional(values, "DMS_METADATA_BACKEND")
    if requested_backend is not None:
        metadata_backend = requested_backend.lower()
    elif postgres_configured:
        metadata_backend = "postgresql"
    elif sqlite_path is not None:
        metadata_backend = "sqlite"
    else:
        raise ValueError("DMS metadata backend configuration is required")

    if metadata_backend not in {"sqlite", "postgresql"}:
        raise ValueError("DMS_METADATA_BACKEND must be sqlite or postgresql")
    if metadata_backend == "sqlite" and sqlite_path is None:
        raise ValueError("DMS_SQLITE_PATH is required for the sqlite DMS backend")
    if metadata_backend == "postgresql" and not all(
        value is not None
        for value in (postgres_host, postgres_database, postgres_user, postgres_password)
    ):
        raise ValueError("DMS PostgreSQL connection settings are incomplete")

    return DmsRuntimeSettings(
        metadata_backend=metadata_backend,
        sqlite_path=sqlite_path,
        postgres_host=postgres_host,
        postgres_port=_integer(values, "DMS_POSTGRES_PORT", default=5432),
        postgres_database=postgres_database,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        minio_endpoint=_required(values, "DMS_MINIO_ENDPOINT"),
        minio_access_key=_required(values, "DMS_MINIO_ACCESS_KEY"),
        minio_secret_key=_required(values, "DMS_MINIO_SECRET_KEY"),
        minio_bucket=_required(values, "DMS_MINIO_BUCKET"),
        minio_secure=_boolean(values.get("DMS_MINIO_SECURE"), default=False),
    )


def _close_minio_client(client: object) -> None:
    # Minio has no public close method; its own destructor clears this pool.
    pool = getattr(client, "_http", None)
    clear = getattr(pool, "clear", None)
    if not callable(clear):
        raise TypeError("MinIO client does not expose a clearable HTTP pool")
    clear()


def _create_dms_engine(settings: DmsRuntimeSettings) -> Engine:
    if settings.metadata_backend == "sqlite":
        assert settings.sqlite_path is not None
        sqlite_path = settings.sqlite_path
        path = Path(sqlite_path).expanduser()
        if str(path) == ":memory:":
            return _create_in_memory_sqlite_engine()
        path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(f"sqlite+pysqlite:///{path}")

    url = URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
    )
    return create_engine(url)


def _create_metadata_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    database = url.database
    if url.drivername.startswith("sqlite") and database == ":memory:":
        return _create_in_memory_sqlite_engine()
    if (
        url.drivername.startswith("sqlite")
        and isinstance(database, str)
        and database not in {"", ":memory:"}
    ):
        path = Path(database).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(path))
    return create_engine(url)


def _create_in_memory_sqlite_engine() -> Engine:
    return create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _required(values: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = _normalize_optional(values.get(key))
        if value is not None:
            return value
    raise ValueError(f"Missing required setting: {' or '.join(keys)}")


def _required_value(value: str | None, key: str) -> str:
    normalized = _normalize_optional(value)
    if normalized is None:
        raise ValueError(f"Missing required setting: {key}")
    return normalized


def _optional(values: Mapping[str, str], key: str) -> str | None:
    return _normalize_optional(values.get(key))


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _integer(values: Mapping[str, str], key: str, *, default: int) -> int:
    value = _optional(values, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{key} must be an integer") from error


def _boolean(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean setting must be true or false")
