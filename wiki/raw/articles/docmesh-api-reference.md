---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/API-Reference
ingested: 2026-08-26
sha256: 22e669aa6653a965f2d5aaa0c9405929c9d82f8c9652d6691936e2ebeed9598c
---
# 공개 API 레퍼런스

> **문서 기준 (version-identifiable)**
>
> | 항목 | 값 |
> |---|---|
> | package | `rag-system-core` |
> | package version | `0.5.0` (`pyproject.toml`) |
> | 구현 기준 source revision | `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3` |
> | 관찰된 source branch | `dms-core-v0.10.0` |
> | Python | `>=3.11` |
> | runtime dependencies | `dms-core>=0.10.0`, `ollama>=0.6.2`, `pydantic-settings>=2.14.1`, `pymilvus[milvus-lite]>=3.0.1` |
> | export 기준 | 위 revision의 source tree에 있는 비어 있지 않은 literal `__all__` |
>
> 이 페이지는 `v0.5.0` package metadata와 위 source revision을 함께 식별하는 API 계약입니다. 현재 저장소에는 `v0.5.0` Git tag가 없으므로, 재현 시에는 package version과 전체 commit hash를 함께 확인하십시오. PRD/SRS는 요구사항 근거로 연결되지만 현재 문서 자체의 API version을 결정하지 않습니다.

## 목적과 공개 범위

이 문서는 `rag-system-core`를 다른 애플리케이션·서비스에서 재사용하기 위한 **현재 구현 기준 공개 Python API 계약**입니다. 독자는 이 문서만으로 다음을 확인할 수 있어야 합니다.

- 안정적으로 사용해야 하는 import path
- package root, public subpackage, advanced module의 구분
- 생성자와 public method의 signature·기본값·반환값
- 주입해야 하는 collaborator의 동작 계약
- 설정·lifecycle 소유권과 실패 동작
- 구현·테스트·PRD/SRS·예제 사이의 추적 경로

문서에 없는 내부 함수·모듈·이름은 호환성 계약으로 간주하지 마십시오. `__all__`에 없는 내부 helper는 공개 API가 아닙니다.

- 실행 예제: [Examples](Examples)
- 명시적 설정과 lifecycle: [Configuration](Configuration)

## 1. Public import 규칙과 안정성 계층

### 1.1 일반 애플리케이션용 package root

일반 애플리케이션은 다음 package-root facade를 우선 사용하십시오.

```python
from rag_system_core import (
    AuthenticatedUser,
    ChunkRecord,
    DocmeshRAGServiceFactory,
    DocumentRecord,
    EmbeddingClient,
    GenerationClient,
    IngestResult,
    IngestionProgressRecord,
    OllamaEmbeddingClient,
    OllamaGenerationClient,
    QueryResult,
    RAGCore,
    RAGServiceFactory,
)
```

package root의 `__all__`은 위 13개 이름입니다. `EmbeddingClient`와 `GenerationClient`의 canonical owner는 `rag_system_core.ports`이며 root와 `rag_system_core.types`는 호환 re-export입니다.

### 1.2 Public subpackage와 advanced module

아래 모듈은 source tree에서 literal `__all__`을 선언한 공개 모듈입니다. 일반 애플리케이션은 root facade를 사용하고, 아래 경로는 extension/composition/storage를 직접 조정할 때만 사용하십시오.

| import path | 안정성 | 공개 export |
|---|---|---|
| `rag_system_core.adapters` | public subpackage | `FixedWindowChunker` |
| `rag_system_core.ports` | canonical protocol module | `Chunker`, `DocumentAssetStorage`, `EmbeddingClient`, `GenerationClient`, `MetadataRepository`, `VectorStore` |
| `rag_system_core.types` | canonical record module + protocol compatibility | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestResult`, `IngestionProgressRecord`, `QueryResult` |
| `rag_system_core.composition` | public composition facade | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `assemble_docmesh_services`, `create_dms_sdk_from_clients`, `create_docmesh_service_client` |
| `rag_system_core.composition.configuration` | explicit configuration models | `ConfigError`, `MilvusConfig`, `OllamaConfig`, `RuntimePlan`, `Service`, `ServiceConfigs`, `ServiceSelection` |
| `rag_system_core.composition.docmesh_runtime` | advanced runtime assembly | `RAG_SERVICES`, `ServiceBundle`, `assemble_docmesh_services`, `build_docmesh_runtime_plan`, `create_docmesh_service_client` |
| `rag_system_core.composition.dms_runtime` | advanced DMS assembly | `create_dms_sdk_from_clients` |
| `rag_system_core.composition.rag_factories` | canonical RAG adapter factory module | `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` |
| `rag_system_core.composition.factories` | compatibility re-export module | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` |
| `rag_system_core.composition.service_factory` | Factory implementation advanced path | `DocmeshRAGServiceFactory`, `RAGServiceFactory` |
| `rag_system_core.domain.core` | user-id direct advanced domain path | records/protocol compatibility와 `GenerationService`, `IngestionService`, `RAGCore`, `RetrievalService`, `VectorStore` |
| `rag_system_core.storage` | storage implementations/models | `ChunkModel`, `DmsDocumentStorage`, `DocumentModel`, `IngestionProgressModel`, `MetadataStore`, `MilvusLiteVectorStore` |
| `rag_system_core.storage.dms_document_storage` | DMS adapter advanced path | `DmsDocumentStorage`, `DocumentManagementSdk` |

