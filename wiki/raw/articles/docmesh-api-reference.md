---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/API-Reference
ingested: 2026-08-20
sha256: 3c82155cb4aafe6ec87ea9da10e1e08931cd8cef487e77d6507871f648572e6f
---
# 공개 API 레퍼런스

이 문서는 `rag-system-core`를 다른 애플리케이션·서비스에서 재사용하기 위한 **현재 구현 기준 공개 Python API 계약**입니다. package root와 각 모듈의 비어 있지 않은 `__all__`을 기준으로 공개 export를 추적합니다.

문서에 없는 내부 함수·모듈은 호환성 계약으로 간주하지 마십시오. 정상 애플리케이션은 package root 또는 아래에 명시된 public submodule/advanced module import를 사용해야 합니다.

- package: `rag-system-core` `0.4.0` (`pyproject.toml`)
- Python: `>=3.11`
- declared runtime dependencies: `dms-core>=0.9.0`, `ollama>=0.6.2`, `pydantic-settings>=2.14.1`, `pymilvus[milvus-lite]>=3.0.1`
- 실행 예제: [Examples](Examples)
- 설정·lifecycle: [Configuration](Configuration)

> 현재 구현은 환경변수만으로 완성된 `RAGCore`를 반환하는 bootstrap helper를 제공하지 않습니다. `ServiceConfigs`, `ServiceBundle`, host-owned raw client 또는 직접 주입한 collaborator를 명시적으로 준비해야 합니다.

## 1. Public import 규칙

### Package root

일반 애플리케이션은 다음 import를 안정적인 public facade로 사용합니다.

```python
from rag_system_core import (
    AuthenticatedUser,
    ChunkRecord,
    DocumentRecord,
    EmbeddingClient,
    GenerationClient,
    IngestionProgressRecord,
    IngestResult,
    OllamaEmbeddingClient,
    OllamaGenerationClient,
    QueryResult,
    RAGCore,
    DocmeshRAGServiceFactory,
    RAGServiceFactory,
)
```

### Public submodule / advanced module

- `rag_system_core.adapters`: `FixedWindowChunker`
- `rag_system_core.ports`: dependency protocols
- `rag_system_core.composition`: assembly facade와 health
- `rag_system_core.composition.configuration`: explicit config models
- `rag_system_core.composition.docmesh_runtime`: plan, bundle, runtime client helper
- `rag_system_core.composition.health`: health result/status model
- `rag_system_core.composition.rag_factories`: RAG adapter factory functions
- `rag_system_core.composition.factories`: 위 factory와 Factory type의 compatibility re-export
- `rag_system_core.composition.service_factory`: Factory 구현의 advanced path
- `rag_system_core.storage`: storage 구현과 ORM models
- `rag_system_core.storage.dms_document_storage`: `DocumentManagementSdk` alias
- `rag_system_core.domain.core`: user-id를 직접 받는 advanced domain service
- `rag_system_core.types`: public record과 protocol compatibility re-export

내부 구현 경로에 우연히 존재하는 이름은 문서화된 public export가 아니면 사용하지 마십시오.

## 2. Public records와 user model

### `AuthenticatedUser`

Canonical import: `rag_system_core.types.AuthenticatedUser` 또는 `rag_system_core.AuthenticatedUser`

```text
AuthenticatedUser(sub: str)
```

`sub`가 저장·검색에 쓰이는 resolved `user_id`입니다. 인증, token 검증, 사용자 객체 생성은 호출 애플리케이션의 책임입니다.

### Dataclass records

| 타입 | Canonical import | 필드 |
|---|---|---|
| `DocumentRecord` | `rag_system_core.types` | `doc_id: str`, `user_id: str`, `source: str`, `created_at: str`, `asset_reference: str | None = None` |
| `ChunkRecord` | `rag_system_core.types` | `chunk_id: str`, `doc_id: str`, `user_id: str`, `content: str`, `metadata: dict[str, str] = {}` |
| `IngestResult` | `rag_system_core.types` | `job_id: str`, `doc_id: str`, `user_id: str`, `source: str`, `created_at: str`, `chunk_count: int` |
| `IngestionProgressRecord` | `rag_system_core.types` | `progress_id: str`, `job_id: str`, `doc_id: str`, `user_id: str`, `source: str`, `step_name: str`, `step_order: int`, `status: str`, `created_at: str` |
| `QueryResult` | `rag_system_core.types` | `answer: str`, `prompt: str`, `context_chunks: list[ChunkRecord]` |

