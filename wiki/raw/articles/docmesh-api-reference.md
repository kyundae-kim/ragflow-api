---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/API-Reference
ingested: 2026-08-10
sha256: c2fb2ba2acb242d2bf83131ddf6edfd72c7625846e27c1158e28c6697d662147
---
# 공개 API 레퍼런스

이 문서는 `rag-system-core`를 다른 애플리케이션·서비스에서 재사용하기 위한 **현재 구현 기준 공개 Python API 계약**입니다. 패키지 루트와 각 모듈의 `__all__`을 기준으로 공개 export를 추적하며, 문서에 없는 내부 함수·모듈은 호환성 계약으로 간주하지 않습니다.

- 구현 기준: `rag-system-core` `0.3.0` (`pyproject.toml`)
- Python: `>=3.11`
- DMS dependency: `dms-core` `v0.7.0` (`dms` package)
- 실행 예제: [Examples](Examples)
- 설정 레퍼런스: [Configuration](Configuration)

> 현재 버전은 환경변수만으로 완성된 `RAGCore`를 반환하는 단일 bootstrap helper를 제공하지 않습니다. 외부 설정과 collaborator를 명시적으로 조립해야 합니다.

## 1. 설치와 공개 import 규칙

```bash
uv sync
```

일반 애플리케이션은 패키지 루트 import를 우선합니다.

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

확장 조립은 명시된 서브패키지·고급 모듈 경로를 사용합니다.

```python
from rag_system_core.adapters import FixedWindowChunker
from rag_system_core.composition import (
    assemble_docmesh_services,
    create_dms_sdk_from_clients,
    create_docmesh_service_client,
    load_docmesh_settings,
    run_health_checks,
)
from rag_system_core.composition.configuration import (
    RuntimePlan,
    ServiceConfigs,
    load_available_service_configs,
    load_service_configs,
)
from rag_system_core.composition.dms_runtime import load_dms_settings
from rag_system_core.composition.docmesh_runtime import (
    ServiceBundle,
    build_docmesh_runtime_plan,
)
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)
from rag_system_core.ports import (
    Chunker,
    DocumentAssetStorage,
    HealthCheckRunner,
    MetadataRepository,
    VectorStore,
)
from rag_system_core.storage import (
    DmsDocumentStorage,
    MetadataStore,
    MilvusLiteVectorStore,
)
```

`rag_system_core.composition.factories`는 `create_rag_*` 함수와 두 Factory를 재-export하는 고급 compatibility path입니다. `rag_system_core.types`의 `EmbeddingClient`·`GenerationClient`는 호환성 re-export이고 canonical protocol 정의는 `rag_system_core.ports`에 있습니다.

## 2. 공개 결과 모델과 사용자 모델

### `AuthenticatedUser`

import path: `rag_system_core.AuthenticatedUser` 또는 `rag_system_core.types.AuthenticatedUser`

```text
AuthenticatedUser(
    sub: str,
    preferred_username: str | None,
    email: str | None,
    given_name: str | None,
    family_name: str | None,
    name: str | None,
    realm_roles: list[str],
    client_roles: dict[str, list[str]],
    claims: dict[str, Any],
)
```

모든 생성자 인자는 필수입니다. RAG user-scope 경계에서는 `sub`가 저장·검색에 쓰이는 `user_id`가 됩니다. 인증, token 검증, 사용자 객체 생성은 호출 애플리케이션의 책임입니다.

### Dataclass 모델

| 타입 | Canonical import | 필드 |
|---|---|---|
| `DocumentRecord` | `rag_system_core.types` | `doc_id: str`, `user_id: str`, `source: str`, `created_at: str`, `asset_reference: str | None = None` |
| `ChunkRecord` | `rag_system_core.types` | `chunk_id: str`, `doc_id: str`, `user_id: str`, `content: str`, `metadata: dict[str, str] = {}` |
| `IngestResult` | `rag_system_core.types` | `job_id`, `doc_id`, `user_id`, `source`, `created_at`, `chunk_count` |
| `IngestionProgressRecord` | `rag_system_core.types` | `progress_id`, `job_id`, `doc_id`, `user_id`, `source`, `step_name`, `step_order`, `status`, `created_at` |
| `QueryResult` | `rag_system_core.types` | `answer: str`, `prompt: str`, `context_chunks: list[ChunkRecord]` |

