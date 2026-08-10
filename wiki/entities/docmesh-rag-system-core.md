---
title: docmesh-rag-system-core
created: 2026-08-10
updated: 2026-08-10
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

`docmesh-rag-system-core`는 다른 애플리케이션이 재사용할 수 있는 동기식 Python RAG 라이브러리다. 기준 버전은 `0.3.0`, 요구 Python 버전은 `>=3.11`, DMS 의존성은 `dms-core v0.7.0`이다. 이 라이브러리는 HTTP 서버가 아니며, 완성된 `RAGCore`를 환경변수만으로 자동 생성하는 단일 bootstrap helper도 제공하지 않는다. 애플리케이션이 collaborator와 설정을 명시적으로 조립해야 한다. ^[raw/articles/docmesh-api-reference.md]

핵심 공개 표면은 사용자 인증 결과를 표현하는 `AuthenticatedUser`, 문서·청크·ingestion progress·query 결과 모델, `RAGCore` facade, `RAGServiceFactory`/`DocmeshRAGServiceFactory`, 그리고 `rag_system_core.ports`의 protocol이다. ^[raw/articles/docmesh-api-reference.md]

## 주요 경계

- **Domain facade:** [[ragcore-facade-and-user-scope]]가 인증된 사용자와 RAG 작업을 연결한다.
- **Ingestion:** 문서 asset 저장, 전처리·chunking, embedding, vector 저장, metadata/progress 기록을 조정한다.
- **DMS asset layer:** [[dms-core]]의 `dms-core v0.7.0` SDK가 document object, metadata, upload operation, 삭제·복구를 담당한다.
- **Retrieval/generation:** [[rag-query-flow]]가 질문 embedding, 사용자 범위 검색, prompt 구성, LLM 호출을 연결한다.
- **Runtime:** [[runtime-configuration-and-lifecycle]]가 Ollama·Milvus·DMS 설정, health check, resource ownership을 다룬다.
- **HTTP integration:** [[fastapi-rest-adapter-boundary]]에 정리한 것처럼 REST endpoint와 HTTP 오류 의미론은 호출 애플리케이션이 정의한다.

## 저장 및 외부 서비스

내장 adapter에는 fixed-window chunker, Ollama embedding/generation client, SQLAlchemy 기반 `MetadataStore`, Milvus Lite vector store, DMS document storage가 포함된다. Factory 및 runtime bundle 경로에서는 RAG collaborator와 DMS SDK를 조립할 수 있지만, 생성 자원의 소유권은 조립 경로별로 다르다. ^[raw/articles/docmesh-api-reference.md]

`dms-core`는 host가 만든 SQLAlchemy Engine/MinIO client 또는 storage component를 주입받으며 환경변수로 client를 자동 생성하지 않는다. `DocmeshRAGServiceFactory`는 생성한 DMS SDK만 소유하고 host-owned client는 caller 책임으로 남긴다. [[runtime-configuration-and-lifecycle]] ^[raw/articles/dms-configuration-v0.7.0.md]

## 현재 제한

- HTTP API, PDF/OCR/parser는 제공하지 않는다.
- 입력 파일은 UTF-8 text를 전제로 한다.
- ingestion과 deletion은 vector store·metadata·DMS 사이의 distributed transaction이 아니다.
- `RAGCore`는 주입된 adapter/client의 lifecycle을 소유하지 않는다.
- DMS의 공개 SDK도 독립 실행형 API 서버가 아니며, HTTP 오류/status 매핑은 host가 담당한다.

이 제한은 FastAPI 서비스가 validation, multipart 처리, 예외 매핑, timeout, 인증, 관측성을 별도로 설계해야 함을 뜻한다. ^[raw/articles/docmesh-api-reference.md]

## 이 repository의 host 구현

`ragflow-api v0.1.0`은 FastAPI를 API 계층으로 두고 `RAGCore` facade만 application use-case 경계로 호출한다. Keycloak JWT의 검증된 `sub`를 `AuthenticatedUser`로 만들며, user scope를 client 입력으로 받지 않는다. HTTP DTO는 `user_id`, DMS asset reference, prompt와 allowlist 밖 chunk metadata를 숨긴다. [[fastapi-rest-adapter-boundary]]

composition root는 host-owned SQLAlchemy Engine와 MinIO client, Ollama/Milvus bundle을 조립하고 FastAPI lifespan에서 종료 순서를 관리한다. 이 구현은 library가 HTTP와 adapter lifecycle을 소유하지 않는다는 원래 경계를 유지한다. [[runtime-configuration-and-lifecycle]]

## 관련 페이지

- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
- [[dms-document-lifecycle]]
- [[dms-error-and-http-contract]]
