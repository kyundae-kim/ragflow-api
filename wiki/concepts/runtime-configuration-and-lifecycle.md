---
title: RAG runtime configuration과 resource lifecycle
created: 2026-08-10
updated: 2026-08-26
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

현재 package 기준은 `rag-system-core` v0.5.0, source revision `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3`, `dms-core>=0.10.0`이다. 이 페이지는 package의 explicit configuration contract와 host가 책임져야 할 lifecycle을 분리해 기록한다. ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

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

`build_docmesh_runtime_plan`은 `services`와 `one_of` 제약으로 `RuntimePlan`을 만들며 환경을 읽지 않는다. `services=None`이면 `milvus`와 `ollama`를 모두 선택한다. 현재 v0.5.0 signature에는 `required`, `check_on_startup`, `parallel_healthchecks` 인자가 없다. `assemble_docmesh_services(plan=..., settings=...)`는 명시적으로 받은 `ServiceConfigs`로 Ollama/Milvus client를 조립하고, 조립 중 실패하면 이미 만든 client를 정리한 뒤 예외를 전달한다. ^[raw/articles/docmesh-configuration.md]

`ServiceBundle`은 context manager가 아니다. bundle이 만든 client 중 `close()`를 제공하는 자원을 역순으로 정리하므로 `try/finally`에서 `bundle.close()`를 호출한다. bundle 밖에서 만든 raw client는 caller-owned다. ^[raw/articles/docmesh-configuration.md]

`DocmeshRAGServiceFactory.from_clients`와 `from_host_clients`는 RAG/DMS 환경변수를 읽지 않는다. v0.5.0 문서의 Factory context는 DMS SDK, host Engine·MinIO·Ollama/Milvus raw client와 주입 collaborator를 닫지 않는다. Factory가 `metadata_path`로 만든 `MetadataStore`만 Factory `close()`에서 정리하고, `metadata_engine`으로 만든 store는 caller-owned다. [[dms-core]] ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

`RAGCore`를 직접 생성하는 경우에도 주입된 `MetadataStore`, transport client, vector store 등의 종료는 호출자 책임이다. `metadata_engine`을 주입한 Factory 경로의 Engine/MetadataStore 역시 caller-owned다. ^[raw/articles/docmesh-configuration.md]

## Health와 FastAPI 운영

현재 v0.5.0 `rag-system-core`에는 `RAGCore.health_check()`, `run_health_checks`, startup check option 또는 health policy API가 없다. FastAPI의 `/health`와 readiness는 host-owned dependency check로 구현해야 하며, 실제 경로·status code·liveness/readiness 분리는 source 문서가 정하지 않는다. HTTP 경계는 [[fastapi-rest-adapter-boundary]]에서 설계한다. ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

이 Wiki의 [[dms-core]] 및 [[dms-error-and-http-contract]]는 별도 versioned DMS v0.7.0 문서의 `check_health()`와 startup health semantics를 기록한다. 이를 현재 `rag-system-core` v0.5.0 public API가 제공하는 health surface로 일반화하지 않는다. ^[raw/articles/dms-configuration-v0.7.0.md]

## Host compatibility watch

현재 repository의 `ragflow/runtime.py`는 package 문서에 없는 runtime plan·Factory health 인자를 전달하고, `ragflow/api/health.py`는 package 문서에 없는 `core.health_check()`를 호출한다. v0.5.0 package와 host의 실제 조립 계약을 맞추는 작업은 [[docmesh-v0-5-host-compatibility]]에서 추적한다.

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[fastapi-rest-adapter-boundary]]
- [[dms-core]]
- [[dms-error-and-http-contract]]