`rag_system_core.domain.__init__`의 `__all__`은 비어 있으므로 package-level domain export는 없습니다. `rag_system_core.domain.core`처럼 명시된 module-qualified path를 사용하십시오.

### 1.3 Versioning rule

- 이 Wiki의 canonical page 이름은 안정적으로 유지하고, 각 페이지의 **문서 기준** block을 갱신합니다.
- API surface는 source revision의 `__all__`과 실제 signature를 기준으로 합니다.
- package version만으로는 source를 재현할 수 없으므로 package version과 전체 commit hash를 함께 기록합니다.
- 내부 module import나 문서에 없는 re-export를 임의로 public API로 승격하지 않습니다.

## 2. Public records와 user model

canonical import는 `rag_system_core.types`이며, 아래 record는 package root에서도 re-export됩니다.

### `AuthenticatedUser`

```text
AuthenticatedUser(sub: str) -> None
```

- `sub`는 persistence와 retrieval filter에 사용되는 resolved `user_id`입니다.
- 인증, token 검증, 사용자 객체 생성은 호출 애플리케이션의 책임입니다.

### Dataclass records

| type | constructor | fields |
|---|---|---|
| `DocumentRecord` | `DocumentRecord(doc_id, user_id, source, created_at, asset_reference=None)` | `doc_id: str`, `user_id: str`, `source: str`, `created_at: str`, `asset_reference: str \| None` |
| `ChunkRecord` | `ChunkRecord(chunk_id, doc_id, user_id, content, metadata={})` | `chunk_id: str`, `doc_id: str`, `user_id: str`, `content: str`, `metadata: dict[str, str]` |
| `IngestResult` | `IngestResult(job_id, doc_id, user_id, source, created_at, chunk_count)` | `job_id: str`, `doc_id: str`, `user_id: str`, `source: str`, `created_at: str`, `chunk_count: int` |
| `IngestionProgressRecord` | `IngestionProgressRecord(progress_id, job_id, doc_id, user_id, source, step_name, step_order, status, created_at)` | `progress_id: str`, `job_id: str`, `doc_id: str`, `user_id: str`, `source: str`, `step_name: str`, `step_order: int`, `status: str`, `created_at: str` |
| `QueryResult` | `QueryResult(answer, prompt, context_chunks)` | `answer: str`, `prompt: str`, `context_chunks: list[ChunkRecord]` |

`ChunkRecord.metadata`의 기본값은 새 `dict` factory입니다. ingestion progress의 tracked pipeline 순서는 다음과 같습니다.

```text
load -> preprocess -> chunking -> embedding -> vector_store -> chunk_persistence
```

기록에 사용하는 상태는 `running`, `completed`, `failed`이며, `RAGCore.get_ingestion_step_statuses()`가 아직 기록되지 않은 정의된 단계에 `not_started`를 계산해 반환합니다.

## 3. Port protocol 계약

canonical import는 `rag_system_core.ports`입니다. protocol은 구조적 typing 계약이며, 구현체는 아래 동작을 만족해야 합니다.

### `EmbeddingClient`

```text
embed(texts: list[str]) -> list[list[float]]
```

입력 순서에 대응하는 embedding 목록을 반환해야 합니다. ingestion은 생성된 전체 chunk를 한 번의 batch 호출로 전달합니다.

### `GenerationClient`

```text
generate(prompt: str) -> str
```

완성된 단일 prompt에 대한 답변 문자열을 반환해야 합니다.

### `Chunker`

```text
chunk(text: str) -> list[str]
```

text를 chunk 목록으로 나눕니다. `RAGCore`의 표준 ingestion 경로에서 빈 결과는 `ValueError`로 처리됩니다.

### `VectorStore`

```text
add(chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]
search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
delete_document(doc_id: str) -> None
delete_chunks(chunk_ids: list[str]) -> None
```

