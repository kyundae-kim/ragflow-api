---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Configuration
ingested: 2026-08-26
sha256: 432717bca9e5ca81e5f9ca7e4112a1f889e76e61b6634fd14bf9bd7df19c1a77
---
# 설정 레퍼런스

> **문서 기준 (version-identifiable)**
>
> | 항목 | 값 |
> |---|---|
> | package | `rag-system-core` |
> | package version | `0.5.0` (`pyproject.toml`) |
> | 구현 기준 source revision | `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3` |
> | Python | `>=3.11` |
> | runtime dependencies | `dms-core>=0.10.0`, `ollama>=0.6.2`, `pydantic-settings>=2.14.1`, `pymilvus[milvus-lite]>=3.0.1` |
>
> 이 페이지는 위 구현 기준의 explicit configuration contract입니다. `v0.5.0` tag가 없으므로 package version과 source commit을 함께 식별하십시오.

이 문서는 현재 구현의 **명시적 configuration model, runtime plan, client assembly 경계와 lifecycle**을 설명합니다.

- 공개 API: [API-Reference](API-Reference)
- 실행 흐름: [Examples](Examples)

## 1. 설정 원천과 책임

현재 package는 process environment를 읽어 RAG/DMS client 또는 완성된 `RAGCore`를 자동 생성하지 않습니다.

| 영역 | 현재 지원 경로 | 책임 |
|---|---|---|
| RAG service client | 명시적 `ServiceConfigs`, `ServiceBundle`, 또는 client 인자 | 호출자가 설정과 client를 준비 |
| RAG core | `RAGCore(...)` 직접 주입 또는 `DocmeshRAGServiceFactory` | 호출자가 collaborator와 lifecycle을 조립 |
| DMS runtime | `create_dms_sdk_from_clients(...)` / Factory classmethod | 호출자가 SQLAlchemy `Engine`, MinIO client, bucket을 준비 |
| RAG metadata | caller-provided `metadata_engine` 또는 Factory의 `metadata_path` compatibility path | ownership에 따라 caller 또는 Factory가 정리 |

따라서 `.env`, `DOCMESH_*`, `OLLAMA_*`, `MILVUS_*`, `DMS_*`를 자동으로 로드하는 public API나 `.env.example` 계약은 이 package에 없습니다. `pydantic-settings`가 dependency로 선언되어 있다는 사실은 environment loader의 존재를 의미하지 않습니다.

## 2. RAG 설정 모델

canonical import:

```python
from rag_system_core.composition.configuration import (
    ConfigError,
    MilvusConfig,
    OllamaConfig,
    RuntimePlan,
    Service,
    ServiceConfigs,
    ServiceSelection,
)
```

### `MilvusConfig`

```text
MilvusConfig(
    *,
    endpoint: str,
    token: str | None = None,
    db_name: str = "default",
    collection: str | None = None,
    secure: bool = False,
    connect_timeout_seconds: int = 10,
    request_timeout_seconds: int = 30,
    max_retries: int = 3,
)
```

| field | type | default / validation |
|---|---|---|
| `endpoint` | `str` | required |
| `token` | `str \| None` | `None` |
| `db_name` | `str` | `"default"` |
| `collection` | `str \| None` | `None` |
| `secure` | `bool` | `False` |
| `connect_timeout_seconds` | `int` | `10`, `>=1` |
| `request_timeout_seconds` | `int` | `30`, `>=1` |
| `max_retries` | `int` | `3`, `>=0` |

### `OllamaConfig`

```text
OllamaConfig(
    *,
    host: str,
    verify_ssl: bool = True,
    follow_redirects: bool = True,
    generation_model: str | None = None,
    embedding_model: str | None = None,
    request_timeout_seconds: int = 120,
    max_retries: int = 2,
)
```

| field | type | default / validation |
|---|---|---|
| `host` | `str` | required |
| `verify_ssl` | `bool` | `True` |
| `follow_redirects` | `bool` | `True` |
| `generation_model` | `str \| None` | `None` |
| `embedding_model` | `str \| None` | `None` |
| `request_timeout_seconds` | `int` | `120`, `>=1` |
| `max_retries` | `int` | `2`, `>=0` |