`IngestionProgressRecord.status`는 현재 `running`, `completed`, `failed`에 사용됩니다. tracked pipeline 순서는 `load`, `preprocess`, `chunking`, `embedding`, `vector_store`, `chunk_persistence`입니다.

## 3. Port protocol 계약

Canonical import: `rag_system_core.ports`

### `EmbeddingClient`

```text
embed(texts: list[str]) -> list[list[float]]
```

입력 순서에 대응하는 embedding 목록을 반환해야 합니다. ingestion은 모든 chunk를 한 번에 전달합니다.

### `GenerationClient`

```text
generate(prompt: str) -> str
```

완성된 prompt에 대한 답변 문자열을 반환해야 합니다.

### `Chunker`

```text
chunk(text: str) -> list[str]
```

text를 chunk 목록으로 나눕니다. 빈 결과는 ingestion에서 `ValueError`로 처리됩니다.

### `VectorStore`

```text
add(chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]
search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
delete_document(doc_id: str) -> None
delete_chunks(chunk_ids: list[str]) -> None
```

`add`는 chunk 수와 같은 수의 ID를 반환해야 합니다. `search`는 반드시 `user_id` scope를 적용해야 합니다.

### `MetadataRepository`

```text
add_document(document: DocumentRecord) -> None
add_chunks(chunks: list[ChunkRecord]) -> None
delete_chunks(chunk_ids: list[str]) -> None
add_ingestion_progress(progress_rows: list[IngestionProgressRecord]) -> None
get_document_for_user(*, doc_id: str, user_id: str) -> DocumentRecord | None
list_documents(user_id: str) -> list[DocumentRecord]
list_document_chunks(*, doc_id: str, user_id: str) -> list[ChunkRecord]
list_ingestion_progress(
    *, doc_id: str, user_id: str, job_id: str | None = None
) -> list[IngestionProgressRecord]
delete_document(*, doc_id: str, user_id: str) -> DocumentRecord | None
check() -> None
```

user 범위를 받는 조회·삭제 메서드는 반드시 `user_id`를 적용해야 합니다.

### `DocumentAssetStorage`

```text
store_text(
    *, doc_id: str, user_id: str, text: str, source: str, idempotency_key: str
) -> str
store_file_stream(
    *, doc_id: str, user_id: str, file_stream: BinaryIO, size: int,
    source: str, idempotency_key: str
) -> str
store_file_path(
    *, doc_id: str, user_id: str, file_path: Path,
    source: str | None = None, idempotency_key: str
) -> str
load(document: DocumentRecord) -> str | None
delete(document: DocumentRecord) -> None
```

저장 메서드는 opaque asset reference를 반환해야 합니다. stream은 caller-owned이며 adapter가 임의로 닫아서는 안 됩니다.

### `HealthCheckRunner`

```text
__call__(
    service_checks: dict[str, Callable[[], None]],
    required_services: set[str] | None = None,
) -> object
```

`RAGCore.health_check()`가 metadata와 선택 dependency check를 전달하는 callable입니다. 기본 runner는 `run_health_checks`입니다.

## 4. `RAGCore` facade

Canonical import: `from rag_system_core import RAGCore`

### 생성자

```text
RAGCore(
    *,
    embedding_client: EmbeddingClient,
    generation_client: GenerationClient,
    vector_store: VectorStore,
    metadata_store: MetadataRepository,
    document_storage: DocumentAssetStorage,
    chunker: Chunker,
    health_check_runner: HealthCheckRunner,
) -> None
```

모든 의존성이 필수인 dependency-injection 생성자입니다. `RAGCore`는 주입된 client/store lifecycle을 소유하지 않으며 공통 `close()`를 제공하지 않습니다.

### Ingestion

```text
ingest_text(*, user: AuthenticatedUser, text: str, source: str) -> IngestResult
ingest_file_stream(
    *, user: AuthenticatedUser, file_stream: BinaryIO,
    source: str | None = None
) -> IngestResult
ingest_file_path(
    *, user: AuthenticatedUser, file_path: str | Path,
    source: str | None = None
) -> IngestResult
```