- `add`는 chunk 수와 같은 수의 chunk ID를 반환해야 합니다.
- `search`는 반드시 `user_id` scope를 적용해야 합니다.
- 직접 주입 구현체도 chunk/vector cardinality 계약을 지켜야 합니다.

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
```

user 범위를 받는 조회·삭제 메서드는 반드시 `user_id`를 적용해야 합니다. 이 protocol에는 `check()`나 health API가 없습니다.

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

저장 메서드는 opaque asset reference를 반환해야 합니다. `file_stream`은 caller-owned이므로 adapter가 임의로 닫아서는 안 됩니다.

## 4. `RAGCore` facade

canonical import: `from rag_system_core import RAGCore`

### 4.1 생성자

```text
RAGCore(
    *,
    embedding_client: EmbeddingClient,
    generation_client: GenerationClient,
    vector_store: VectorStore,
    metadata_store: MetadataRepository,
    document_storage: DocumentAssetStorage,
    chunker: Chunker,
) -> None
```

모든 collaborator가 필수인 dependency-injection 생성자입니다. `RAGCore`는 주입된 client/store의 lifecycle을 소유하지 않으며 `close()` 또는 health-check runner를 제공하지 않습니다.

### 4.2 Ingestion API

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
- `ingest_text`는 text를 `strip()`한 뒤 asset upload를 수행합니다.
- stream/path byte payload는 UTF-8 text로 decode합니다.
- `ingest_file_stream`에서 `source`가 없거나 공백이면 `ValueError`입니다.
- `ingest_file_path`에서 `source`를 생략하면 파일명이 사용됩니다.
- ingestion마다 `job_id`와 `doc_id`가 생성됩니다.
- asset upload와 document metadata 생성은 tracked progress pipeline보다 앞서 수행될 수 있습니다. 후속 단계가 실패해도 distributed transaction 전체 rollback은 보장하지 않습니다.

### 4.3 Retrieval / generation

```text
query(*, user: AuthenticatedUser, question: str, top_k: int = 3) -> QueryResult
```

질문을 embedding하고 `user.sub`로 vector 검색을 제한한 뒤 generation client를 호출합니다. 생성 prompt는 `[System Prompt]`, `[Retrieved Context]`, `[User Query]` 섹션을 포함합니다.

### 4.4 Document management와 progress

```text
list_documents(*, user: AuthenticatedUser) -> list[DocumentRecord]
get_document(doc_id: str, *, user: AuthenticatedUser) -> DocumentRecord | None
list_document_chunks(doc_id: str, *, user: AuthenticatedUser) -> list[ChunkRecord]
list_ingestion_progress(
    doc_id: str, *, user: AuthenticatedUser,
    job_id: str | None = None
) -> list[IngestionProgressRecord]
get_ingestion_step_statuses(
    doc_id: str, *, user: AuthenticatedUser,
    job_id: str | None = None
) -> dict[str, str]
delete_document(doc_id: str, *, user: AuthenticatedUser) -> bool
```

- 다른 사용자의 문서는 조회 대상이 아닙니다.
- `list_ingestion_progress`는 transition history를 반환합니다.
- `get_ingestion_step_statuses`는 `load`부터 `chunk_persistence`까지 정의된 모든 단계의 최종 상태를 map으로 반환합니다. 문서가 존재하고 `job_id`가 없지만 progress가 없으면 모든 단계가 `not_started`입니다. 알 수 없는 문서나 해당 `job_id`의 progress가 없으면 빈 dict가 될 수 있습니다.
- `delete_document`는 user-scoped document가 없으면 `False`를 반환합니다.
- 삭제 순서는 vector store → document asset → metadata store입니다. 중간 실패 시 이미 정리된 artifact가 있을 수 있으며 distributed rollback은 제공하지 않습니다.

## 5. Composition API

### 5.1 `RAGServiceFactory` protocol

canonical implementation path: `rag_system_core.composition.service_factory`. 일반 애플리케이션은 `rag_system_core` 또는 `rag_system_core.composition`의 compatibility export를 사용할 수 있습니다.

```text
create_embedding_client() -> EmbeddingClient
create_generation_client() -> GenerationClient
create_vector_store() -> VectorStore
create_document_storage() -> DocumentAssetStorage
create_metadata_store(*, metadata_path: str | Path | None = None) -> MetadataRepository
create_chunker(*, chunk_size: int, chunk_overlap: int) -> Chunker
```

이 protocol은 `RAGCore` 조립에 필요한 collaborator factory 계약만 정의합니다.

### 5.2 `DocmeshRAGServiceFactory`

canonical import: `from rag_system_core import DocmeshRAGServiceFactory`

#### Direct constructor

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

`owns_dms_sdk`는 source compatibility를 위해 남아 있지만 현재 Factory의 `close()`가 DMS SDK를 닫는 소유권을 만들지는 않습니다.

#### Class methods

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
) -> DocmeshRAGServiceFactory
```

- `from_clients`는 host-owned DMS Engine/MinIO와 이미 만든 RAG collaborator를 받아 DMS SDK를 생성합니다.
- `from_host_clients`는 raw Ollama/Milvus client로 RAG adapter를 만들고 DMS 조립을 위임합니다.
- 두 classmethod는 환경변수, `ServiceConfigs`, `ServiceBundle`을 읽거나 보관하지 않습니다.
- `metadata_engine`이 제공된 Factory는 `create_rag_core()`를 바로 사용할 수 있습니다. 제공되지 않은 경우 `create_metadata_store(metadata_path=...)`를 별도로 호출할 수 있지만 `create_rag_core()`는 `metadata_path` 인자를 받지 않습니다.

