---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Configuration
ingested: 2026-08-20
sha256: 77b5cdf6aab72c708be695c774f30789d2344011bbab02fc895027ca93e5ce4b
---
# 설정 레퍼런스

이 문서는 현재 구현의 **명시적 configuration model, runtime plan, client assembly 경계와 lifecycle**을 설명합니다.

- 공개 API: [API-Reference](API-Reference)
- 실행 흐름: [Examples](Examples)
- 구현 기준: `rag-system-core` `0.4.0`

> 중요: 현재 패키지는 RAG 또는 DMS 설정을 process environment에서 자동으로 읽는 loader를 제공하지 않습니다. 상위 애플리케이션이 `ServiceConfigs`와 client를 직접 만들거나 host-owned raw client를 Factory에 전달해야 합니다.

## 1. 설정 원천과 책임

| 영역 | 현재 지원 경로 | 책임 |
|---|---|---|
| RAG runtime | 명시적 `ServiceConfigs`, `ServiceBundle`, 또는 client 인자 | 호출자가 설정과 client를 준비 |
| DMS runtime | `create_dms_sdk_from_clients(...)` | 호출자가 SQLAlchemy `Engine`, MinIO client, bucket을 준비 |
| RAG metadata | `metadata_engine` 또는 compatibility `metadata_path` | Factory/호출자 lifecycle 규칙 적용 |

`.env`, `DOCMESH_*`, `OLLAMA_*`, `MILVUS_*`, `DMS_*`를 자동으로 로드하는 public API는 현재 없습니다. `pydantic-settings`는 선언 의존성이지만 이 저장소의 composition 경로가 환경변수 loader를 호출한다는 뜻은 아닙니다.

## 2. RAG 설정 모델

Canonical import:

```python
from rag_system_core.composition.configuration import (
    ConfigError,
    HealthcheckPolicy,
    MilvusConfig,
    OllamaConfig,
    RuntimePlan,
    Service,
    ServiceConfigs,
    ServiceSelection,
)
```

### `MilvusConfig`

| 필드 | 타입 | 기본값/제약 |
|---|---|---|
| `endpoint` | `str` | 필수 |
| `token` | `str | None` | `None` |
| `db_name` | `str` | `"default"` |
| `collection` | `str | None` | `None` |
| `secure` | `bool` | `False` |
| `connect_timeout_seconds` | `int` | `10`, `>=1` |
| `request_timeout_seconds` | `int` | `30`, `>=1` |
| `max_retries` | `int` | `3`, `>=0` |

### `OllamaConfig`

| 필드 | 타입 | 기본값/제약 |
|---|---|---|
| `host` | `str` | 필수 |
| `verify_ssl` | `bool` | `True` |
| `follow_redirects` | `bool` | `True` |
| `generation_model` | `str | None` | `None` |
| `embedding_model` | `str | None` | `None` |
| `request_timeout_seconds` | `int` | `120`, `>=1` |
| `max_retries` | `int` | `2`, `>=0` |

`ServiceConfigs`는 다음 dataclass입니다.

```text
ServiceConfigs(
    milvus: MilvusConfig | None = None,
    ollama: OllamaConfig | None = None,
)
```

`Service`는 `Service.MILVUS`, `Service.OLLAMA` 두 값만 지원합니다. `Service.parse(...)`는 문자열을 소문자로 정규화하고 알 수 없는 service에 `ConfigError`를 발생시킵니다.

## 3. Runtime plan

```text
ServiceSelection(service: Service, required: bool = False)
HealthcheckPolicy(on_startup: bool = False, parallel: bool = False)
RuntimePlan(
    services: tuple[ServiceSelection | Service, ...],
    one_of: tuple[tuple[Service, ...], ...] = (),
    healthcheck: HealthcheckPolicy = HealthcheckPolicy(),
)
```

`RuntimePlan`은 빈 service, 중복 선택, 선택되지 않은 `one_of` service를 거부합니다. plan을 만드는 helper는 환경을 읽지 않습니다.

```python
from rag_system_core.composition.configuration import (
    HealthcheckPolicy,
    RuntimePlan,
    Service,
    ServiceSelection,
)

plan = RuntimePlan(
    services=(
        ServiceSelection(Service.OLLAMA, required=True),
        ServiceSelection(Service.MILVUS, required=True),
    ),
    healthcheck=HealthcheckPolicy(on_startup=False, parallel=True),
)
assert plan.selected_services == {Service.OLLAMA, Service.MILVUS}
```

## 4. RAG adapter factory 설정 해석

Canonical import:

```python
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)
```

입력 우선순위:

