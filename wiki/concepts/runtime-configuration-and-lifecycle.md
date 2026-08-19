---
title: RAG runtime configuration과 resource lifecycle
created: 2026-08-10
updated: 2026-08-20
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

## 설정 원천과 책임

현재 docmesh configuration은 RAG와 DMS를 모두 **명시적 객체·client 조립**으로 다룬다.

| 영역 | 현재 지원 경로 | 책임 |
|---|---|---|
| RAG runtime | `ServiceConfigs`, `ServiceBundle`, explicit client/model 인자 | 호출자가 설정과 client를 준비 |
| DMS runtime | `create_dms_sdk_from_clients(...)` | 호출자가 SQLAlchemy `Engine`, MinIO client, bucket을 준비 |
| RAG metadata | `metadata_engine` 또는 compatibility `metadata_path` | Factory/호출자 lifecycle 규칙 적용 |

`.env`, `DOCMESH_*`, `OLLAMA_*`, `MILVUS_*`, `DMS_*`를 자동으로 읽는 public loader는 현재 없다. `pydantic-settings`가 declared dependency라는 사실도 composition 경로가 process environment를 자동으로 로드한다는 뜻이 아니다. ^[raw/articles/docmesh-configuration.md]

## 명시적 RAG 설정 모델

`MilvusConfig`는 `endpoint`를 필수로 하고 token, database, collection, secure, connect/request timeout, retry 값을 가진다. `OllamaConfig`는 `host`를 필수로 하며 verify/redirect, generation·embedding model, timeout, retry 값을 가진다. `ServiceConfigs`는 두 설정을 선택적으로 묶고, `ConfigError`는 invalid configuration을 표현한다. ^[raw/articles/docmesh-configuration.md]

RAG adapter factory의 해석 우선순위는 명시적 `client`/`model`/`collection_name`/`timeout`, 그 다음 `settings`와 `bundle.configs`, 마지막으로 collection `rag_chunks`와 timeout `30.0` 기본값이다. settings나 bundle로 client를 만들 수 없으면 `RuntimeError`, 빈 model은 `ValueError`다. ^[raw/articles/docmesh-configuration.md]

## RuntimePlan과 ServiceBundle

`build_docmesh_runtime_plan`은 service selection, required services, `one_of` 제약, startup/parallel healthcheck 정책을 포함한 `RuntimePlan`을 만들며 환경을 읽지 않는다. `assemble_docmesh_services(plan=..., settings=...)`는 명시적으로 받은 `ServiceConfigs`로 Ollama/Milvus client를 조립한다. ^[raw/articles/docmesh-configuration.md]

`ServiceBundle`은 context manager가 아니다. bundle이 만든 client 중 `close()`를 제공하는 자원을 역순으로 정리하므로 `try/finally`에서 `bundle.close()`를 호출한다. bundle 밖에서 만든 raw client는 caller-owned다. ^[raw/articles/docmesh-configuration.md]

`DocmeshRAGServiceFactory.from_clients`와 `from_host_clients`는 RAG/DMS 환경변수를 읽지 않는다. dms-core v0.9 SDK에는 `close()` lifecycle이 없으므로 Factory context는 DMS SDK를 닫지 않고, host Engine·MinIO·Ollama/Milvus raw client와 주입 collaborator도 caller-owned다. Factory가 `metadata_path`로 만든 `MetadataStore`만 Factory `close()`에서 정리한다. [[dms-core]] ^[raw/articles/docmesh-api-reference.md]

`RAGCore`를 직접 생성하는 경우에도 주입된 `MetadataStore`, transport client, vector store 등의 종료는 호출자 책임이다. `metadata_engine`을 주입한 Factory 경로의 Engine/MetadataStore 역시 caller-owned다. ^[raw/articles/docmesh-configuration.md]

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