#### Factory methods와 lifecycle

```text
create_embedding_client() -> EmbeddingClient
create_generation_client() -> GenerationClient
create_vector_store() -> VectorStore
create_document_storage() -> DmsDocumentStorage
create_metadata_store(*, metadata_path: str | Path | None = None) -> MetadataStore
create_chunker(*, chunk_size: int, chunk_overlap: int) -> FixedWindowChunker
create_rag_core(*, chunk_size: int = 512, chunk_overlap: int = 64) -> RAGCore
close() -> None
__enter__() -> DocmeshRAGServiceFactory
__exit__(exc_type, exc_value, traceback) -> None
```

- `create_rag_core()`는 Factory의 collaborator와 `metadata_engine`을 사용해 `RAGCore`를 조립합니다.
- embedding/generation/vector collaborator가 없는 direct Factory에서 해당 `create_*`를 호출하면 `RuntimeError`입니다.
- `metadata_engine`이 없고 `metadata_path`도 주어지지 않으면 metadata store 생성 시 `ValueError`입니다.
- Factory context는 DMS SDK, host-owned Engine/MinIO/transport client, 주입된 RAG collaborator를 닫지 않습니다.
- `metadata_path`로 Factory가 직접 생성해 추적한 `MetadataStore`만 `close()`에서 정리합니다. `metadata_engine`으로 만든 store는 caller-owned입니다.

### 5.3 RAG adapter factory functions

canonical import: `rag_system_core.composition.rag_factories`; compatibility import: `rag_system_core.composition.factories`

```text
create_rag_embedding_client(
    *,
    settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    model: str | None = None,
    client: object | None = None,
) -> EmbeddingClient

create_rag_generation_client(
    *,
    settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    model: str | None = None,
    client: object | None = None,
) -> GenerationClient

create_rag_vector_store(
    *,
    settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
    collection_name: str | None = None,
    timeout: float | None = None,
    client: object | None = None,
) -> VectorStore
```

해석 순서는 다음과 같습니다.

1. 명시적 `client`와 `model`/`collection_name`/`timeout`
2. 명시적 `settings`
3. `bundle.configs`
4. embedding/generation model은 설정값이 없으면 빈 값이 되어 `ValueError`
5. vector collection은 `rag_chunks`, timeout은 `30.0`

client가 없고 settings/bundle로 client를 생성할 수 없으면 `RuntimeError`입니다. 명시적 `settings`가 `bundle`보다 우선합니다. 명시적으로 빈 model을 전달하면 설정값으로 대체하지 않고 `ValueError`가 발생합니다.

### 5.4 Explicit configuration types

canonical import: `rag_system_core.composition.configuration`

```text
ConfigError(ValueError)
MilvusConfig(
    *, endpoint: str, token: str | None = None,
    db_name: str = "default", collection: str | None = None,
    secure: bool = False, connect_timeout_seconds: int = 10,
    request_timeout_seconds: int = 30, max_retries: int = 3,
)
OllamaConfig(
    *, host: str, verify_ssl: bool = True,
    follow_redirects: bool = True, generation_model: str | None = None,
    embedding_model: str | None = None, request_timeout_seconds: int = 120,
    max_retries: int = 2,
)
ServiceConfigs(
    milvus: MilvusConfig | None = None,
    ollama: OllamaConfig | None = None,
)
ServiceSelection(service: Service)
RuntimePlan(
    services: tuple[ServiceSelection | Service, ...],
    one_of: tuple[tuple[Service, ...], ...] = (),
)
Service.parse(value: Service | str) -> Service
RuntimePlan.selected_services -> frozenset[Service]
```

- `MilvusConfig.endpoint`와 `OllamaConfig.host`는 필수입니다.
- `connect_timeout_seconds`, `request_timeout_seconds`는 1 이상, `max_retries`는 0 이상이어야 합니다.
- `Service`는 `MILVUS="milvus"`, `OLLAMA="ollama"` 두 값만 지원합니다. `parse()`는 문자열을 소문자로 정규화하고 미지원 값에 `ConfigError`를 발생시킵니다.
- `ServiceSelection`은 `service`만 보유하며 required flag는 없습니다.
- `RuntimePlan`은 빈 service, 중복 선택, 선택되지 않은 `one_of` service를 거부합니다.
- 이 모델들은 process environment를 읽지 않습니다. Pydantic `BaseModel`의 상속 serialization API는 별도 계약이 아니라 dependency-provided behavior입니다.

### 5.5 Runtime plan과 `ServiceBundle`

canonical import: `rag_system_core.composition.docmesh_runtime`