1. 명시적 `client`/`model`/`collection_name`/`timeout` 인자
2. `settings`가 제공한 설정과 `bundle.configs`
3. vector collection `rag_chunks`, timeout `30.0`

`settings`가 `bundle`과 함께 있으면 명시적 `settings`가 우선합니다. client가 없고 settings/bundle로 client를 만들 수 없으면 `RuntimeError`입니다. 빈 embedding/generation model은 `ValueError`입니다.

```python
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    ServiceConfigs,
)
from rag_system_core.composition.rag_factories import create_rag_vector_store

settings = ServiceConfigs(
    milvus=MilvusConfig(endpoint="./data/rag-vectors.db"),
    ollama=OllamaConfig(
        host="http://ollama:11434",
        embedding_model="bge-m3",
        generation_model="gpt-oss:20b",
    ),
)

# 외부 client를 별도로 생성해 전달하는 경우 collection/timeout만 adapter가 해석합니다.
# vector_store = create_rag_vector_store(
#     settings=settings,
#     client=milvus_client,
# )
```

## 5. Runtime bundle

```text
build_docmesh_runtime_plan(
    *,
    services: set[str | Service] | None = None,
    required: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = (),
    check_on_startup: bool = False,
    parallel_healthchecks: bool = False,
) -> RuntimePlan

assemble_docmesh_services(*, plan: RuntimePlan, settings: ServiceConfigs) -> ServiceBundle
```

`assemble_docmesh_services`는 `settings`에 있는 Ollama/Milvus 설정으로 client를 생성합니다. 반환된 `ServiceBundle`은 context manager가 아니므로 `try/finally`와 `bundle.close()`를 사용합니다.

```python
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    ServiceConfigs,
)
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)

settings = ServiceConfigs(
    milvus=MilvusConfig(endpoint="./data/rag-vectors.db"),
    ollama=OllamaConfig(host="http://ollama:11434"),
)
plan = build_docmesh_runtime_plan(
    services={"ollama", "milvus"},
    required={"ollama"},
    check_on_startup=False,
)
bundle = assemble_docmesh_services(plan=plan, settings=settings)
try:
    ollama_client = bundle.get_client("ollama")
finally:
    bundle.close()
```

`ServiceBundle.close()`는 bundle이 만든 client 중 `close()`를 제공하는 client를 역순으로 정리합니다. bundle 밖에서 만든 raw client는 호출자가 정리합니다.

## 6. DMS 조립

Canonical import:

```python
from rag_system_core.composition.dms_runtime import create_dms_sdk_from_clients
```

```text
create_dms_sdk_from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
) -> dms.DefaultDocumentManagementSDK
```

이 helper는 환경변수를 읽지 않습니다. SQLAlchemy `Engine`, MinIO client, bucket name은 호출자가 제공하며 underlying client lifecycle도 호출자 책임입니다. dms-core v0.9 SDK에는 `close()` lifecycle이 없으므로 `DocmeshRAGServiceFactory` context도 DMS SDK를 닫지 않습니다.

## 7. Metadata 경로

- `metadata_engine`을 Factory에 주입하면 `MetadataStore`가 해당 Engine에 바인딩됩니다. 이 경로의 Engine/MetadataStore lifecycle은 caller-owned입니다.
- `create_metadata_store(metadata_path=...)`를 호출하면 Factory가 SQLite Engine과 `MetadataStore`를 만들고 해당 store를 추적합니다.
- Factory `close()`는 Factory가 `metadata_path`로 만든 store만 정리합니다.
- `MetadataStore.close()`는 자신이 바인딩한 Engine에 `dispose()`를 호출합니다.

## 8. 설정 오류와 비목표

- `ConfigError`는 explicit RAG configuration 또는 invalid runtime plan 오류입니다.
- process environment를 자동으로 읽는 configuration API는 현재 지원하지 않습니다.
- DMS 설정 진단/환경 loader, `.env` 자동 로드, 임의 SDK `**kwargs` 전달은 현재 공개 계약이 아닙니다.
- 외부 service가 필요한 Ollama/Milvus/DMS 경로는 [Examples](Examples)와 API의 lifecycle 설명을 함께 확인하십시오.

## 9. 추적 근거

- 구현: `rag_system_core/composition/configuration.py`, `docmesh_runtime.py`, `rag_factories.py`, `dms_runtime.py`, `service_factory.py`
- 테스트: `test_rag_system_core/composition/test_core_configuration.py`, `test_docmesh_integration.py`
- 요구사항: `docs/prd.md` PRD-FR-19, `docs/srs.md` SRS-FR-038–044, SRS-FR-070–071, SRS-FR-075, SRS-FR-079, SRS-NFR-013, SRS-NFR-015–016
