---
title: RAG runtime configuration과 resource lifecycle
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [deployment, reliability, observability, fastapi, vector-store, embedding, llm]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
confidence: high
---

# RAG runtime configuration과 resource lifecycle

## 설정 namespace

구현은 RAG runtime과 DMS runtime 설정을 분리한다.

| 영역 | 주요 loader | prefix | 용도 |
|---|---|---|---|
| RAG runtime | `load_service_configs`, `load_available_service_configs`, `load_docmesh_settings` | `DOCMESH_`, `MILVUS_`, `OLLAMA_` | Ollama/Milvus client와 RAG adapter |
| DMS runtime | `load_dms_settings` | `DMS_` | metadata backend와 MinIO |

라이브러리는 `.env`를 자동으로 읽지 않는다. 상위 애플리케이션이나 process manager가 값을 `os.environ`에 넣어야 한다. `DMS_SQLITE_PATH`는 DMS metadata 경로이며 RAG metadata용 SQLAlchemy engine/path와 별개다. ^[raw/articles/docmesh-configuration.md]

여기서 DMS 설정 loader는 `dms-core` 자체가 아니라 `rag-system-core.composition.dms_runtime.load_dms_settings`라는 host-side composition 계층이다. `dms-core v0.7.0`의 public factory는 환경변수를 읽지 않고, host가 만든 Engine/MinIO client 또는 component를 주입받는다. `DmsServiceConfigs`도 client를 자동 생성하지 않는 immutable value object다. [[dms-core]] ^[raw/articles/dms-configuration-v0.7.0.md]

## 핵심 환경값

- Ollama: `OLLAMA_HOST` 필수, verify SSL/redirect, generation·embedding model, timeout 기본 120초, max retries 기본 2
- Milvus: `MILVUS_ENDPOINT` 필수, optional token/db/collection, secure, connect timeout 기본 10초, request timeout 기본 30초, max retries 기본 3
- 공통: `DOCMESH_ENV` 기본 `development`, `DOCMESH_SECURITY_MODE`로 production 판정 가능
- DMS MinIO: endpoint, access key, secret key, bucket 필수
- DMS backend: `DMS_METADATA_BACKEND=sqlite|postgresql` 또는 환경 단서로 선택, strict mode에서 SQLite/PostgreSQL 단서 동시 존재는 오류

secret 값은 `ConfigError`의 issue나 진단 결과에 저장하지 않고 환경변수 이름과 원인만 노출한다. ^[raw/articles/docmesh-configuration.md]

## RuntimePlan과 ServiceBundle

`build_docmesh_runtime_plan`은 service selection, required services, `one_of` 제약, startup/parallel healthcheck 정책을 포함한 `RuntimePlan`을 만든다. `assemble_docmesh_services`는 plan을 받아 available 설정을 읽고 Ollama/Milvus client를 조립한다. 반환된 `ServiceBundle`은 자신이 생성한 client의 lifecycle을 소유하므로 `with bundle:` 또는 `bundle.close()`를 사용한다. ^[raw/articles/docmesh-configuration.md]

`DocmeshRAGServiceFactory.from_clients`와 `from_host_clients`는 Factory가 만든 DMS SDK만 소유한다. host Engine, MinIO/Ollama/Milvus raw client, 주입된 RAG collaborator는 caller-owned다. 직접 생성한 `RAGCore`도 caller가 각 자원을 정리해야 한다. ^[raw/articles/docmesh-api-reference.md]

DMS SDK에 직접 주입된 client/component도 기본적으로 caller-owned다. SDK가 닫아야 하는 자원만 `ManagedResource(ownership=SDK)` 또는 `close_callbacks`로 등록하며, 등록 자원은 역순으로 정리한다. [[dms-core]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## Health와 FastAPI 운영

`run_health_checks`는 service check 예외를 `ServiceHealthStatus(ok=False, error=...)`로 변환하고, required service의 누락 check도 실패로 처리한다. 결과는 `ok`와 서비스별 duration/error를 가진 JSON-friendly 모델로 변환할 수 있다. ^[raw/articles/docmesh-api-reference.md]

FastAPI의 `/health` 또는 readiness endpoint는 이 결과를 이용해 dependency 상태를 표현할 수 있지만, 실제 경로·status code·liveness/readiness 분리는 source 문서가 정하지 않는다. HTTP 경계는 [[fastapi-rest-adapter-boundary]]에서 설계한다.

DMS `check_health()`는 `HealthStatus`를 반환하고, startup check 실패는 `HealthCheckFailedError`와 SDK-owned resource rollback으로 처리한다. FastAPI startup mandatory check와 runtime health observation을 분리하고, 외부 오류는 [[dms-error-and-http-contract]]의 stable descriptor를 사용한다. ^[raw/articles/dms-configuration-v0.7.0.md]

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[fastapi-rest-adapter-boundary]]
- [[dms-core]]
- [[dms-error-and-http-contract]]