```text
RAG_SERVICES = frozenset({"milvus", "ollama"})

build_docmesh_runtime_plan(
    *,
    services: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = (),
) -> RuntimePlan

ServiceBundle(
    configs: ServiceConfigs,
    clients: dict[str, object],
    selected_services: frozenset[str],
)

assemble_docmesh_services(
    *, plan: RuntimePlan, settings: ServiceConfigs
) -> ServiceBundle

create_docmesh_service_client(
    service_name: str,
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
) -> object | None

ServiceBundle.get_client(service: Service | str) -> object
ServiceBundle.close() -> None
```

- `build_docmesh_runtime_plan(services=None)`은 `milvus`와 `ollama`를 모두 선택합니다.
- `assemble_docmesh_services`는 explicit `ServiceConfigs`로 client를 만들며 누락된 설정에는 `ConfigError`를 발생시킵니다.
- `create_docmesh_service_client`는 bundle에 client가 없거나 settings가 없으면 `None`을 반환할 수 있습니다.
- `get_client`에서 없는 service를 요청하면 `ConfigError`입니다.
- `ServiceBundle.close()`는 bundle이 만든 client 중 `close()`를 제공하는 것을 역순으로 닫고, 여러 번 호출해도 반복 정리하지 않습니다. bundle은 context manager가 아닙니다.

### 5.6 DMS client assembly

canonical import: `rag_system_core.composition` 또는 `rag_system_core.composition.dms_runtime`

```text
create_dms_sdk_from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
) -> dms.DefaultDocumentManagementSDK
```

이 helper는 dms-core의 `DocumentManagementSDKFactory(...).create()`를 사용합니다. Engine과 MinIO client는 caller-owned이며 helper가 process environment를 읽거나 lifecycle을 등록하지 않습니다.

## 6. Built-in adapter API

### `FixedWindowChunker`

canonical import: `rag_system_core.adapters.FixedWindowChunker`

```text
FixedWindowChunker(chunk_size: int, chunk_overlap: int) -> None
chunk(text: str) -> list[str]
```

`chunk_size > 0`, `0 <= chunk_overlap < chunk_size`를 요구합니다. 입력 whitespace를 한 칸으로 정규화하고 문자 수 기준 fixed window를 반환합니다. 빈/whitespace-only 입력은 빈 list입니다.

### `OllamaEmbeddingClient`

canonical import: `rag_system_core.OllamaEmbeddingClient` (advanced path: `rag_system_core.adapters.ollama`)

```text
OllamaEmbeddingClient(*, client: Any, model: str) -> None
embed(texts: list[str]) -> list[list[float]]
```

주입 client는 `embed(model=<model>, input=<texts>)`를 제공하고 응답에 `embeddings` key를 포함해야 합니다.

- 빈 model은 `ValueError`
- 빈 text list는 `[]`
- transport 예외는 `RuntimeError`
- `embeddings` key가 없거나 응답 형식이 잘못되면 `RuntimeError`
- 반환 vector 값은 `float`로 변환됩니다.

### `OllamaGenerationClient`

canonical import: `rag_system_core.OllamaGenerationClient` (advanced path: `rag_system_core.adapters.ollama`)

```text
OllamaGenerationClient(*, client: Any, model: str) -> None
generate(prompt: str) -> str
```

주입 client는 `chat(model=<model>, messages=[{"role": "user", "content": prompt}])`를 제공하고 응답의 `message.content`를 반환해야 합니다. 빈 model, transport 예외, malformed response의 동작은 embedding adapter와 같은 `ValueError`/`RuntimeError` 계약을 따릅니다.

두 Ollama adapter에는 `check()` health method가 없습니다.

## 7. Storage API

### 7.1 `MetadataStore`와 ORM models

canonical import: `rag_system_core.storage`

```text
MetadataStore(engine: sqlalchemy.engine.Engine) -> None
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
```

`MetadataStore`는 주입된 SQLAlchemy `Engine`에 `documents`, `chunks`, `ingestion_progress` ORM table을 초기화합니다. `close()`는 해당 Engine에 `dispose()`를 호출합니다. user-scoped 조회·삭제는 `user_id` 조건을 적용합니다.

| public ORM model | 주요 column |
|---|---|
| `DocumentModel` | `doc_id`, `user_id`, `source`, `created_at`, public `asset_reference` (physical column name `storage_path`) |
| `ChunkModel` | `chunk_id`, `doc_id`, `user_id`, `chunk_index`, `content`, `metadata_json` |
| `IngestionProgressModel` | `progress_id`, `job_id`, `doc_id`, `user_id`, `source`, `step_name`, `step_order`, `status`, `created_at` |

ORM model은 SQLAlchemy `DeclarativeBase` mapping export입니다. 내부 conversion helper는 `__all__`에 없어 공개 계약이 아닙니다.

### 7.2 `MilvusLiteVectorStore`

canonical import: `rag_system_core.storage.MilvusLiteVectorStore`

```text
MilvusLiteVectorStore(
    *, collection_name: str, timeout: float = 30.0, client: Any
) -> None
add(chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]
search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
delete_document(doc_id: str) -> None
delete_chunks(chunk_ids: list[str]) -> None
```