- `user.sub`를 `user_id`로 사용합니다.
- file stream/path는 UTF-8 text로 decode합니다.
- `ingest_file_stream`에서 `source`가 없거나 공백이면 `ValueError`입니다.
- `ingest_file_path`의 source 기본값은 파일명입니다.
- `ingest_text`는 text를 `strip()`한 뒤 asset을 저장합니다.
- embedding은 chunk 전체를 batch로 요청합니다.
- text upload는 `job_id`를 DMS idempotency key로 전달합니다. 현재 DMS file-stream/path adapter는 해당 key를 DMS request에 전달하지 않습니다.
- vector ID 수 불일치 또는 chunk metadata 저장 실패 시 vector 삭제를 시도합니다. 전체 ingestion을 distributed transaction처럼 rollback하지는 않습니다.

### Retrieval / generation

```text
query(*, user: AuthenticatedUser, question: str, top_k: int = 3) -> QueryResult
```

질문을 embedding하고 user scope로 vector 검색한 뒤 generation client를 호출합니다. prompt는 `[System Prompt]`, `[Retrieved Context]`, `[User Query]` 섹션을 포함합니다.

### Document management

```text
list_documents(*, user: AuthenticatedUser) -> list[DocumentRecord]
get_document(doc_id: str, *, user: AuthenticatedUser) -> DocumentRecord | None
list_document_chunks(doc_id: str, *, user: AuthenticatedUser) -> list[ChunkRecord]
list_ingestion_progress(
    doc_id: str, *, user: AuthenticatedUser,
    job_id: str | None = None
) -> list[IngestionProgressRecord]
delete_document(doc_id: str, *, user: AuthenticatedUser) -> bool
```

다른 사용자의 문서는 조회 대상이 아니며, user-scoped document가 없으면 삭제는 `False`입니다. 삭제 순서는 vector → document asset soft delete → RAG metadata/chunk/progress입니다. 중간 실패 시 이미 삭제된 artifact가 있을 수 있으며 distributed rollback은 제공하지 않습니다.

### Health

```text
health_check() -> object
```

항상 metadata check를 포함하고 `check()`를 제공하는 vector, embedding, generation, document-storage collaborator를 추가합니다. 기본 `run_health_checks` runner를 사용하면 반환값은 `HealthCheckResult`입니다.

## 5. Composition API

### `RAGServiceFactory`

Canonical imports: `rag_system_core.RAGServiceFactory`, `rag_system_core.composition.RAGServiceFactory`, `rag_system_core.composition.service_factory.RAGServiceFactory`

```text
create_embedding_client() -> EmbeddingClient
create_generation_client() -> GenerationClient
create_vector_store() -> VectorStore
create_document_storage() -> DocumentAssetStorage
create_metadata_store(*, metadata_path: str | Path | None = None) -> MetadataRepository
create_chunker(*, chunk_size: int, chunk_overlap: int) -> Chunker
```

구조적 typing protocol입니다. `health_check_runner`는 Factory protocol이 직접 생성하지 않으며 caller가 `RAGCore`에 전달합니다.

### `DocmeshRAGServiceFactory`

Canonical import: `rag_system_core.DocmeshRAGServiceFactory`

Direct constructor:

```text
DocmeshRAGServiceFactory(
    dms_sdk: dms.DefaultDocumentManagementSDK,
    owns_dms_sdk: bool = False,
    embedding_client: EmbeddingClient | None = None,
    generation_client: GenerationClient | None = None,
    vector_store: VectorStore | None = None,
    metadata_engine: sqlalchemy.engine.Engine | None = None,
) -> None
```

`owns_dms_sdk`는 source compatibility를 위해 보존된 필드이며 현재 `close()`에서 DMS SDK를 닫는 소유권을 만들지 않습니다.

```text
@classmethod
from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
    embedding_client: EmbeddingClient,
    generation_client: GenerationClient,
    vector_store: VectorStore,
    metadata_engine: sqlalchemy.engine.Engine | None = None,
    check_on_startup: bool = False,
) -> DocmeshRAGServiceFactory

@classmethod
from_host_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    metadata_engine: sqlalchemy.engine.Engine,
    minio_client: minio.Minio,
    bucket_name: str,
    ollama_client: ollama.Client,
    milvus_client: pymilvus.MilvusClient,
    embedding_model: str,
    generation_model: str,
    collection_name: str = "rag_chunks",
    timeout: float = 30.0,
    check_on_startup: bool = True,
) -> DocmeshRAGServiceFactory
```

