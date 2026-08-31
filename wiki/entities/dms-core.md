---
title: dms-core v0.7.0 Document Management SDK
created: 2026-08-10
updated: 2026-08-26
type: entity
tags: [api, ingestion, data-model, auth, reliability, observability, deployment]
sources:
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
confidence: high
---

# dms-core v0.7.0 Document Management SDK

## 개요

`dms-core` `0.7.0`은 Python 애플리케이션에 주입되어 문서 업로드·조회·목록·본문 스트리밍·삭제·복구·health를 제공하는 Document Management SDK다. 권장 import 경계는 `dms` package root이며, SDK 자체는 독립 실행형 HTTP 서버가 아니다. ^[raw/articles/dms-api-reference-v0.7.0.md]

DMS는 SQLAlchemy `Engine`, MinIO client, 또는 완성된 metadata/object/operation store를 환경변수로 만들지 않는다. host가 client나 component를 생성한 뒤 factory에 주입해야 한다. ^[raw/articles/dms-configuration-v0.7.0.md]

## 공개 조립 표면

- `create_sdk_from_clients(...)` / `create_async_sdk_from_clients(...)`
- `create_sdk_from_components(...)` / `create_async_sdk_from_components(...)`
- `DefaultDocumentManagementSDK`와 `AsyncDocumentManagementSDK`
- 공유 SDK에 operation context를 적용하는 `ScopedDocumentManagementSDK`
- `DocumentWriter`, `DocumentReader`, `DocumentLister`, `DocumentDeleter`, `DataResetter`, `DocumentHealth` protocol
- 업로드·metadata·pagination·stream·삭제·복구·health 결과 모델
- `DmsError` hierarchy와 transport-neutral HTTP projection

sync facade와 async facade는 같은 기능 계약을 제공한다. Async facade는 동기 저장소 작업을 worker thread에서 실행하며, 이미 시작한 변경 작업의 취소를 rollback 완료로 간주하지 않는다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## docmesh-rag-system-core와의 관계

현재 `docmesh-rag-system-core` v0.5.0 문서는 `dms-core>=0.10.0`을 선언하고 `DocmeshRAGServiceFactory`가 `create_dms_sdk_from_clients`를 이용해 DMS SDK를 조립한다고 기록한다. 이 페이지 자체는 dms-core v0.7.0 문서이므로 v0.10.0 dependency의 세부 API를 대체하지 않는다. v0.5.0 Factory context도 DMS SDK, host가 제공한 SQLAlchemy Engine·MinIO client·raw transport와 주입 collaborator를 닫지 않으며, Factory가 compatibility path로 만든 metadata store만 추적한다. ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

RAG의 사용자 scope와 DMS의 접근 정책은 같은 계층이 아니다. RAGCore는 `AuthenticatedUser.sub`를 `user_id`로 적용하고, DMS는 host가 `AccessContext`와 `DocumentAccessPolicy`를 정의해 작업을 제한한다. 이 두 경계를 FastAPI adapter에서 함께 연결해야 한다. [[ragcore-facade-and-user-scope]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 운영 경계

기본 주입 자원은 SDK가 닫지 않는다. `ManagedResource(ownership=SDK)` 또는 `close_callbacks`로 명시적으로 등록한 자원만 SDK가 역순으로 정리한다. `close()`와 `aclose()`는 반복 호출에 안전하며 cleanup 오류는 `ResourceCleanupError`에 모인다. ^[raw/articles/dms-api-reference-v0.7.0.md]

DMS는 public metadata에서 내부 `storage_key`를 제거하고, 일반 API와 관리·복구 API를 분리한다. FastAPI 외부 응답은 [[dms-error-and-http-contract]]와 [[fastapi-rest-adapter-boundary]]의 원칙을 따라야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## 관련 페이지

- [[dms-document-lifecycle]]
- [[dms-access-idempotency-and-metadata-policy]]
- [[dms-error-and-http-contract]]
- [[docmesh-rag-system-core]]
- [[rag-ingestion-pipeline]]
- [[runtime-configuration-and-lifecycle]]
- [[docmesh-v0-5-host-compatibility]]