- 빈 chunk list는 `[]`입니다.
- chunk/vector 개수가 다르면 `ValueError`입니다.
- 첫 `add`에서 collection이 없으면 vector dimension, COSINE metric, auto integer ID로 collection을 생성합니다.
- 검색은 escaped `user_id` filter를 적용합니다. non-positive `top_k`, 빈 query vector, 없는 collection은 빈 결과입니다.
- `delete_chunks`는 chunk ID를 integer ID로 변환해 Milvus에 전달합니다.
- 이 adapter에도 `check()` health method는 없습니다.

### 7.3 `DmsDocumentStorage`

canonical import: `rag_system_core.storage.DmsDocumentStorage`

```text
DmsDocumentStorage(sdk: DocumentManagementSdk) -> None
store_text(*, doc_id: str, user_id: str, text: str, source: str, idempotency_key: str) -> str
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

- `DocumentManagementSdk`는 `dms.DocumentManagementClient`의 module-level alias입니다. DMS SDK 전체 API를 이 package가 재정의하지 않습니다.
- upload 결과의 `document_id`가 요청한 `doc_id`와 다르면 `RuntimeError`입니다.
- text upload는 UTF-8 bytes, user/source metadata, `created_by=user_id`, idempotency key와 scope를 DMS request에 전달합니다.
- stream/path upload는 signature에 `idempotency_key`를 받지만 현재 구현은 DMS request에 전달하지 않습니다.
- path의 source 기본값은 파일명이며 MIME type은 filename으로 추정합니다.
- asset reference가 없으면 load/delete는 각각 `None`/no-op입니다.
- DMS `DocumentNotFoundError`와 `DocumentDeletedError`는 load에서 `None`, delete에서 idempotent completion으로 변환됩니다.

## 8. Advanced domain service API

canonical import: `rag_system_core.domain.core`입니다. 이 계층은 `AuthenticatedUser`를 받지 않고 이미 해석된 `user_id`를 직접 받으므로, 인증과 user-scope 보장은 호출자 책임입니다. 일반 애플리케이션에는 user-aware `RAGCore`를 권장합니다.

### `IngestionService`

```text
IngestionService(
    *, chunker: Chunker, embedding_client: EmbeddingClient,
    vector_store: VectorStore, metadata_store: MetadataRepository,
    document_storage: DocumentAssetStorage,
) -> None
ingest_text(*, user_id: str, text: str, source: str) -> IngestResult
ingest_file_stream(*, user_id: str, file_stream: BinaryIO, source: str) -> IngestResult
ingest_file_path(*, user_id: str, file_path: Path, source: str | None = None) -> IngestResult
preprocess(text: str) -> str
chunk(text: str) -> list[str]
embed(chunks: list[str]) -> list[list[float]]
store(chunks: list[ChunkRecord], embeddings: list[list[float]]) -> None
```

`PIPELINE_STEPS` class attribute는 `load`, `preprocess`, `chunking`, `embedding`, `vector_store`, `chunk_persistence`입니다.

### `RetrievalService`

```text
RetrievalService(*, embedding_client: EmbeddingClient, vector_store: VectorStore) -> None
search(*, user_id: str, question: str, top_k: int) -> list[ChunkRecord]
embed_query(question: str) -> list[float]
vector_search(*, user_id: str, query_vector: list[float], top_k: int) -> list[ChunkRecord]
```

### `GenerationService`

```text
GenerationService(
    generation_client: GenerationClient,
    system_prompt: str | None = None,
) -> None
build_prompt(*, question: str, context_chunks: list[ChunkRecord]) -> str
call_llm(prompt: str) -> str
generate(*, question: str, context_chunks: list[ChunkRecord]) -> QueryResult
```

기본 system prompt는 다음 문자열입니다.

```text
You are a helpful RAG assistant. Answer only from the retrieved context.
```

`call_llm()`은 마지막 prompt를 `last_prompt`에 기록하고 generation client를 호출합니다. `domain.core`의 record/protocol 이름은 canonical owner의 compatibility re-export입니다.

## 9. 전체 공개 export 추적표

아래 표는 generated artifact를 제외한 source tree의 **14개 비어 있지 않은 `__all__` 선언**을 모두 나열합니다. 동일한 객체가 여러 모듈에서 re-export되더라도 module별 export를 생략하지 않습니다.

| 공개 import path | `__all__` export | API 절 | 예제 / 설정 / 환경 |
|---|---|---|---|
| `rag_system_core` | `AuthenticatedUser`, `ChunkRecord`, `DocmeshRAGServiceFactory`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestResult`, `IngestionProgressRecord`, `OllamaEmbeddingClient`, `OllamaGenerationClient`, `QueryResult`, `RAGCore`, `RAGServiceFactory` | §2, §4, §5.2, §6 | [Examples](Examples) §1–§3, §6; env 자동 설정 없음 |
| `rag_system_core.adapters` | `FixedWindowChunker` | §6 | [Examples](Examples) §1, §6; [Configuration](Configuration) §2 |
| `rag_system_core.ports` | `Chunker`, `DocumentAssetStorage`, `EmbeddingClient`, `GenerationClient`, `MetadataRepository`, `VectorStore` | §3 | [Examples](Examples) §1, §7; 환경 설정 없음 |
| `rag_system_core.types` | `AuthenticatedUser`, `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `IngestResult`, `IngestionProgressRecord`, `QueryResult` | §2, §3 | [Examples](Examples) §1–§2, §7; 환경 설정 없음 |
| `rag_system_core.composition` | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `assemble_docmesh_services`, `create_dms_sdk_from_clients`, `create_docmesh_service_client` | §5 | [Examples](Examples) §3–§5; [Configuration](Configuration) §2–§5 |
| `rag_system_core.composition.configuration` | `ConfigError`, `MilvusConfig`, `OllamaConfig`, `RuntimePlan`, `Service`, `ServiceConfigs`, `ServiceSelection` | §5.4 | [Examples](Examples) §4; [Configuration](Configuration) §2–§3; process env 없음 |
| `rag_system_core.composition.dms_runtime` | `create_dms_sdk_from_clients` | §5.6 | [Examples](Examples) §5; [Configuration](Configuration) §6 |
| `rag_system_core.composition.docmesh_runtime` | `RAG_SERVICES`, `ServiceBundle`, `assemble_docmesh_services`, `build_docmesh_runtime_plan`, `create_docmesh_service_client` | §5.5 | [Examples](Examples) §4; [Configuration](Configuration) §4–§5 |
| `rag_system_core.composition.factories` | `DocmeshRAGServiceFactory`, `RAGServiceFactory`, `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5.2–§5.3 | [Examples](Examples) §3–§4; [Configuration](Configuration) §4 |
| `rag_system_core.composition.rag_factories` | `create_rag_embedding_client`, `create_rag_generation_client`, `create_rag_vector_store` | §5.3 | [Examples](Examples) §4; [Configuration](Configuration) §4 |
| `rag_system_core.composition.service_factory` | `DocmeshRAGServiceFactory`, `RAGServiceFactory` | §5.1–§5.2 | [Examples](Examples) §3; [Configuration](Configuration) §6–§7 |
| `rag_system_core.domain.core` | `ChunkRecord`, `DocumentRecord`, `EmbeddingClient`, `GenerationClient`, `GenerationService`, `IngestResult`, `IngestionProgressRecord`, `IngestionService`, `QueryResult`, `RAGCore`, `RetrievalService`, `VectorStore` | §4, §8 | [Examples](Examples) §1, §7; 환경 설정 없음 |
| `rag_system_core.storage` | `ChunkModel`, `DmsDocumentStorage`, `DocumentModel`, `IngestionProgressModel`, `MetadataStore`, `MilvusLiteVectorStore` | §7 | [Examples](Examples) §1, §5–§6; [Configuration](Configuration) §6–§7 |
| `rag_system_core.storage.dms_document_storage` | `DmsDocumentStorage`, `DocumentManagementSdk` | §7.3 | [Examples](Examples) §5–§6; [Configuration](Configuration) §6 |