- `from_clients`는 host-owned DMS Engine/MinIO와 이미 만든 RAG collaborator를 받아 dms-core SDK를 생성합니다.
- `from_host_clients`는 Ollama/Milvus raw client로 RAG adapter를 만들고 `from_clients`에 위임합니다.
- `metadata_engine`은 signature에서는 optional이지만 `create_rag_core()` 정상 경로에는 필요합니다. 없으면 `create_metadata_store(metadata_path=...)`를 별도로 호출합니다.
- 두 classmethod는 RAG/DMS 환경변수를 읽지 않습니다.
- `check_on_startup`은 classmethod에서 호환성을 위해 받지만 startup health check를 실행하지 않습니다. startup check는 `RuntimePlan` + `assemble_docmesh_services` 경로에서 사용합니다.

Factory methods:

```text
create_embedding_client() -> EmbeddingClient
create_generation_client() -> GenerationClient
create_vector_store() -> VectorStore
create_document_storage() -> DmsDocumentStorage
create_metadata_store(*, metadata_path: str | Path | None = None) -> MetadataStore
create_chunker(*, chunk_size: int, chunk_overlap: int) -> FixedWindowChunker
create_rag_core(
    *, chunk_size: int = 512, chunk_overlap: int = 64,
    health_check_runner: HealthCheckRunner = run_health_checks
) -> RAGCore
close() -> None
__enter__() -> DocmeshRAGServiceFactory
__exit__(...) -> None
```

Factory context는 dms-core v0.9 SDK, host-owned Engine/MinIO/transport client, 주입 collaborator를 닫지 않습니다. Factory가 `metadata_path`로 생성해 추적한 `MetadataStore`만 `close()`에서 정리합니다. `metadata_engine`을 주입한 store는 caller-owned입니다.

### RAG adapter factory functions

Canonical import: `rag_system_core.composition.rag_factories`; compatibility import: `rag_system_core.composition.factories`

```text
create_rag_embedding_client(
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    model: str | None = None,
    client: object | None = None,
) -> EmbeddingClient

create_rag_generation_client(
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    model: str | None = None,
    client: object | None = None,
) -> GenerationClient

create_rag_vector_store(
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    collection_name: str | None = None,
    timeout: float | None = None,
    client: object | None = None,
) -> VectorStore
```

Explicit argument가 없으면 settings/bundle 설정을 사용하고, vector collection은 `rag_chunks`, timeout은 `30.0`을 기본값으로 사용합니다. client를 만들 수 없으면 `RuntimeError`, 빈 Ollama model은 `ValueError`입니다.

### Configuration types

Canonical import: `rag_system_core.composition.configuration`

```text
ConfigError(ValueError)
HealthcheckPolicy(on_startup: bool = False, parallel: bool = False)
MilvusConfig(
    *, endpoint: str, token: str | None = None, db_name: str = "default",
    collection: str | None = None, secure: bool = False,
    connect_timeout_seconds: int = 10,
    request_timeout_seconds: int = 30,
    max_retries: int = 3,
)
OllamaConfig(
    *, host: str, verify_ssl: bool = True, follow_redirects: bool = True,
    generation_model: str | None = None, embedding_model: str | None = None,
    request_timeout_seconds: int = 120, max_retries: int = 2,
)
ServiceConfigs(milvus: MilvusConfig | None = None, ollama: OllamaConfig | None = None)
ServiceSelection(service: Service, required: bool = False)
RuntimePlan(
    services: tuple[ServiceSelection | Service, ...],
    one_of: tuple[tuple[Service, ...], ...] = (),
    healthcheck: HealthcheckPolicy = HealthcheckPolicy(),
)
Service.parse(value: Service | str) -> Service
```

### Runtime plan / `ServiceBundle`

Canonical import: `rag_system_core.composition.docmesh_runtime`