`IngestionProgressRecord.status`는 현재 `running`, `completed`, `failed` 단계 기록에 사용됩니다. 현재 pipeline step 순서는 `load`, `preprocess`, `chunking`, `embedding`, `vector_store`, `chunk_persistence`입니다.

## 3. Port protocol 계약

Canonical import path: `rag_system_core.ports`

### `EmbeddingClient`

```text
embed(texts: list[str]) -> list[list[float]]
```

입력 text 순서에 대응하는 embedding 목록을 반환해야 합니다. `RAGCore` ingestion은 여러 chunk를 한 번에 전달합니다.

### `GenerationClient`

```text
generate(prompt: str) -> str
```

생성된 답변을 문자열로 반환해야 합니다.

### `Chunker`

```text
chunk(text: str) -> list[str]
```

입력 text를 하나 이상의 chunk로 나눕니다. 빈 결과는 ingestion에서 `ValueError`로 처리됩니다.

### `VectorStore`

```text
add(chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]
search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
delete_document(doc_id: str) -> None
delete_chunks(chunk_ids: list[str]) -> None
```

`add`는 입력 chunk와 같은 수의 opaque chunk ID를 반환해야 합니다. 검색은 `user_id` scope를 적용해야 합니다.

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

사용자 범위를 받는 조회·삭제 메서드는 반드시 `user_id`를 적용해야 합니다.

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

저장 메서드는 opaque asset reference를 반환해야 합니다. stream은 호출자가 소유하며 adapter가 임의로 닫아서는 안 됩니다.

### `HealthCheckRunner`

```text
__call__(
    service_checks: dict[str, Callable[[], None]],
    required_services: set[str] | None = None,
) -> object
```

`RAGCore.health_check()`가 metadata와 선택 dependency check를 전달하는 callable입니다. 기본 구현은 `run_health_checks`입니다.

## 4. `RAGCore`

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

모든 의존성이 필수인 dependency-injection 생성자입니다. `RAGCore`는 주입된 client·store의 lifecycle을 소유하지 않으며 공통 `close()`를 제공하지 않습니다.

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
- 입력 파일/stream은 UTF-8 text로 decode합니다.
- `ingest_file_stream`에서 `source`가 없거나 공백이면 `ValueError`입니다.
- `ingest_file_path`의 source 기본값은 파일명입니다.
- `ingest_text`는 text를 `strip()`한 뒤 asset을 저장합니다.
- embedding은 chunk 전체를 batch로 요청합니다.
- text upload는 `job_id`를 DMS idempotency key로 전달합니다. 현재 file-stream/path upload adapter는 method 인자로 받은 idempotency key를 DMS request에 전달하지 않습니다.
- vector ID 수 불일치 또는 chunk metadata 저장 실패 시 생성된 vector 삭제를 시도합니다. 전체 ingestion을 distributed transaction처럼 rollback하지는 않습니다.

### Retrieval / generation

```text
query(*, user: AuthenticatedUser, question: str, top_k: int = 3) -> QueryResult
```

질문을 embedding하고 user scope로 vector 검색한 뒤 generation client를 호출합니다. 기본 prompt는 `[System Prompt]`, `[Retrieved Context]`, `[User Query]` 구역을 포함합니다. 반환되는 `QueryResult.prompt`는 실제 generation client에 전달된 prompt입니다.

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

다른 사용자의 문서는 조회되지 않으며 삭제 대상이 아니면 `False`입니다. 삭제 순서는 vector → document asset soft delete → RAG metadata/청크/progress입니다. 중간 실패 시 이미 삭제된 artifact가 있을 수 있으며 distributed rollback은 제공하지 않습니다.

### Health

```text
health_check() -> HealthCheckResult | object
```

항상 metadata check를 포함하고 `check()`를 가진 vector, embedding, generation, document-storage adapter를 추가합니다. 기본 runner를 사용할 경우 반환 모델은 `HealthCheckResult`입니다.

## 5. Composition API

### `RAGServiceFactory`

Canonical import: `rag_system_core.composition.RAGServiceFactory` 또는 `rag_system_core.composition.service_factory.RAGServiceFactory`

```text
create_embedding_client() -> EmbeddingClient
create_generation_client() -> GenerationClient
create_vector_store() -> VectorStore
create_document_storage() -> DocumentAssetStorage
create_metadata_store(*, metadata_path: str | Path | None = None) -> MetadataRepository
create_chunker(*, chunk_size: int, chunk_overlap: int) -> Chunker
```