`rag_system_core.domain.__init__`의 빈 `__all__`은 의도적으로 export 표에서 제외했습니다. `__all__`에 없는 `escape_milvus_string`, `chunk_record_from_milvus_hit`, ORM conversion helper 등은 내부 구현입니다.

## 10. 구현·테스트·요구사항 추적표

경로는 repository root 기준입니다. `PRD`/`SRS` version label은 현재 `0.4.0` implementation baseline으로 남아 있으므로, 아래 ID는 요구사항 근거로만 사용하고 API version은 이 페이지의 `0.5.0` source revision으로 식별합니다.

| API surface | 구현 source | 주요 테스트 근거 | PRD / SRS 근거 | Wiki 예제 |
|---|---|---|---|---|
| root records, user scope, protocol ownership | `rag_system_core/__init__.py`, `types.py`, `ports.py` | `test_rag_system_core/domain/test_architecture.py`, `test_ingestion_api.py`, `test_query.py` | PRD-FR-1–3; SRS-FR-001–003, 008–011, SRS-NFR-006–007, SRS-NFR-012 | Examples §1–§2, §7 |
| `RAGCore` ingestion/query/document API | `rag_system_core/domain/core.py`, `domain/ingestion.py`, `domain/retrieval.py`, `domain/generation.py` | `test_rag_system_core/domain/test_ingestion_api.py`, `test_query.py`, `test_metadata_and_progress.py`, `test_deletion_and_rollback.py` | PRD-FR-4–12, 15–17; SRS-FR-012–023, 030–037, 045–063, 078 | Examples §1–§2 |
| `get_ingestion_step_statuses` derived summary | `rag_system_core/domain/core.py` | `test_rag_system_core/domain/test_metadata_and_progress.py`, `test_deletion_and_rollback.py` | PRD-FR-9; SRS-FR-023, 056 | Examples §2 |
| public ports and custom collaborator contracts | `rag_system_core/ports.py` | `test_rag_system_core/domain/test_architecture.py`, `test_ingestion_api.py` | SRS-FR-001–003, SRS-NFR-005, SRS-NFR-012 | Examples §1, §7 |
| `FixedWindowChunker` | `rag_system_core/adapters/chunking.py`, `adapters/__init__.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_metadata_and_progress.py` | PRD-FR-8; SRS-FR-016–019 | Examples §1, §6 |
| Ollama adapters | `rag_system_core/adapters/ollama.py` | `test_rag_system_core/adapters/test_ollama_embedding_client.py`, `test_ollama_generation_client.py`, `test_rag_system_core/composition/test_docmesh_integration.py` | PRD-FR-11–12; SRS-FR-030–037, SRS-FR-077 | Examples §6 |
| explicit config models and runtime plan | `rag_system_core/composition/configuration.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_docmesh_integration.py` | PRD-FR-19; SRS-FR-038–044, SRS-FR-070–071, SRS-NFR-016 | Examples §4; Configuration §2–§5 |
| `ServiceBundle` and runtime assembly | `rag_system_core/composition/docmesh_runtime.py` | `test_rag_system_core/composition/test_docmesh_integration.py`, `test_core_configuration.py`, `test_module_boundaries.py` | PRD-FR-19; SRS-FR-070–071, SRS-NFR-013, SRS-NFR-015 | Examples §4 |
| RAG adapter factory functions | `rag_system_core/composition/rag_factories.py`, `composition/factories.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_docmesh_integration.py`, `test_module_boundaries.py` | PRD-FR-19; SRS-FR-038–044, SRS-FR-070–071 | Examples §4; Configuration §4 |
| DMS SDK assembly and Factory | `rag_system_core/composition/dms_runtime.py`, `composition/service_factory.py` | `test_rag_system_core/composition/test_docmesh_integration.py`, `test_core_configuration.py`, `test_object_creation.py` | PRD-FR-19; SRS-FR-075, SRS-FR-079, SRS-NFR-015–016 | Examples §3, §5; Configuration §6–§7 |
| `MetadataStore` and ORM models | `rag_system_core/storage/metadata_store.py`, `storage/__init__.py` | `test_rag_system_core/domain/test_metadata_and_progress.py`, `test_deletion_and_rollback.py`, `test_object_creation.py` | PRD-FR-15–16; SRS-FR-045–052, SRS-DR-001–005, SRS-NFR-008 | Examples §1, §6; Configuration §7 |
| `MilvusLiteVectorStore` | `rag_system_core/storage/vector_store.py`, `storage/__init__.py` | `test_rag_system_core/composition/test_core_configuration.py`, `test_docmesh_integration.py`, `test_object_creation.py` | PRD-FR-13–14, 17; SRS-FR-032, 038–044, 051, 061–063 | Examples §4, §6 |
| `DmsDocumentStorage` and DMS alias | `rag_system_core/storage/dms_document_storage.py` | `test_rag_system_core/storage/test_dms_document_storage.py`, `test_ingestion_api.py`, `test_docmesh_integration.py` | PRD-FR-5, 17; SRS-FR-024–029, 078, SRS-DR-006–007 | Examples §3, §5–§6 |
| package/submodule export boundaries | all non-empty `__all__` modules listed in §9 | `test_rag_system_core/composition/test_module_boundaries.py`, `test_rag_system_core/domain/test_architecture.py` | PRD-FR-19; SRS-NFR-004–005, SRS-NFR-011–013 | Examples §8 |

추적표는 representative automated evidence를 표시합니다. `Partially verified` 또는 inspection-only requirement를 테스트 전체가 검증했다고 해석하지 마십시오. 최신 검증 명령은 [Examples §9](Examples)의 명령을 사용하십시오.

## 11. 제한과 비목표

- HTTP 서버가 아닌 동기 Python library입니다.
- process environment만으로 완성된 `RAGCore`를 반환하는 bootstrap helper는 없습니다.
- 파일 입력은 UTF-8 text를 전제하며 PDF/OCR/parser는 제공하지 않습니다.
- `RAGCore`와 host-owned collaborator의 lifecycle을 소유하지 않습니다.
- `ServiceBundle`은 명시적으로 `close()`해야 하며 context manager가 아닙니다.
- ingestion/deletion은 vector, metadata, DMS 사이의 distributed transaction이 아닙니다.
- `DocmeshRAGServiceFactory`는 DMS SDK와 host-owned resources를 닫지 않고, compatibility `metadata_path`로 자신이 만든 MetadataStore만 추적·정리합니다.
- 현재 구현에는 Ollama/metadata/vector/DMS health-check API가 없습니다.