```text
RAG_SERVICES = frozenset({"milvus", "ollama"})
build_docmesh_runtime_plan(
    *, services: set[str | Service] | None = None,
    required: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = (),
    check_on_startup: bool = False,
    parallel_healthchecks: bool = False,
) -> RuntimePlan
assemble_docmesh_services(*, plan: RuntimePlan, settings: ServiceConfigs) -> ServiceBundle
create_docmesh_service_client(
    service_name: str,
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
) -> object | None
```

`ServiceBundle`의 public fields와 methods:

```text
ServiceBundle(
    configs: ServiceConfigs,
    clients: dict[str, object],
    selected_services: frozenset[str],
    required_services: frozenset[str] = frozenset(),
)
get_client(service: Service | str) -> object
checks -> dict[str, Callable[[], None]]
close() -> None
```

`ServiceBundle`은 context manager가 아닙니다. `bundle.close()`를 사용합니다. `assemble_docmesh_services`는 explicit settings를 사용하며 환경변수를 읽지 않습니다.

### DMS assembly

Canonical imports: `rag_system_core.composition.create_dms_sdk_from_clients` 또는 `rag_system_core.composition.dms_runtime`

```text
create_dms_sdk_from_clients(
    *, engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
) -> dms.DefaultDocumentManagementSDK
```

DMS SDK는 dms-core의 `DocumentManagementSDKFactory(...).create()`로 조립됩니다. underlying Engine/MinIO client는 caller-owned이고 dms-core v0.9 SDK에는 `close()`가 없습니다.

### Health API

Canonical import: `rag_system_core.composition.health`

```text
ServiceHealthStatus(
    service_name: str, ok: bool,
    duration_seconds: float, error: str | None = None,
)
HealthCheckResult(ok: bool, services: list[ServiceHealthStatus])
run_health_checks(
    service_checks: Mapping[str, Callable[[], None]],
    required_services: set[str] | None = None,
    *, parallel: bool = False,
) -> HealthCheckResult
```

각 check 예외는 `ok=False` status로 변환됩니다. required service의 check가 없으면 실패 status가 추가됩니다. `to_dict()`는 result/status를 JSON-friendly dict로 변환합니다.

## 6. Built-in adapter API

### `FixedWindowChunker`

Canonical import: `rag_system_core.adapters.FixedWindowChunker`

```text
FixedWindowChunker(chunk_size: int, chunk_overlap: int)
chunk(text: str) -> list[str]
```

`chunk_size > 0`, `0 <= chunk_overlap < chunk_size`를 요구합니다. 입력 whitespace를 한 칸으로 정규화한 뒤 문자 수 기준 fixed window를 만듭니다.

### `OllamaEmbeddingClient`

Canonical import: `rag_system_core.OllamaEmbeddingClient`

```text
OllamaEmbeddingClient(*, client: Any, model: str)
embed(texts: list[str]) -> list[list[float]]
check() -> None
```

주입 client는 `embed(model=<model>, input=<texts>)`를 제공하고 응답에 `embeddings` key를 포함해야 합니다. 빈 model은 `ValueError`, transport/malformed response는 `RuntimeError`입니다. health check는 client의 `check()` 또는 `ps()`를 사용합니다.

### `OllamaGenerationClient`

Canonical import: `rag_system_core.OllamaGenerationClient`

```text
OllamaGenerationClient(*, client: Any, model: str)
generate(prompt: str) -> str
check() -> None
```

주입 client는 `chat(model=<model>, messages=[{"role": "user", "content": prompt}])`를 제공해야 하며 응답의 `message.content`를 반환합니다.

## 7. Storage API

### `MetadataStore`와 ORM models

Canonical import: `rag_system_core.storage`

```text
MetadataStore(engine: sqlalchemy.engine.Engine)
close() -> None
add_document(document: DocumentRecord) -> None
add_chunks(chunks: list[ChunkRecord]) -> None
delete_chunks(chunk_ids: list[str]) -> None
add_ingestion_progress(progress_rows: list[IngestionProgressRecord]) -> None
get_document_for_user(*, doc_id: str, user_id: str) -> DocumentRecord | None
list_documents(user_id: str) -> list[DocumentRecord]
list_document_chunks(*, doc_id: str, user_id: str) -> list[ChunkRecord]
list_ingestion_progress(
    *, doc_id: str, user_id: str, job_id: str | None = None
) -> list[IngestionProgressRecord]
delete_document(*, doc_id: str, user_id: str) -> DocumentRecord | None
check() -> None
```

