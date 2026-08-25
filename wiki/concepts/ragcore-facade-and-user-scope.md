---
title: RAGCore facade와 사용자 scope
created: 2026-08-10
updated: 2026-08-26
type: concept
tags: [rag, workflow, auth, data-model, reliability]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
confidence: high
---

# RAGCore facade와 사용자 scope

현재 API 기준은 `rag-system-core` v0.5.0, source revision `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3`이다. ^[raw/articles/docmesh-api-reference.md]

## 정의

`RAGCore`는 embedding client, generation client, vector store, metadata store, document storage, chunker를 모두 주입받는 user-aware facade다. 모든 의존성이 생성자에 필요하며 `RAGCore`가 주입된 collaborator의 lifecycle을 소유하지 않는다. `RAGCore` 자체에는 `close()`나 health-check runner가 없다. ^[raw/articles/docmesh-api-reference.md]

인증과 token 검증은 호출 애플리케이션의 책임이다. 검증된 `AuthenticatedUser.sub`가 내부 `user_id`로 사용되므로, FastAPI 계층은 인증 결과를 이 값으로 안전하게 변환해 core에 전달해야 한다. ^[raw/articles/docmesh-api-reference.md]

## 제공 작업

| 영역 | `RAGCore` 메서드 | 결과 |
|---|---|---|
| Text ingestion | `ingest_text(user, text, source)` | `IngestResult` |
| Stream/file ingestion | `ingest_file_stream`, `ingest_file_path` | `IngestResult` |
| Query | `query(user, question, top_k=3)` | `QueryResult` |
| Documents | `list_documents`, `get_document` | user-scoped document records |
| Chunks/progress | `list_document_chunks`, `list_ingestion_progress` | user-scoped records |
| Step status | `get_ingestion_step_statuses` | 정의된 pipeline의 final status map |
| Deletion | `delete_document` | 대상이 있으면 `True`, 없으면 `False` |

문서 조회·청크 조회·progress 조회·삭제는 `user_id`를 적용한다. 다른 사용자의 문서는 조회되지 않으며, 삭제 대상이 아니면 `False`를 반환한다. ^[raw/articles/docmesh-api-reference.md]

## 사용자 경계

현재 public API의 `AuthenticatedUser`는 `sub: str`만을 받는 간결한 user model이다. 이 값이 RAG 저장·검색 scope의 resolved `user_id`가 된다. advanced domain service는 이미 해석된 `user_id`를 직접 받으며 인증이나 scope 보장을 수행하지 않으므로 일반 애플리케이션에서는 `RAGCore` 사용이 안전한 기본 경로다. ^[raw/articles/docmesh-api-reference.md]

FastAPI adapter는 요청 시작 시 인증된 principal을 만들고, 모든 문서·검색·삭제 호출에 동일한 `sub`를 연결해야 한다. 이 매핑과 endpoint 형태는 [[fastapi-rest-adapter-boundary]]에서 별도 설계 대상으로 취급한다.

DMS SDK는 자체 인증 helper를 제공하지 않고 host가 `AccessContext(subject, tenant, roles)`와 `DocumentAccessPolicy`를 주입해야 한다. 따라서 `AuthenticatedUser.sub`를 RAG `user_id`와 DMS `subject`에 매핑할 수는 있지만, tenant/role authorization은 DMS policy와 FastAPI dependency에서 별도로 명시한다. [[dms-access-idempotency-and-metadata-policy]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## Lifecycle과 실패 의미

`RAGCore` 자체에는 공통 `close()`가 없다. 직접 조립하는 경우 SQLAlchemy `MetadataStore`, transport client, vector store 등의 종료 책임은 호출자에게 있다. `ServiceBundle`은 context manager가 아니며 bundle이 만든 client 중 `close()`를 제공하는 자원만 역순으로 정리한다. Factory는 `metadata_path`로 직접 만든 `MetadataStore`만 추적·정리하고, v0.5.0 문서의 DMS SDK, host Engine/MinIO/raw transport client, 주입 collaborator는 닫지 않는다. ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/docmesh-configuration.md]

문서 삭제는 vector store → document asset → metadata store 순서로 진행되며, 중간 실패 뒤 이미 정리된 artifact가 남을 수 있고 distributed rollback을 보장하지 않는다. 따라서 REST layer는 부분 실패를 500/503으로 무조건 숨기기보다 operation 상태와 재시도 정책을 명시해야 한다. ^[raw/articles/docmesh-api-reference.md]

DMS 내부 document 삭제도 `deleting` 상태 표시 → object 삭제 → metadata 후속 처리 순서이며, object/metadata 불일치는 `ConsistencyError`와 reconciliation 후보가 될 수 있다. RAG vector와 DMS asset을 함께 다루는 endpoint는 두 시스템의 복구 상태를 하나의 성공 응답으로 단정하지 않아야 한다. [[dms-document-lifecycle]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
- [[docmesh-v0-5-host-compatibility]]
- [[dms-core]]
- [[dms-error-and-http-contract]]