구조적 typing protocol입니다. `RAGCore`가 요구하는 `health_check_runner`는 Factory protocol이 직접 생성하지 않으며 caller가 `RAGCore`에 전달합니다.

### `DocmeshRAGServiceFactory`

Canonical import: `rag_system_core.DocmeshRAGServiceFactory`

직접 생성자:

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

주요 classmethod:

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

- `from_clients`는 host-owned DMS SQLAlchemy Engine·MinIO client와 이미 만들어진 RAG collaborator를 받아 DMS SDK를 생성합니다.
- `from_host_clients`는 Ollama/Milvus raw client로 RAG adapter를 만들고 `from_clients`에 위임합니다.
- `from_clients`의 `metadata_engine`은 optional signature지만 `create_rag_core()`의 정상 조립 경로에는 필요합니다. 없으면 `create_metadata_store(metadata_path=...)`를 별도로 호출할 수 있습니다.
- 두 classmethod가 생성한 DMS SDK는 Factory가 소유합니다. 주입된 Engine, MinIO, Ollama, Milvus client는 caller-owned입니다.

Factory method:

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
__enter__() / __exit__()
```

`metadata_engine`이 주입되면 `MetadataStore`는 그 Engine에 바인딩됩니다. 주입되지 않고 `metadata_path`를 지정하면 Factory가 SQLite Engine과 MetadataStore를 만들고 close 시 정리합니다.

### RAG adapter factory functions

Canonical import: `rag_system_core.composition.rag_factories` 또는 compatibility path `rag_system_core.composition.factories`

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

- `settings`가 없고 필요한 값도 없으면 RAG 환경을 읽습니다.
- `bundle`이 있으면 bundle의 config/client를 사용합니다.
- vector collection 기본값은 `rag_chunks`, timeout 기본값은 `30.0`입니다.
- explicit client는 client 생성을 대체하지만 collection/timeout 설정 해석은 별도입니다.

### Runtime plan / ServiceBundle

Canonical import: `rag_system_core.composition.docmesh_runtime`

```text
RAG_SERVICES = frozenset({"milvus", "ollama"})

build_docmesh_runtime_plan(
    *,
    services: set[str | Service] | None = None,
    required: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = (),
    check_on_startup: bool = False,
    parallel_healthchecks: bool = False,
) -> RuntimePlan

assemble_docmesh_services(*, plan: RuntimePlan) -> ServiceBundle