`MetadataStore`는 injected Engine에 SQLAlchemy ORM으로 `documents`, `chunks`, `ingestion_progress`를 초기화합니다. `metadata_path`를 직접 받지 않습니다. `ChunkModel`, `DocumentModel`, `IngestionProgressModel`은 `rag_system_core.storage`의 ORM mapping export입니다.

### `MilvusLiteVectorStore`

Canonical import: `rag_system_core.storage.MilvusLiteVectorStore`

```text
MilvusLiteVectorStore(
    *, collection_name: str, timeout: float = 30.0, client: Any
)
add(chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]
search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
delete_document(doc_id: str) -> None
delete_chunks(chunk_ids: list[str]) -> None
check() -> None
```

첫 `add`에서 collection이 없으면 embedding dimension, COSINE metric, auto integer ID로 생성합니다. 검색에는 escaped `user_id` filter를 적용합니다. empty query/non-positive `top_k`/missing collection은 빈 결과가 될 수 있습니다.

### `DmsDocumentStorage`

Canonical import: `rag_system_core.storage.DmsDocumentStorage`

```text
DmsDocumentStorage(sdk: DocumentManagementSdk)
store_text(*, doc_id, user_id, text, source, idempotency_key) -> str
store_file_stream(*, doc_id, user_id, file_stream, size, source, idempotency_key) -> str
store_file_path(*, doc_id, user_id, file_path, source=None, idempotency_key) -> str
load(document: DocumentRecord) -> str | None
delete(document: DocumentRecord) -> None
```

`DocumentManagementSdk`는 `rag_system_core.storage.dms_document_storage`에 있는 `dms.DocumentManagementClient` compatibility alias입니다. DMS upload 결과의 `document_id`가 요청한 `doc_id`와 다르면 `RuntimeError`입니다. text upload는 idempotency request를 전달하지만 현재 file-stream/path adapter는 key를 DMS request에 전달하지 않습니다. missing/deleted asset load/delete는 idempotent하게 처리됩니다. 현재 `DmsDocumentStorage`는 `check()`를 제공하지 않습니다.

## 8. Advanced domain service API

Canonical import: `rag_system_core.domain.core`

일반 애플리케이션은 user-aware `RAGCore`를 사용합니다. 아래 서비스는 이미 해석된 `user_id`를 직접 받으며 인증·scope 보장은 호출자 책임입니다.

```text
IngestionService(
    *, chunker: Chunker, embedding_client: EmbeddingClient,
    vector_store: VectorStore, metadata_store: MetadataRepository,
    document_storage: DocumentAssetStorage,
)
ingest_text(*, user_id: str, text: str, source: str) -> IngestResult
ingest_file_stream(*, user_id: str, file_stream: BinaryIO, source: str) -> IngestResult
ingest_file_path(*, user_id: str, file_path: Path, source: str | None = None) -> IngestResult
preprocess(text: str) -> str
chunk(text: str) -> list[str]
embed(chunks: list[str]) -> list[list[float]]
store(chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None

RetrievalService(*, embedding_client: EmbeddingClient, vector_store: VectorStore)
search(*, user_id: str, question: str, top_k: int) -> list[ChunkRecord]
embed_query(question: str) -> list[float]
vector_search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]

GenerationService(generation_client: GenerationClient, system_prompt: str | None = None)
build_prompt(*, question: str, context_chunks: list[ChunkRecord]) -> str
call_llm(prompt: str) -> str
generate(*, question: str, context_chunks: list[ChunkRecord]) -> QueryResult
```

`GenerationService`의 기본 system prompt는 `You are a helpful RAG assistant. Answer only from the retrieved context.`입니다.

## 9. 전체 공개 export 추적표

아래 표는 generated artifact를 제외한 source tree의 모든 비어 있지 않은 `__all__` 선언을 API 절과 Examples/Configuration 페이지에 연결합니다. 같은 export가 여러 경로로 re-export되는 경우 canonical 구현과 compatibility path를 함께 표기합니다.

