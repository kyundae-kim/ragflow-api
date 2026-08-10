---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Configuration
ingested: 2026-08-10
sha256: 0060bb439a60c210a9a0ec44e3a39094ec71725397309a97db88cf802612d4d1
---
# 설정 레퍼런스

이 문서는 현재 구현의 configuration loader, runtime plan, DMS environment adapter가 읽는 값과 lifecycle을 정의합니다.

- 공개 API: [API-Reference](API-Reference)
- 실행 흐름: [Examples](Examples)
- 구현 기준: `rag-system-core` `0.3.0`

> 이 라이브러리는 `.env` 파일을 자동으로 읽지 않습니다. 상위 애플리케이션, process manager 또는 실행 환경이 값을 `os.environ`에 로드해야 합니다.

## 1. 설정 원천과 분리

현재 설정은 두 namespace로 분리됩니다.

| 영역 | Loader | 환경변수 prefix | 용도 |
|---|---|---|---|
| RAG runtime | `load_service_configs`, `load_available_service_configs`, `load_docmesh_settings` | `DOCMESH_`, `MILVUS_`, `OLLAMA_` | Ollama/Milvus client와 RAG adapter 조립 |
| DMS runtime | `load_dms_settings` | `DMS_` | DMS metadata backend와 MinIO 설정 진단/조립 |

RAG metadata용 SQLAlchemy Engine/SQLite 경로는 `DocmeshRAGServiceFactory` 또는 호출자가 별도로 관리합니다. `load_dms_settings`의 `DMS_SQLITE_PATH`는 DMS metadata 경로이며 RAG metadata와 다른 저장소입니다.

설정 loader에 임의 mapping이나 SDK `**kwargs`를 전달하는 API는 없습니다. DMS loader만 진단·테스트 목적으로 `env: Mapping[str, str] | None`을 받습니다.

## 2. RAG 공통 설정

`CommonConfig` import: `rag_system_core.composition.configuration.CommonConfig`

| 환경변수 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `DOCMESH_ENV` | `str` | `development` | 공통 runtime 환경 이름 |
| `DOCMESH_SECURITY_MODE` | `development \| production` | `None` | 지정하면 `is_production` 판정에 우선 |

```python
from rag_system_core.composition.configuration import CommonConfig

common = CommonConfig()
print(common.env, common.is_production)
```

`CommonConfig.is_production`은 `security_mode == "production"`이거나 `env`가 `prod`/`production`이면 `True`입니다. 이 값 자체가 transport TLS를 자동으로 켜거나 외부 service를 연결하지는 않습니다.

## 3. Ollama 설정

`OllamaConfig` import: `rag_system_core.composition.configuration.OllamaConfig`

| 환경변수 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `OLLAMA_HOST` | `str` | 필수 | Ollama endpoint |
| `OLLAMA_VERIFY_SSL` | `bool` | `true` | client verify 옵션 |
| `OLLAMA_FOLLOW_REDIRECTS` | `bool` | `true` | client redirect 옵션 |
| `OLLAMA_GENERATION_MODEL` | `str` | `None` | generation adapter가 사용할 모델 |
| `OLLAMA_EMBEDDING_MODEL` | `str` | `None` | embedding adapter가 사용할 모델 |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `int >= 1` | `120` | Ollama client timeout |
| `OLLAMA_MAX_RETRIES` | `int >= 0` | `2` | 설정 value로 보관되는 retry 정책 |

`OllamaConfig`는 `host`가 없으면 `ConfigError`로 변환되는 validation error를 발생시킵니다. `OllamaEmbeddingClient`와 `OllamaGenerationClient`를 직접 만들 때는 `client=`와 `model=`을 명시하며 환경 설정을 자동으로 읽지 않습니다.

```python
from rag_system_core.composition.configuration import load_service_configs

settings = load_service_configs(services={"ollama"})
assert settings.ollama is not None
print(settings.ollama.host, settings.ollama.embedding_model)
```

## 4. Milvus 설정

`MilvusConfig` import: `rag_system_core.composition.configuration.MilvusConfig`

| 환경변수 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `MILVUS_ENDPOINT` | `str` | 필수 | Milvus URI/endpoint 또는 Milvus Lite 경로 |
| `MILVUS_TOKEN` | `str` | `None` | optional token; repr에서 숨김 |
| `MILVUS_DB_NAME` | `str` | `default` | database name |
| `MILVUS_COLLECTION` | `str` | `None` | RAG adapter가 없으면 `rag_chunks`를 사용할 수 있음 |
| `MILVUS_SECURE` | `bool` | `false` | Milvus client secure 옵션 |
| `MILVUS_CONNECT_TIMEOUT_SECONDS` | `int >= 1` | `10` | 설정 value |
| `MILVUS_REQUEST_TIMEOUT_SECONDS` | `int >= 1` | `30` | Milvus client/adapter timeout |
| `MILVUS_MAX_RETRIES` | `int >= 0` | `3` | 설정 value로 보관되는 retry 정책 |

