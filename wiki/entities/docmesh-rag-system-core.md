---
title: docmesh-rag-system-core
created: 2026-08-10
updated: 2026-08-26
type: entity
tags: [rag, api, workflow, fastapi, deployment]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
confidence: high
---

# docmesh-rag-system-core

## 개요

`docmesh-rag-system-core`는 다른 애플리케이션이 재사용할 수 있는 동기식 Python RAG 라이브러리다. 현재 공개 문서 기준 package 버전은 `0.5.0`, source revision은 `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3`, 관찰된 source branch는 `dms-core-v0.10.0`, 요구 Python 버전은 `>=3.11`이다. declared runtime dependency에는 `dms-core>=0.10.0`, `ollama>=0.6.2`, `pydantic-settings>=2.14.1`, `pymilvus[milvus-lite]>=3.0.1`이 포함된다. ^[raw/articles/docmesh-api-reference.md]

이 라이브러리는 HTTP 서버가 아니며, 환경변수만으로 완성된 `RAGCore`를 반환하는 bootstrap helper나 Ollama·metadata·vector·DMS health-check API를 제공하지 않는다. 애플리케이션이 `ServiceConfigs`, `ServiceBundle`, host-owned raw client 또는 직접 주입한 collaborator를 명시적으로 준비해야 한다. ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

핵심 공개 표면은 `sub`만을 갖는 `AuthenticatedUser`, 문서·청크·ingestion progress·query 결과 모델, `RAGCore` facade, `RAGServiceFactory`/`DocmeshRAGServiceFactory`, configuration/runtime API, storage adapter, 그리고 `rag_system_core.ports`의 protocol이다. package root와 literal `__all__`을 선언한 public submodule의 경계를 문서에 없는 내부 helper와 구분한다. ^[raw/articles/docmesh-api-reference.md]

## 주요 경계

- **Domain facade:** [[ragcore-facade-and-user-scope]]가 인증된 사용자와 RAG 작업을 연결한다.
- **Ingestion:** 문서 asset 저장, 전처리·chunking, embedding, vector 저장, metadata/progress 기록을 조정한다.
- **DMS asset layer:** 현재 package는 `dms-core>=0.10.0`을 dependency로 선언하고 `create_dms_sdk_from_clients`로 DMS SDK를 조립해 document asset 저장에 사용한다. 이 Wiki의 [[dms-core]] 페이지는 v0.7.0 문서이므로 version-specific DMS 계약과 현재 docmesh dependency 경계를 구분해야 한다. ^[raw/articles/docmesh-api-reference.md]
- **Retrieval/generation:** [[rag-query-flow]]가 질문 embedding, 사용자 범위 검색, prompt 구성, LLM 호출을 연결한다.
- **Runtime:** [[runtime-configuration-and-lifecycle]]가 Ollama·Milvus·DMS 설정, runtime plan, resource ownership, 그리고 package health API 부재를 다룬다.
- **HTTP integration:** [[fastapi-rest-adapter-boundary]]에 정리한 것처럼 REST endpoint와 HTTP 오류 의미론은 호출 애플리케이션이 정의한다.

## 저장 및 외부 서비스

내장 adapter에는 fixed-window chunker, Ollama embedding/generation client, SQLAlchemy 기반 `MetadataStore`, Milvus Lite vector store, DMS document storage가 포함된다. 현재 composition 경계는 명시적 `ServiceConfigs` 또는 host가 만든 raw client를 받아 RAG collaborator를 조립하며, Factory와 `ServiceBundle`의 정리 범위는 각각 다르다. ^[raw/articles/docmesh-api-reference.md]

`dms-core` 조립에는 host가 만든 SQLAlchemy Engine과 MinIO client가 필요하며, 현재 docmesh Factory/classmethod는 RAG/DMS 환경변수를 읽지 않는다. v0.5.0 문서는 DMS SDK와 host-owned Engine·MinIO·transport client, 주입 collaborator를 package가 닫지 않는다고 규정하며, compatibility `metadata_path`로 Factory가 직접 만든 `MetadataStore`만 Factory `close()`에서 정리한다. [[runtime-configuration-and-lifecycle]] ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

## 현재 제한

- HTTP API, PDF/OCR/parser는 제공하지 않는다.
- 입력 파일은 UTF-8 text를 전제로 한다.
- RAG/DMS 설정을 process environment에서 자동으로 읽는 public configuration loader는 제공하지 않는다.
- ingestion과 deletion은 vector store·metadata·DMS 사이의 distributed transaction이 아니다.
- `RAGCore`는 주입된 adapter/client의 lifecycle을 소유하지 않는다.
- `ServiceBundle`은 context manager가 아니며 `close()`를 명시적으로 호출해야 한다.
- 현재 package에는 Ollama·metadata·vector·DMS health-check API가 없다.
- DMS의 공개 SDK도 독립 실행형 API 서버가 아니며, HTTP 오류/status 매핑은 host가 담당한다.

이 제한은 FastAPI 서비스가 validation, multipart 처리, 예외 매핑, timeout, 인증, 관측성을 별도로 설계해야 함을 뜻한다. ^[raw/articles/docmesh-api-reference.md]

## 이 repository의 host 구현

`ragflow-api v0.1.0`은 FastAPI를 API 계층으로 두고 `RAGCore` facade만 application use-case 경계로 호출한다. Business request의 `X-User-Id` header를 `AuthenticatedUser.sub`로 직접 변환하며, 이 API 자체는 identity provider/token 인증을 수행하지 않는다. HTTP DTO는 DMS asset reference, prompt와 allowlist 밖 chunk metadata를 숨긴다. [[fastapi-rest-adapter-boundary]]

composition root는 host-owned SQLAlchemy Engine와 MinIO client, Ollama/Milvus bundle을 조립하고 FastAPI lifespan에서 종료 순서를 관리한다. 이 구현은 library가 HTTP와 adapter lifecycle을 소유하지 않는다는 원래 경계를 유지한다. [[runtime-configuration-and-lifecycle]]

## v0.5.0 host compatibility

현재 host repository는 `rag-system-core>=0.5.0`을 선언하지만 `ragflow/runtime.py`에서 legacy `required`, `check_on_startup`, `parallel_healthchecks` 인자를 runtime plan과 Factory에 전달하고, `ragflow/api/health.py`에서 `core.health_check()`를 호출한다. 이 이름들은 v0.5.0 공개 문서에 없으므로 package 문서와 host 코드 사이의 통합 gap을 별도로 추적해야 한다. [[docmesh-v0-5-host-compatibility]]

## 관련 페이지

- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
- [[dms-document-lifecycle]]
- [[dms-error-and-http-contract]]