### `ServiceConfigs`

```text
ServiceConfigs(
    milvus: MilvusConfig | None = None,
    ollama: OllamaConfig | None = None,
)
```

`ServiceConfigs`는 명시적 settings container이며 환경변수와 연결되지 않습니다. model 이름이 필요한 Ollama factory를 사용할 때 `embedding_model`과 `generation_model`을 채워야 합니다.

## 3. Runtime plan

```text
ServiceSelection(service: Service)
RuntimePlan(
    services: tuple[ServiceSelection | Service, ...],
    one_of: tuple[tuple[Service, ...], ...] = (),
)
RuntimePlan.selected_services -> frozenset[Service]
```

`Service`는 `Service.MILVUS`와 `Service.OLLAMA`를 제공합니다. `Service.parse(...)`는 문자열을 lowercase로 정규화합니다.

`RuntimePlan`은 다음을 검증합니다.

- 하나 이상의 service 선택
- 중복 service 선택 금지
- 빈 `one_of` group 금지
- `one_of` group의 service가 plan에 실제 선택되어 있어야 함

```python
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    RuntimePlan,
    Service,
    ServiceConfigs,
    ServiceSelection,
)

settings = ServiceConfigs(
    milvus=MilvusConfig(endpoint="./data/rag-vectors.db"),
    ollama=OllamaConfig(
        host="http://ollama:11434",
        embedding_model="bge-m3",
        generation_model="gpt-oss:20b",
    ),
)
plan = RuntimePlan(
    services=(
        ServiceSelection(Service.OLLAMA),
        ServiceSelection(Service.MILVUS),
    ),
)
assert plan.selected_services == {Service.OLLAMA, Service.MILVUS}
```

## 4. RAG adapter factory 설정 해석

canonical import:

```python
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)
```

### 우선순위

1. 명시적 `client` 및 `model`/`collection_name`/`timeout`
2. 명시적 `settings`
3. `bundle.configs`
4. vector collection 기본값 `rag_chunks`
5. vector timeout 기본값 `30.0`

- `settings`가 `bundle`과 함께 있으면 `settings`가 우선합니다.
- 명시적 client는 client 자동 생성을 대체하지만, settings/bundle의 collection·timeout·model은 별도로 사용할 수 있습니다.
- client가 없고 settings/bundle로 생성할 수 없으면 `RuntimeError`입니다.
- model이 명시적으로 비어 있거나 settings에도 없으면 Ollama adapter 생성 시 `ValueError`입니다.
- vector collection/timeout은 explicit override가 없을 때 settings 값, 그 다음 `rag_chunks`/`30.0`을 사용합니다.

```python
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    ServiceConfigs,
)
from rag_system_core.composition.rag_factories import create_rag_vector_store

settings = ServiceConfigs(
    milvus=MilvusConfig(
        endpoint="./data/rag-vectors.db",
        collection="configured_chunks",
        request_timeout_seconds=18,
    ),
)

# milvus_client가 caller-owned로 준비되어 있다고 가정합니다.
vector_store = create_rag_vector_store(
    settings=settings,
    client=milvus_client,
)
assert vector_store.collection_name == "configured_chunks"
assert vector_store.timeout == 18.0
```

## 5. Runtime bundle lifecycle

canonical import:

```python
from rag_system_core.composition.docmesh_runtime import (
    RAG_SERVICES,
    ServiceBundle,
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
    create_docmesh_service_client,
)
```

```text
RAG_SERVICES = frozenset({"milvus", "ollama"})
build_docmesh_runtime_plan(
    *, services: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = ()
) -> RuntimePlan
assemble_docmesh_services(
    *, plan: RuntimePlan, settings: ServiceConfigs
) -> ServiceBundle
create_docmesh_service_client(
    service_name: str,
    *, settings: ServiceConfigs | None = None,
    bundle: ServiceBundle | None = None,
) -> object | None
```