| 공개 import path | `__all__` export | API 절 | 예제/설정 |
|---|---|---|---|
| `rag_system_core` | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestionProgressRecord`, `IngestResult`, `OllamaEmbeddingClient`, `OllamaGenerationClient`, `QueryResult`, `RAGCore`, `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §2, §4, §5, §6 | [Examples](Examples) §1–§4 |
| `rag_system_core.types` | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestionProgressRecord`, `IngestResult`, `QueryResult` | §2, §3 | [Examples](Examples) §1–§2 |
| `rag_system_core.ports` | `Chunker`, `DocumentAssetStorage`, `EmbeddingClient`, `GenerationClient`, `HealthCheckRunner`, `MetadataRepository`, `VectorStore` | §3 | [Examples](Examples) §1, §3 |
| `rag_system_core.adapters` | `FixedWindowChunker` | §6 | [Examples](Examples) §7 |
| `rag_system_core.composition` | `assemble_docmesh_services`, `create_dms_sdk_from_clients`, `create_docmesh_service_client`, `run_health_checks`, `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §5 | [Examples](Examples) §3–§6; [Configuration](Configuration) |
| `rag_system_core.composition.configuration` | `ConfigError`, `HealthcheckPolicy`, `MilvusConfig`, `OllamaConfig`, `RuntimePlan`, `Service`, `ServiceConfigs`, `ServiceSelection` | §5 | [Examples](Examples) §5; [Configuration](Configuration) §2–§3 |
| `rag_system_core.composition.dms_runtime` | `create_dms_sdk_from_clients` | §5 | [Examples](Examples) §3–§4; [Configuration](Configuration) §6 |
| `rag_system_core.composition.docmesh_runtime` | `RAG_SERVICES`, `ServiceBundle`, `assemble_docmesh_services`, `build_docmesh_runtime_plan`, `create_docmesh_service_client` | §5 | [Examples](Examples) §5; [Configuration](Configuration) §5 |
| `rag_system_core.composition.health` | `HealthCheckResult`, `ServiceHealthStatus`, `run_health_checks` | §5 | [Examples](Examples) §6 |
| `rag_system_core.composition.rag_factories` | `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5 | [Examples](Examples) §5; [Configuration](Configuration) §4 |
| `rag_system_core.composition.factories` | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5 | [Examples](Examples) §3, §5 |
| `rag_system_core.composition.service_factory` | `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §5 | [Examples](Examples) §3 |
| `rag_system_core.domain.core` | `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `GenerationService`, `IngestionProgressRecord`, `IngestionService`, `IngestResult`, `QueryResult`, `RAGCore`, `RetrievalService`, `VectorStore` | §4, §8 | [Examples](Examples) §1, §8 |
| `rag_system_core.storage` | `ChunkModel`, `DmsDocumentStorage`, `DocumentModel`, `IngestionProgressModel`, `MetadataStore`, `MilvusLiteVectorStore` | §7 | [Examples](Examples) §7 |
| `rag_system_core.storage.dms_document_storage` | `DmsDocumentStorage`, `DocumentManagementSdk` | §7 | [Examples](Examples) §3, §7 |

`rag_system_core.domain.__init__`의 `__all__`은 비어 있으므로 public export 표에서 제외했습니다.

## 10. 구현·테스트·요구사항 추적표

각 row는 canonical implementation file, 주요 test file, PRD/SRS requirement ID, example/configuration section을 연결합니다. path는 repository root 기준입니다.

| API surface | 구현 source | 주요 테스트 | PRD / SRS | 예제/설정 |
|---|---|---|---|---|
| records, user, protocol compatibility | `rag_system_core/types.py`, `ports.py` | `test_rag_system_core/domain/test_architecture.py`, `test_ingestion_api.py`, `test_query.py` | PRD-FR-1–6; SRS-FR-001–011, SRS-NFR-006–007 | Examples §1–2 |
| `RAGCore` facade | `rag_system_core/domain/core.py` | `test_ingestion_api.py`, `test_query.py`, `test_metadata_and_progress.py`, `test_deletion_and_rollback.py` | PRD-FR-1–19; SRS-FR-001–023, 030–040, 045–071, 077–079 | Examples §1–2, §4 |
| domain advanced services | `rag_system_core/domain/ingestion.py`, `retrieval.py`, `generation.py` | `test_ingestion_api.py`, `test_query.py`, `test_deletion_and_rollback.py` | PRD-FR-4–12; SRS-FR-012–037, 053–063 | Examples §8 |
| `FixedWindowChunker` | `rag_system_core/adapters/chunking.py` | `test_core_configuration.py`, `test_metadata_and_progress.py` | PRD-FR-8; SRS-FR-016–019 | Examples §7 |
| Ollama adapters | `rag_system_core/adapters/ollama.py` | `test_ollama_embedding_client.py`, `test_ollama_generation_client.py`, `test_docmesh_integration.py` | PRD-FR-11–12, 18; SRS-FR-030–037, 064–069, 077 | Examples §7 |
| metadata store/models | `rag_system_core/storage/metadata_store.py` | `test_metadata_and_progress.py`, `test_deletion_and_rollback.py`, `test_object_creation.py` | PRD-FR-15–17; SRS-FR-045–063, SRS-DR-001–005, SRS-NFR-008–010 | Examples §1, §7; Configuration §7 |
| Milvus vector adapter | `rag_system_core/storage/vector_store.py` | `test_metadata_and_progress.py`, `test_deletion_and_rollback.py`, `test_object_creation.py` | PRD-FR-13–14, 17; SRS-FR-032, 038–044, 061–063, SRS-NFR-008–009 | Examples §5, §7 |
| DMS asset adapter | `rag_system_core/storage/dms_document_storage.py` | `test_dms_document_storage.py`, `test_ingestion_api.py`, `test_docmesh_integration.py` | PRD-FR-5, 17–19; SRS-FR-024–029, 078, SRS-DR-006–007 | Examples §3–4, §7 |
| configuration models | `rag_system_core/composition/configuration.py` | `test_core_configuration.py`, `test_docmesh_integration.py` | PRD-FR-19; SRS-FR-038–044, 070–071, SRS-NFR-013, 015–016 | Configuration §2–4 |
| runtime plan/bundle | `rag_system_core/composition/docmesh_runtime.py` | `test_docmesh_integration.py`, `test_core_configuration.py`, `test_module_boundaries.py` | PRD-FR-19; SRS-FR-038–044, 070–071, 075, SRS-NFR-013, 015–016 | Examples §5; Configuration §5 |
| RAG adapter factories | `rag_system_core/composition/rag_factories.py` | `test_core_configuration.py`, `test_docmesh_integration.py` | PRD-FR-19; SRS-FR-038–044, 070–071 | Examples §5; Configuration §4 |
| DMS client assembly / Factory | `rag_system_core/composition/dms_runtime.py`, `service_factory.py` | `test_docmesh_integration.py`, `test_core_configuration.py`, `test_object_creation.py` | PRD-FR-19; SRS-FR-075, 079, SRS-NFR-015–016 | Examples §3–4; Configuration §6–7 |
| health models/runner | `rag_system_core/composition/health.py` | `test_docmesh_integration.py`, `test_core_configuration.py` | PRD-FR-18; SRS-FR-064–069, 073 | Examples §6 |
| package/submodule export boundaries | `__init__.py` files listed in §9 | `test_module_boundaries.py`, `test_architecture.py` | PRD-FR-19; SRS-NFR-004–005, 011–013 | API §1, §9 |

`Partially verified` SRS requirements는 test coverage의 한계를 포함합니다. 이 표는 테스트가 없는 항목을 자동으로 `Verified`로 승격하지 않습니다.

## 11. 제한과 비목표

- HTTP 서버가 아닌 동기 Python library입니다.
- 환경변수만으로 완성된 `RAGCore` 자동 조립은 없습니다.
- 파일 입력은 UTF-8 text를 전제하며 PDF/OCR/parser는 제공하지 않습니다.
- `RAGCore`와 host-owned transport client는 주입 자원 lifecycle을 소유하지 않습니다.
- ingestion/deletion은 vector, metadata, DMS 사이의 distributed transaction이 아닙니다.
- dms-core v0.9 SDK에는 `close()`가 없으므로 Factory context가 DMS SDK를 닫지 않습니다.
- Factory가 `metadata_path`로 만든 `MetadataStore`만 Factory `close()`에서 정리됩니다.
