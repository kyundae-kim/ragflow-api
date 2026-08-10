---
title: FastAPI REST adapter boundary for RAGCore
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [api, fastapi, rag, auth, data-model, reliability, observability]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
confidence: medium
---

# FastAPI REST adapter boundary for RAGCore

## 범위

`docmesh-rag-system-core`는 HTTP 서버가 아니라 동기식 Python library다. 따라서 아래 endpoint mapping은 소스에 이미 존재하는 REST 계약이 아니라, 이 wiki의 FastAPI 서비스에서 사용할 수 있는 **설계 초안**이다. 실제 status code, JSON schema, 인증 방식, 공개 필드는 애플리케이션 요구사항으로 확정해야 한다. ^[raw/articles/docmesh-api-reference.md]

| 제안 경로 | FastAPI handler가 호출할 core 작업 | 비고 |
|---|---|---|
| `POST /documents/text` | `core.ingest_text` | text와 source, idempotency 정책 |
| `POST /documents/file` | `core.ingest_file_stream` | multipart stream, UTF-8 전제 |
| `GET /documents` | `core.list_documents` | principal의 user scope |
| `GET /documents/{doc_id}` | `core.get_document` | 다른 사용자 문서는 not found 취급 가능 |
| `GET /documents/{doc_id}/chunks` | `core.list_document_chunks` | 내부 metadata 공개 여부 결정 |
| `GET /documents/{doc_id}/ingestion-progress` | `core.list_ingestion_progress` | `job_id` filter 지원 가능 |
| `DELETE /documents/{doc_id}` | `core.delete_document` | `False`의 HTTP 의미론 확정 필요 |
| `POST /query` | `core.query` | question, `top_k`, context 노출 정책 |
| `GET /health` 또는 readiness endpoint | `core.health_check` | liveness/readiness 구분은 앱 책임 |

이 매핑은 [[ragcore-facade-and-user-scope]], [[rag-ingestion-pipeline]], [[rag-query-flow]]의 core 계약을 HTTP 경계로 옮기기 위한 출발점이다.

## 인증과 tenant/user scope

인증·token 검증은 library가 하지 않는다. FastAPI dependency가 검증된 principal을 `AuthenticatedUser`로 만들고, 그 객체의 `sub`가 모든 ingestion·query·document operation에 전달되어야 한다. advanced service를 직접 노출하면 user scope 보장이 호출자 책임으로 내려가므로 기본 adapter는 `RAGCore` facade를 사용하는 편이 안전하다. ^[raw/articles/docmesh-api-reference.md]

권장 원칙:

- `sub`를 client-provided `user_id`보다 우선한다.
- path의 `doc_id`가 다른 사용자 소유이면 정보 노출을 막기 위해 not found 정책을 검토한다.
- roles/claims 기반 권한은 HTTP dependency에서 검사하고 core의 저장 scope와 분리한다.
- response에 원본 claims, access token, secret config를 넣지 않는다.

## HTTP 계약으로 확정할 항목

소스 문서에는 HTTP endpoint, JSON schema, status code가 없다. 다음은 FastAPI application이 명시해야 한다.

- request/response Pydantic model과 validation
- `201`/`202` 여부 및 동기 ingestion timeout
- `409` idempotency conflict와 재시도 semantics
- `404` document ownership 처리
- `400`/`422` 입력·UTF-8·`top_k` 오류
- vector/metadata/DMS 부분 실패의 error code와 operator recovery
- query context를 응답에 포함할지 여부
- dependency health 실패의 readiness status

DMS는 `error_descriptor()`와 `recommended_http_error()`를 제공해 canonical `code`, `category`, `retryable`을 transport-neutral하게 유지한다. 권장 projection은 access 403, validation 400, payload-too-large 413, not-found 404, conflict/deleted 409, idempotency-in-progress 425, storage/metadata/health 503 등의 status를 제공하지만, DMS 자체가 HTTP server나 exception을 생성하는 것은 아니다. [[dms-error-and-http-contract]] ^[raw/articles/dms-api-reference-v0.7.0.md]

일반 문서 응답에는 `PublicDocumentMetadata`만 사용하고 내부 `DocumentMetadata.storage_key`는 관리·복구 경계에 남겨야 한다. 목록은 opaque cursor와 동일한 status/limit을 유지하며, 본문 stream은 caller-owned input과 SDK-owned output의 close 책임을 구분해야 한다. [[dms-document-lifecycle]] ^[raw/articles/dms-api-reference-v0.7.0.md]

특히 text upload에는 `job_id`가 DMS idempotency key로 전달되지만 현재 file-stream/path adapter는 method 인자의 idempotency key를 DMS request에 전달하지 않는다는 제한이 있다. 따라서 file endpoint는 자체 idempotency layer를 두거나, 해당 library 구현을 먼저 보완해야 한다. ^[raw/articles/docmesh-api-reference.md]

## 운영 경계

설정은 `DOCMESH_`, `MILVUS_`, `OLLAMA_`, `DMS_` namespace로 나뉘고 `.env` 자동 로드는 없다. FastAPI process startup에서 configuration을 로드하고, ServiceBundle/Factory가 소유하는 자원과 host-owned 자원을 구분해 shutdown해야 한다. ^[raw/articles/docmesh-configuration.md]

health response는 `run_health_checks`의 service별 `ok`, duration, error를 기반으로 만들 수 있다. 단, liveness/readiness 경로와 외부 dependency를 어느 정도까지 required로 볼지는 서비스 운영 정책이다. ^[raw/articles/docmesh-api-reference.md]

RAGCore의 `AuthenticatedUser.sub`와 DMS `AccessContext.subject/tenant/roles`를 FastAPI dependency에서 매핑하되, RAG user scope와 DMS `DocumentAccessPolicy`를 중복·혼동하지 않는다. `access_policy`가 없는 DMS SDK는 기본적으로 제한 없이 동작하므로 production adapter에서 정책을 명시해야 한다. [[dms-access-idempotency-and-metadata-policy]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[dms-core]]
- [[dms-document-lifecycle]]
- [[dms-error-and-http-contract]]
