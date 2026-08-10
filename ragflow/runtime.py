from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import dms
from minio import Minio
from rag_system_core import DocmeshRAGServiceFactory, RAGCore
from rag_system_core.composition.dms_runtime import load_dms_settings
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import StaticPool

from ragflow.auth import Authenticator, KeycloakAuthenticator, KeycloakSettings

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_DOCMESH_ENV_PREFIXES = ("DOCMESH_", "MILVUS_", "OLLAMA_")
_DOCMESH_ENVIRONMENT_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    core: RAGCore
    authenticator: Authenticator
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    keycloak: KeycloakSettings
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
            keycloak=KeycloakSettings(
                base_url=_required(values, "KEYCLOAK_URL", "KEYCLOAK__HTTP_URL"),
                realm=_required(values, "KEYCLOAK_REALM", "KEYCLOAK__REALM"),
                client_id=_required(
                    values,
                    "KEYCLOAK_CLIENT_ID",
                    "KEYCLOAK__CLIENT_ID",
                ),
                allow_insecure_http=_boolean(
                    values.get("KEYCLOAK_ALLOW_INSECURE_HTTP"),
                    default=False,
                ),
            ),
            metadata_database_url=values.get(
                "RAGFLOW_METADATA_DATABASE_URL",
                "sqlite+pysqlite:///./data/rag-metadata.db",
            ),
            chunk_size=int(values.get("RAGFLOW_CHUNK_SIZE", "512")),
            chunk_overlap=int(values.get("RAGFLOW_CHUNK_OVERLAP", "64")),
            check_on_startup=_boolean(
                values.get("RAGFLOW_CHECK_ON_STARTUP"),
                default=True,
            ),
            max_upload_bytes=int(
                values.get("RAGFLOW_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
            ),
        )


RuntimeFactory = Callable[[], AbstractContextManager[RuntimeComponents]]


@contextmanager
def build_runtime(
    env: Mapping[str, str] | None = None,
) -> Iterator[RuntimeComponents]:
    settings = RuntimeSettings.from_env(env)
    authenticator = KeycloakAuthenticator(settings=settings.keycloak)

    with ExitStack() as resources:
        with _docmesh_configuration_environment(env):
            plan = build_docmesh_runtime_plan(
                services={"ollama", "milvus"},
                required={"ollama", "milvus"},
                check_on_startup=settings.check_on_startup,
                parallel_healthchecks=True,
            )
            bundle = assemble_docmesh_services(plan=plan)
        resources.callback(bundle.close)

        dms_settings = load_dms_settings(env)
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
        embedding_client = create_rag_embedding_client(bundle=bundle)
        generation_client = create_rag_generation_client(bundle=bundle)
        vector_store = create_rag_vector_store(bundle=bundle)

        factory = DocmeshRAGServiceFactory.from_clients(
            engine=dms_engine,
            metadata_engine=metadata_engine,
            minio_client=minio_client,
            bucket_name=dms_settings.minio_bucket,
            embedding_client=embedding_client,
            generation_client=generation_client,
            vector_store=vector_store,
            check_on_startup=settings.check_on_startup,
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

        yield RuntimeComponents(
            core=core,
            authenticator=authenticator,
            max_upload_bytes=settings.max_upload_bytes,
        )


@contextmanager
def _docmesh_configuration_environment(
    env: Mapping[str, str] | None,
) -> Iterator[None]:
    if env is None:
        yield
        return

    def is_docmesh_key(key: str) -> bool:
        return key.upper().startswith(_DOCMESH_ENV_PREFIXES)

    with _DOCMESH_ENVIRONMENT_LOCK:
        original_values = {key: value for key, value in os.environ.items() if is_docmesh_key(key)}
        replacement_values = {key: value for key, value in env.items() if is_docmesh_key(key)}
        try:
            for key in tuple(os.environ):
                if is_docmesh_key(key):
                    del os.environ[key]
            os.environ.update(replacement_values)
            yield
        finally:
            for key in tuple(os.environ):
                if is_docmesh_key(key):
                    del os.environ[key]
            os.environ.update(original_values)


def _close_minio_client(client: object) -> None:
    # Minio has no public close method; its own destructor clears this pool.
    pool = getattr(client, "_http", None)
    clear = getattr(pool, "clear", None)
    if not callable(clear):
        raise TypeError("MinIO client does not expose a clearable HTTP pool")
    clear()


def _create_dms_engine(settings: dms.DmsServiceConfigs) -> Engine:
    sqlite_path = settings.sqlite_path
    if sqlite_path is not None:
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
        value = values.get(key)
        if value is not None and value.strip():
            return value.strip()
    raise ValueError(f"Missing required setting: {' or '.join(keys)}")


def _boolean(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean setting must be true or false")