`build_docmesh_runtime_plan(services=None)`은 두 RAG service를 선택합니다. `assemble_docmesh_services`는 explicit settings로 client를 조립하고, 실패 중 이미 만든 client가 있으면 정리한 뒤 예외를 전달합니다.

`ServiceBundle`은 다음 public state와 method를 가집니다.

```text
ServiceBundle(
    configs: ServiceConfigs,
    clients: dict[str, object],
    selected_services: frozenset[str],
)
get_client(service: Service | str) -> object
close() -> None
```

bundle은 context manager가 아닙니다. `try/finally`에서 `bundle.close()`를 호출하십시오. `close()`는 bundle이 만든 client 중 `close()`를 제공하는 client를 역순으로 닫으며 반복 호출은 no-op입니다. bundle 밖에서 만든 raw client는 caller가 정리합니다.

## 6. DMS 조립 경계

canonical import:

```python
from rag_system_core.composition import create_dms_sdk_from_clients
```

```text
create_dms_sdk_from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
) -> dms.DefaultDocumentManagementSDK
```

이 helper는 환경변수를 읽지 않고, dms-core의 `DocumentManagementSDKFactory`를 통해 SDK를 생성합니다. Engine, MinIO client, bucket name은 caller가 제공합니다. dms-core SDK와 underlying clients는 이 package의 Factory가 닫지 않습니다.

## 7. Metadata ownership과 compatibility path

### host-owned `metadata_engine`

`DocmeshRAGServiceFactory.from_clients(...)` 또는 `from_host_clients(...)`에 `metadata_engine`을 전달하면 Factory가 `MetadataStore(metadata_engine)`을 사용합니다.

- Engine과 MetadataStore lifecycle은 caller-owned입니다.
- Factory `close()`는 이 store를 추적하지 않습니다.
- `create_rag_core()`를 바로 사용할 수 있습니다.

### `metadata_path` compatibility path

```python
from rag_system_core import DocmeshRAGServiceFactory

factory = DocmeshRAGServiceFactory(
    dms_sdk=dms_sdk,
    embedding_client=embedding_client,
    generation_client=generation_client,
    vector_store=vector_store,
)
metadata = factory.create_metadata_store(metadata_path="./data/rag-metadata.db")
try:
    print(metadata.list_documents("user-a"))
finally:
    factory.close()
```

- `metadata_path`가 `None`이고 `metadata_engine`도 없으면 `ValueError`입니다.
- Factory는 path로 생성한 `MetadataStore`를 추적합니다.
- Factory `close()`는 추적 store를 닫고 SQLite Engine을 dispose합니다.
- `create_rag_core()` 자체는 `metadata_path`를 받지 않으므로, 완성된 Core에는 `metadata_engine`을 주입한 Factory를 사용하거나 별도 조립이 필요합니다.

## 8. 환경변수와 비목표

현재 public configuration contract에 포함되지 않는 것:

- `.env` 자동 로드
- `DOCMESH_*`, `OLLAMA_*`, `MILVUS_*`, `DMS_*` environment parsing
- configuration만으로 완성된 `RAGCore` bootstrap
- 임의 SDK `**kwargs` override
- health-check runner, startup check 옵션, health policy API

외부 service가 필요한 Ollama/Milvus/DMS 경로는 [Examples](Examples)의 §3–§7과 [API-Reference](API-Reference)의 composition/storage 계약을 함께 확인하십시오.

## 9. 추적 근거

- 구현: `rag_system_core/composition/configuration.py`, `docmesh_runtime.py`, `rag_factories.py`, `dms_runtime.py`, `service_factory.py`
- storage 구현: `rag_system_core/storage/metadata_store.py`, `vector_store.py`, `dms_document_storage.py`
- 테스트: `test_rag_system_core/composition/test_core_configuration.py`, `test_docmesh_integration.py`, `test_module_boundaries.py`, `test_rag_system_core/storage/test_dms_document_storage.py`
- 요구사항: `docs/prd.md` PRD-FR-13–19, `docs/srs.md` SRS-FR-038–052, SRS-FR-070–071, SRS-FR-075, SRS-FR-079, SRS-NFR-013, SRS-NFR-015–016