현재 canonical 이름은 `MILVUS_ENDPOINT`입니다. 이전 URI 별칭이나 nested 설정명은 이 configuration API의 이름이 아닙니다.

```python
from rag_system_core.composition.configuration import load_service_configs

settings = load_service_configs(services={"milvus"})
assert settings.milvus is not None
print(settings.milvus.endpoint, settings.milvus.collection)
```

`MilvusLiteVectorStore`를 직접 생성할 때는 `client=`, `collection_name=`, `timeout=`을 명시합니다.

## 5. ServiceConfigs와 service selection

```text
ServiceConfigs(
    common: CommonConfig,
    milvus: MilvusConfig | None = None,
    ollama: OllamaConfig | None = None,
)

ServiceSelection(service: Service, required: bool = False)
HealthcheckPolicy(on_startup: bool = False, parallel: bool = False)
RuntimePlan(
    services: tuple[ServiceSelection | Service, ...],
    one_of: tuple[tuple[Service, ...], ...] = (),
    healthcheck: HealthcheckPolicy = HealthcheckPolicy(),
)
```

지원 service enum은 `Service.MILVUS`와 `Service.OLLAMA`입니다. `Service.parse("MILVUS")`처럼 대소문자를 정규화할 수 있습니다. 알 수 없는 service, 빈 runtime plan, duplicate selection, 선택되지 않은 `one_of` service는 `ConfigError`입니다.

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
    healthcheck=HealthcheckPolicy(on_startup=True, parallel=True),
)
assert plan.selected_services == {Service.OLLAMA, Service.MILVUS}
assert plan.required_services == {Service.OLLAMA, Service.MILVUS}
```

## 6. Configuration loader

### `load_service_configs`

```text
load_service_configs(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs
```

선택된 모든 service의 설정을 process environment에서 읽습니다. `services=None`이면 `milvus`와 `ollama`를 모두 선택합니다. 선택된 service의 필수 값이 없으면 secret-safe `ConfigError`가 발생합니다.

### `load_available_service_configs`

```text
load_available_service_configs(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs
```

선택된 service 중 해당 prefix 환경변수가 하나 이상 있는 service만 로드합니다. 환경값이 전혀 없는 service는 `None`으로 남을 수 있습니다. `load_docmesh_settings`와 runtime bundle이 사용하는 기본 경로입니다.

### `load_docmesh_settings`

```text
load_docmesh_settings(
    *, services: set[str | Service] | None = None
) -> ServiceConfigs
```

`services=None`이면 `{"milvus", "ollama"}`를 선택하고 `load_available_service_configs`에 위임합니다.

```python
from rag_system_core.composition.docmesh_runtime import load_docmesh_settings

settings = load_docmesh_settings(services={"ollama", "milvus"})
if settings.ollama is not None:
    print(settings.ollama.host)
if settings.milvus is not None:
    print(settings.milvus.endpoint)
```

## 7. Runtime plan과 bundle lifecycle

```text
build_docmesh_runtime_plan(
    *,
    services: set[str | Service] | None = None,
    required: set[str | Service] | None = None,
    one_of: tuple[set[str | Service], ...] = (),
    check_on_startup: bool = False,
    parallel_healthchecks: bool = False,
) -> RuntimePlan

assemble_docmesh_services(*, plan: RuntimePlan) -> ServiceBundle
```

`build_docmesh_runtime_plan`은 service set을 정렬·정규화하고 `HealthcheckPolicy`를 포함한 `RuntimePlan`을 만듭니다. `assemble_docmesh_services`는 plan을 받아 available RAG settings를 로드하고 Ollama/Milvus raw client를 만듭니다.

```python
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)

plan = build_docmesh_runtime_plan(
    services={"ollama", "milvus"},
    required={"ollama"},
    check_on_startup=False,
)
with assemble_docmesh_services(plan=plan) as bundle:
    ollama = bundle.get_client("ollama")
    print(bundle.selected_services, ollama)
```

`ServiceBundle`이 생성한 client는 bundle 소유입니다. `with` 또는 `bundle.close()`를 사용합니다. bundle 밖에서 만든 client는 caller가 닫습니다.

## 8. DMS runtime 설정

Canonical import: `rag_system_core.composition.dms_runtime.load_dms_settings`

DMS loader가 실제로 읽는 필수 값은 다음과 같습니다.

### 공통 MinIO

| 환경변수 | 타입 | 요구 여부 | 기본값 |
|---|---|---|---|
| `DMS_MINIO_ENDPOINT` | `str` | 필수 | 없음 |
| `DMS_MINIO_ACCESS_KEY` | `str` | 필수 | 없음 |
| `DMS_MINIO_SECRET_KEY` | `str` | 필수 | 없음 |
| `DMS_MINIO_BUCKET` | `str` | 필수 | 없음 |
| `DMS_MINIO_SECURE` | `bool` | 선택 | `false` |

### Backend 선택

| 환경변수 | 의미 |
|---|---|
| `DMS_METADATA_BACKEND=sqlite` | SQLite backend를 명시 |
| `DMS_METADATA_BACKEND=postgresql` | PostgreSQL backend를 명시 |
| `DMS_CONFIGURATION_STRICT` | backend ambiguity 처리 정책 |
| `DMS_SQLITE_PATH` | SQLite backend 필수 값 |
| `DMS_POSTGRES_HOST` | PostgreSQL 선택 단서/필수 값 |
| `DMS_POSTGRES_DB` | PostgreSQL 필수 값 |
| `DMS_POSTGRES_USER` | PostgreSQL 필수 값 |
| `DMS_POSTGRES_PASSWORD` | PostgreSQL 필수 값 |
| `DMS_POSTGRES_PORT` | PostgreSQL port; 기본 `5432` |

선택 규칙:

1. `DMS_METADATA_BACKEND`가 유효한 `sqlite` 또는 `postgresql`이면 명시 선택을 사용합니다.
2. 명시값이 없고 PostgreSQL 단서가 있으면 `postgresql`을 선택합니다.
3. PostgreSQL 단서가 없고 `DMS_SQLITE_PATH`가 있으면 `sqlite`를 선택합니다.
4. 두 단서가 모두 있고 strict가 아니면 `postgresql`을 선택하고 warning을 기록합니다.
5. 두 단서가 모두 있고 `DMS_CONFIGURATION_STRICT=true`이면 invalid입니다.
6. backend와 MinIO 필수 값이 없으면 `dms.ConfigurationError`가 발생합니다.

```python
from rag_system_core.composition.dms_runtime import load_dms_settings

settings = load_dms_settings()
print(settings)
```

직접 mapping을 전달할 수도 있지만 전역 `os.environ`은 수정되지 않습니다.

```python
from rag_system_core.composition.dms_runtime import load_dms_settings

test_env = {
    "DMS_METADATA_BACKEND": "sqlite",
    "DMS_SQLITE_PATH": ":memory:",
    "DMS_MINIO_ENDPOINT": "minio:9000",
    "DMS_MINIO_ACCESS_KEY": "replace-me",
    "DMS_MINIO_SECRET_KEY": "replace-me",
    "DMS_MINIO_BUCKET": "documents",
}
settings = load_dms_settings(test_env)
```

`DmsEnvironmentDiagnosis`는 `selected_backend`, `missing_required_keys`, `unsupported_keys`, `warnings`, `valid`를 제공합니다. password·token 값 자체는 진단에 포함되지 않습니다.

## 9. DMS SDK 조립 인자

```text
create_dms_sdk_from_clients(
    *,
    engine: sqlalchemy.engine.Engine,
    minio_client: object,
    bucket_name: str,
    plan: dms.DmsAssemblyPlan | None = None,
) -> dms.DefaultDocumentManagementSDK
```

SQLAlchemy Engine과 MinIO client는 호출자가 만들고 소유합니다. 이 helper가 반환하는 DMS SDK가 주입 client의 lifecycle을 자동으로 소유하지 않는다는 점을 전제로 합니다. `DocmeshRAGServiceFactory.from_clients`가 이 helper를 사용해 만든 SDK를 Factory-owned로 등록합니다.

## 10. Configuration 오류 처리

RAG configuration validation은 `ConfigError`로 표준화됩니다.

```python
from rag_system_core.composition.configuration import ConfigError

try:
    # 필요한 환경이 없는 상태의 예시
    from rag_system_core.composition.configuration import load_service_configs
    load_service_configs(services={"ollama"})
except ConfigError as exc:
    print(exc)
    for issue in exc.issues:
        print(issue.service, issue.env_key, issue.reason)
```

`ConfigIssue`는 `service`, `env_key`, `reason`을 가지며 secret value를 저장하지 않습니다. `ConfigError.env_keys`는 실패한 환경변수 이름만 tuple로 제공합니다.

## 11. Lifecycle 요약

| 조립 경로 | 생성 자원 소유자 | 정리 |
|---|---|---|
| `assemble_docmesh_services` | 반환 `ServiceBundle` | `with bundle` 또는 `bundle.close()` |
| `DocmeshRAGServiceFactory.from_clients` | Factory는 생성한 DMS SDK만 소유 | `with factory` 또는 `factory.close()` |
| `DocmeshRAGServiceFactory.from_host_clients` | Factory는 생성한 DMS SDK만 소유 | host Engine/raw client는 caller가 정리 |
| `RAGCore(...)` 직접 생성 | 호출자 | 각 주입 adapter/store의 계약에 따름 |
| `MetadataStore(engine)` | Engine 소유자 | `MetadataStore.close()` 후 필요 시 `Engine.dispose()` |

`RAGCore`는 공통 close method를 제공하지 않습니다. `ServiceBundle`과 Factory는 close를 idempotent하게 수행합니다.

## 12. 지원하지 않는 설정 이름

다음은 현재 구현의 canonical 설정 API가 아닙니다.

- 이전 URI/nested/DSN 별칭
- library가 `.env`를 자동으로 로드한다는 가정
- 함수에 임의 SDK `**kwargs` 전달