ServiceBundle(
    configs: ServiceConfigs,
    clients: dict[str, object],
    selected_services: frozenset[str],
    required_services: frozenset[str] = frozenset(),
)
```

`ServiceBundle.get_client(service)`로 선택된 `ollama`·`milvus` client를 얻습니다. `checks` property는 client의 `check()`, Ollama `ps()`, Milvus `list_collections()`를 health callable로 수집합니다. `assemble_docmesh_services`가 만든 bundle은 client lifecycle을 소유하므로 `with bundle:` 또는 `bundle.close()`를 사용합니다.

### Settings loading / client creation

Canonical import: `rag_system_core.composition.docmesh_runtime` 및 `rag_system_core.composition.configuration`

```text
load_docmesh_settings(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs

create_docmesh_service_client(
    service_name: str,
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
) -> object | None

load_service_configs(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs

load_available_service_configs(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs
```

`load_docmesh_settings`는 선택된 `milvus`·`ollama` 환경 설정만 로드합니다. 설정이 없는 service는 `load_available_service_configs` 경로에서 생략될 수 있습니다. `create_docmesh_service_client`는 지원되지 않는 service명에 `ValueError`, 설정되지 않은 service에 `None`을 반환합니다.

### DMS client assembly

Canonical import: `rag_system_core.composition.dms_runtime`

```text
load_dms_settings(
    env: Mapping[str, str] | None = None,
) -> dms.DmsServiceConfigs

create_dms_sdk_from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
    plan: dms.DmsAssemblyPlan | None = None,
) -> dms.DefaultDocumentManagementSDK

DmsEnvironmentDiagnosis(
    selected_backend: str | None = None,
    missing_required_keys: tuple[str, ...] = (),
    unsupported_keys: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
)
```

`load_dms_settings`는 현재 process environment를 기본으로 읽으며 `DMS_` namespace를 사용합니다. `DMS_METADATA_BACKEND`, `DMS_SQLITE_PATH`, `DMS_POSTGRES_*`, `DMS_MINIO_*`, `DMS_CONFIGURATION_STRICT`를 사용합니다. strict mode에서 SQLite/PostgreSQL 단서가 동시에 있으면 설정 오류입니다. `env`를 직접 전달하는 것은 진단·테스트용 공개 인자이며 global environment를 변경하지 않습니다.

### Health API

Canonical import: `rag_system_core.composition.health`

```text
run_health_checks(
    service_checks: Mapping[str, Callable[[], None]],
    required_services: set[str] | None = None,
    *, parallel: bool = False,
) -> HealthCheckResult

ServiceHealthStatus(
    service_name: str,
    ok: bool,
    duration_seconds: float,
    error: str | None = None,
)

HealthCheckResult(
    ok: bool,
    services: list[ServiceHealthStatus],
)
```

각 check 예외는 `ok=False` status로 변환됩니다. 설정된 check가 없는 required service도 실패 status가 됩니다. `to_dict()`는 status/result를 JSON-friendly dictionary로 변환합니다. `ok`는 required service들의 상태와 missing required check를 기준으로 계산됩니다.

## 6. Built-in adapter API

### `FixedWindowChunker`

Import: `rag_system_core.adapters.FixedWindowChunker`

```text
FixedWindowChunker(chunk_size: int, chunk_overlap: int)
chunk(text: str) -> list[str]
```

`chunk_size > 0`, `0 <= chunk_overlap < chunk_size`를 요구합니다. 입력 whitespace를 한 칸으로 정규화한 뒤 문자 수 기준 fixed window를 만들고, 빈 입력에는 `[]`를 반환합니다.

### `OllamaEmbeddingClient`

Import: `rag_system_core.OllamaEmbeddingClient`

```text
OllamaEmbeddingClient(*, client: Any, model: str)
embed(texts: list[str]) -> list[list[float]]
check() -> None
```

주입 client는 `embed(model=<model>, input=<texts>)`를 제공해야 하고 응답에 `embeddings` key가 있어야 합니다. 빈 text 목록은 `[]`입니다. 빈 model은 `ValueError`, transport/malformed response는 원인을 연결한 `RuntimeError`입니다. health는 client의 `check()` 또는 `ps()`를 호출합니다.

### `OllamaGenerationClient`

Import: `rag_system_core.OllamaGenerationClient`

```text
OllamaGenerationClient(*, client: Any, model: str)
generate(prompt: str) -> str
check() -> None
```

주입 client는 `chat(model=<model>, messages=[{"role": "user", "content": prompt}])`를 제공해야 합니다. 응답의 `message.content`를 문자열로 반환합니다. 빈 model은 `ValueError`, transport/malformed response는 `RuntimeError`입니다.

## 7. Storage API

### `MetadataStore`

Import: `rag_system_core.storage.MetadataStore`

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

생성자는 SQLAlchemy `Engine`에 binding하며 `documents`, `chunks`, `ingestion_progress` schema를 초기화합니다. `metadata_path`를 직접 받지 않습니다. `close()`는 주입된 Engine에 `dispose()`를 호출하므로, host-owned Engine을 다른 곳에서도 사용하는 경우에는 Factory의 `metadata_engine` 경로처럼 호출자 lifecycle 정책에 맞춰 사용해야 합니다.

`rag_system_core.storage`는 `DocumentModel`, `ChunkModel`, `IngestionProgressModel`도 export합니다. 각각 `documents`, `chunks`, `ingestion_progress` table mapping입니다. ORM을 직접 조작하면 vector/DMS lifecycle을 우회할 수 있습니다.

### `MilvusLiteVectorStore`

Import: `rag_system_core.storage.MilvusLiteVectorStore`

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

첫 `add`에서 collection이 없으면 embedding dimension, COSINE metric, auto integer ID로 생성합니다. 검색에는 escaped `user_id` filter를 사용합니다. empty chunks, non-positive `top_k`, missing collection은 빈 결과/무동작으로 처리되는 경로가 있습니다.

### `DmsDocumentStorage`

Import: `rag_system_core.storage.DmsDocumentStorage`

```text
DmsDocumentStorage(sdk: DocumentManagementSdk)
store_text(*, doc_id, user_id, text, source, idempotency_key) -> str
store_file_stream(*, doc_id, user_id, file_stream, size, source, idempotency_key) -> str
store_file_path(*, doc_id, user_id, file_path, source=None, idempotency_key) -> str
load(document: DocumentRecord) -> str | None
delete(document: DocumentRecord) -> None
check() -> None
```

`DocumentManagementSdk`는 `dms.DocumentManagementClient`의 compatibility alias입니다. concrete SDK는 text/stream/path upload, content read, soft delete, health check를 제공해야 합니다. 업로드된 DMS `document_id`가 요청한 `doc_id`와 다르면 `RuntimeError`입니다. text upload는 idempotency request를 전달하지만 file-stream/path 호출은 현재 adapter에서 idempotency key를 전달하지 않습니다. missing/deleted asset load/delete는 idempotent하게 처리됩니다.

## 8. Advanced domain service API

일반 애플리케이션은 user-aware `RAGCore`를 사용합니다. 아래 타입은 `rag_system_core.domain.core`의 명시적 `__all__` export이며 이미 해석된 `user_id`를 직접 받습니다.

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

GenerationService(
    generation_client: GenerationClient,
    system_prompt: str | None = None,
)
build_prompt(*, question: str, context_chunks: list[ChunkRecord]) -> str
call_llm(prompt: str) -> str
generate(*, question: str, context_chunks: list[ChunkRecord]) -> QueryResult
```

`GenerationService`의 기본 system prompt는 `You are a helpful RAG assistant. Answer only from the retrieved context.`입니다. 이 advanced service들은 인증·user-scope를 직접 수행하지 않습니다.

## 9. 전체 공개 export 추적표

아래 표는 `build/` 생성 산출물을 제외한 저장소 source tree의 **모든 비어 있지 않은 `__all__` 선언**을 API 절과 Examples/Configuration 페이지에 연결합니다. 같은 export가 여러 경로로 re-export되는 경우 각 경로를 별도 표기합니다.

| 공개 import path | `__all__` export | API 절 | 예제/설정 |
|---|---|---|---|
| `rag_system_core` | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestionProgressRecord`, `IngestResult`, `OllamaEmbeddingClient`, `OllamaGenerationClient`, `QueryResult`, `RAGCore`, `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §2, §3, §4, §5, §6 | [Examples](Examples) §1, §2, §3, §5 |
| `rag_system_core.types` | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestionProgressRecord`, `IngestResult`, `QueryResult` | §2, §3 | [Examples](Examples) §1, §4 |
| `rag_system_core.ports` | `Chunker`, `DocumentAssetStorage`, `EmbeddingClient`, `GenerationClient`, `HealthCheckRunner`, `MetadataRepository`, `VectorStore` | §3 | [Examples](Examples) §4 |
| `rag_system_core.adapters` | `FixedWindowChunker` | §6 | [Examples](Examples) §4 |
| `rag_system_core.composition` | `assemble_docmesh_services`, `create_dms_sdk_from_clients`, `create_docmesh_service_client`, `load_docmesh_settings`, `run_health_checks`, `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §5 | [Examples](Examples) §5, §6; [Configuration](Configuration) |
| `rag_system_core.composition.configuration` | `CommonConfig`, `ConfigError`, `ConfigIssue`, `HealthcheckPolicy`, `MilvusConfig`, `OllamaConfig`, `RuntimePlan`, `Service`, `ServiceConfigs`, `ServiceSelection`, `load_available_service_configs`, `load_service_configs` | §5 | [Examples](Examples) §6; [Configuration](Configuration) |
| `rag_system_core.composition.dms_runtime` | `DmsEnvironmentDiagnosis`, `create_dms_sdk_from_clients`, `load_dms_settings` | §5 | [Examples](Examples) §6; [Configuration](Configuration) |
| `rag_system_core.composition.docmesh_runtime` | `RAG_SERVICES`, `ServiceBundle`, `assemble_docmesh_services`, `build_docmesh_runtime_plan`, `create_docmesh_service_client`, `load_docmesh_settings` | §5 | [Examples](Examples) §5, §6; [Configuration](Configuration) |
| `rag_system_core.composition.health` | `HealthCheckResult`, `ServiceHealthStatus`, `run_health_checks` | §5 | [Examples](Examples) §6 |
| `rag_system_core.composition.rag_factories` | `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5 | [Examples](Examples) §5, §6; [Configuration](Configuration) |
| `rag_system_core.composition.factories` | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5 | [Examples](Examples) §4, §5 |
| `rag_system_core.composition.service_factory` | `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §5 | [Examples](Examples) §4 |
| `rag_system_core.domain.core` | `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `GenerationService`, `IngestionProgressRecord`, `IngestionService`, `IngestResult`, `QueryResult`, `RAGCore`, `RetrievalService`, `VectorStore` | §8 | [Examples](Examples) §7 |
| `rag_system_core.storage` | `ChunkModel`, `DmsDocumentStorage`, `DocumentModel`, `IngestionProgressModel`, `MetadataStore`, `MilvusLiteVectorStore` | §7 | [Examples](Examples) §4, §5 |
| `rag_system_core.storage.dms_document_storage` | `DmsDocumentStorage`, `DocumentManagementSdk` | §7 | [Examples](Examples) §5 |

## 10. 구현·테스트·요구사항 추적표

각 export row는 아래 canonical implementation file에 정의되거나 re-export됩니다. Wiki의 source/test path는 repository root 기준이며, requirement ID는 `docs/prd.md`와 `docs/srs.md` 기준입니다. 같은 API를 여러 모듈이 re-export하는 경우 canonical 구현 row를 공유합니다.

| API surface | 구현 source | 주요 테스트 | PRD / SRS |
|---|---|---|---|
| `AuthenticatedUser`, records, `EmbeddingClient`, `GenerationClient` | `rag_system_core/types.py`, `rag_system_core/ports.py` | `test_rag_system_core/domain/test_architecture.py`, `test_rag_system_core/domain/test_ingestion_api.py`, `test_rag_system_core/domain/test_query.py` | `PRD-FR-1`–`PRD-FR-5`; `SRS-FR-001`–`011`, `SRS-NFR-006`–`007` |
| `RAGCore` facade | `rag_system_core/domain/core.py` | `test_rag_system_core/domain/test_ingestion_api.py`, `test_rag_system_core/domain/test_query.py`, `test_rag_system_core/domain/test_metadata_and_progress.py`, `test_rag_system_core/domain/test_deletion_and_rollback.py` | `PRD-FR-1`–`PRD-FR-5`, `PRD-FR-10`; `SRS-FR-001`–`023`, `SRS-FR-045`–`063`, `SRS-FR-064`–`069` |
| `IngestionService`, `RetrievalService`, `GenerationService` | `rag_system_core/domain/ingestion.py`, `rag_system_core/domain/retrieval.py`, `rag_system_core/domain/generation.py` | `test_rag_system_core/domain/test_ingestion_api.py`, `test_rag_system_core/domain/test_query.py`, `test_rag_system_core/domain/test_deletion_and_rollback.py` | `PRD-FR-1`–`PRD-FR-5`; `SRS-FR-001`–`037`, `SRS-FR-053`–`063` |
| `FixedWindowChunker` | `rag_system_core/adapters/chunking.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/domain/test_deletion_and_rollback.py`, `test_rag_system_core/domain/test_metadata_and_progress.py` | `PRD-FR-3`; `SRS-FR-012`–`023`, `SRS-FR-030`–`037` |
| `OllamaEmbeddingClient`, `OllamaGenerationClient` | `rag_system_core/adapters/ollama.py` | `test_rag_system_core/adapters/test_ollama_embedding_client.py`, `test_rag_system_core/adapters/test_ollama_generation_client.py`, `test_rag_system_core/composition/test_docmesh_integration.py` | `PRD-FR-4`–`PRD-FR-5`; `SRS-FR-030`–`037`, `SRS-FR-064`–`069` |
| `MetadataStore`, ORM models | `rag_system_core/storage/metadata_store.py` | `test_rag_system_core/domain/test_metadata_and_progress.py`, `test_rag_system_core/domain/test_deletion_and_rollback.py`, `test_rag_system_core/integration/test_object_creation.py` | `PRD-FR-6`, `PRD-FR-10`; `SRS-FR-045`–`063`, `SRS-DR-001`–`005`, `SRS-NFR-008`–`009` |
| `MilvusLiteVectorStore` | `rag_system_core/storage/vector_store.py` | `test_rag_system_core/domain/test_metadata_and_progress.py`, `test_rag_system_core/domain/test_deletion_and_rollback.py`, `test_rag_system_core/integration/test_object_creation.py` | `PRD-FR-5`, `PRD-FR-10`; `SRS-FR-030`–`037`, `SRS-FR-053`–`063`, `SRS-NFR-008`–`009` |
| `DmsDocumentStorage`, `DocumentManagementSdk` | `rag_system_core/storage/dms_document_storage.py` | `test_rag_system_core/storage/test_dms_document_storage.py`, `test_rag_system_core/domain/test_ingestion_api.py`, `test_rag_system_core/composition/test_docmesh_integration.py` | `PRD-FR-10`; `SRS-FR-024`–`029`, `SRS-FR-078`, `SRS-DR-006`–`007` |
| `ServiceConfigs`, config models, `Service`, loader functions | `rag_system_core/composition/configuration.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py` | `PRD-FR-7`, `PRD-FR-19`; `SRS-FR-038`–`044`, `SRS-FR-070`, `SRS-FR-079`, `SRS-NFR-013`, `SRS-NFR-015`–`016` |
| `RuntimePlan`, `ServiceBundle`, runtime loader/assembly | `rag_system_core/composition/docmesh_runtime.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py`, `test_rag_system_core/composition/test_module_boundaries.py` | `PRD-FR-7`–`PRD-FR-9`, `PRD-FR-19`; `SRS-FR-038`–`044`, `SRS-FR-070`–`071`, `SRS-FR-075`, `SRS-NFR-013`, `SRS-NFR-015`–`016` |
| `DocmeshRAGServiceFactory`, `RAGServiceFactory` | `rag_system_core/composition/service_factory.py`, `rag_system_core/composition/factories.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py`, `test_rag_system_core/composition/test_module_boundaries.py`, `test_rag_system_core/integration/test_object_creation.py` | `PRD-FR-6`–`PRD-FR-9`, `PRD-FR-18`–`PRD-FR-19`; `SRS-FR-070`–`071`, `SRS-FR-075`, `SRS-FR-079`, `SRS-NFR-015`–`016` |
| RAG adapter factory helpers | `rag_system_core/composition/rag_factories.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py` | `PRD-FR-7`–`PRD-FR-9`; `SRS-FR-038`–`044`, `SRS-FR-070`–`071` |
| DMS environment API | `rag_system_core/composition/dms_runtime.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py`, `test_rag_system_core/storage/test_dms_document_storage.py` | `PRD-FR-10`, `PRD-FR-19`; `SRS-FR-078`–`079`, `SRS-DR-006`–`007`, `SRS-NFR-015`–`016` |
| Health models and `run_health_checks` | `rag_system_core/composition/health.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_rag_system_core/composition/test_docmesh_integration.py`, `test_rag_system_core/storage/test_dms_document_storage.py` | `PRD-FR-8`; `SRS-FR-064`–`069`, `SRS-FR-077` |
| Package/submodule exports | `rag_system_core/__init__.py`, `rag_system_core/composition/__init__.py`, `rag_system_core/storage/__init__.py`, `rag_system_core/adapters/__init__.py` | `test_rag_system_core/composition/test_module_boundaries.py`, `test_rag_system_core/domain/test_architecture.py` | `PRD-FR-6`–`PRD-FR-9`; `SRS-FR-070`–`071`, `SRS-NFR-004`–`005`, `SRS-NFR-011`–`012` |

추적표의 `Partially verified` 요구사항은 SRS의 test traceability와 동일하게 해석합니다. 이 Wiki는 구현·테스트·요구사항 사이의 위치를 연결하지만, 테스트가 없는 항목을 자동으로 `Verified`로 승격하지 않습니다.

## 11. 현재 제한과 비목표

- HTTP 서버가 아닌 동기 Python library입니다.
- 환경변수만으로 완성된 `RAGCore`를 자동 조립하는 public bootstrap은 없습니다.
- 파일 입력은 UTF-8 text를 전제하며 PDF/OCR/parser는 제공하지 않습니다.
- `RAGCore`와 host-owned transport client는 주입 자원 lifecycle을 소유하지 않습니다.
- ingestion/deletion은 vector, metadata, DMS 사이의 distributed transaction이 아닙니다.
- `DocmeshRAGServiceFactory` classmethod가 생성한 DMS SDK만 Factory context가 소유합니다.
- 이전 버전에만 존재하는 API·설정 별칭은 현재 계약이 아닙니다.
