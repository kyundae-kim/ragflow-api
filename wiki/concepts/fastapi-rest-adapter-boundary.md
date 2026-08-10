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
confidence: high
---

# FastAPI REST adapter boundary for RAGCore

## 범위

`docmesh-rag-system-core`는 HTTP 서버가 아니라 동기식 Python library다. 아래 mapping은 core 자체 계약이 아니라 이 repository의 `ragflow-api v0.1.0` FastAPI host가 확정해 구현한 REST 계약이다. route는 동기 `def` handler로 실행되어 `RAGCore`의 blocking 작업을 FastAPI thread pool에 위임한다. ^[raw/articles/docmesh-api-reference.md]

| 구현 경로 | FastAPI handler가 호출할 core 작업 | 비고 |
|---|---|---|
| `POST /documents/text` | `core.ingest_text` | text/source 검증 후 동기 `201` |
| `POST /documents/file` | `core.ingest_file_stream` | multipart UTF-8, size/body limit 후 동기 `201` |
| `GET /documents` | `core.list_documents` | principal의 user scope |
| `GET /documents/{doc_id}` | `core.get_document` | 다른 사용자 문서는 not found로 conceal |
| `GET /documents/{doc_id}/chunks` | `core.list_document_chunks` | metadata는 `source` allowlist만 공개 |
| `GET /documents/{doc_id}/ingestion-progress` | `core.list_ingestion_progress` | `job_id` filter 지원 가능 |
| `DELETE /documents/{doc_id}` | `core.delete_document` | `False`는 concealment `404` |
| `POST /query` | `core.query` | question/`top_k` 검증, filtered context 공개 |
| `GET /health/live` | 없음 | 외부 dependency를 호출하지 않는 liveness |
| `GET /health/ready` | `core.health_check` | 실패 세부정보를 숨기고 `503` 반환 |

이 매핑은 [[ragcore-facade-and-user-scope]], [[rag-ingestion-pipeline]], [[rag-query-flow]]의 core 계약을 HTTP 경계로 옮기기 위한 출발점이다.

## 인증과 tenant/user scope

인증·token 검증은 library가 하지 않는다. FastAPI dependency가 검증된 principal을 `AuthenticatedUser`로 만들고, 그 객체의 `sub`가 모든 ingestion·query·document operation에 전달되어야 한다. advanced service를 직접 노출하면 user scope 보장이 호출자 책임으로 내려가므로 기본 adapter는 `RAGCore` facade를 사용하는 편이 안전하다. ^[raw/articles/docmesh-api-reference.md]

권장 원칙:

- `sub`를 client-provided `user_id`보다 우선한다.
- path의 `doc_id`가 다른 사용자 소유이면 정보 노출을 막기 위해 not found 정책을 검토한다.
- roles/claims 기반 권한은 HTTP dependency에서 검사하고 core의 저장 scope와 분리한다.
- response에 원본 claims, access token, secret config를 넣지 않는다.

## 구현된 HTTP 계약

소스 문서에는 HTTP endpoint, JSON schema, status code가 없으므로 FastAPI application이 다음 의미론을 소유한다.

- text/file ingestion은 동기 완료 후 `201`, deletion 성공은 body 없는 `204`다.
- 다른 사용자의 문서와 없는 문서는 모두 stable `document_not_found` `404`로 처리한다.
- Pydantic 입력 오류와 빈/whitespace-only upload는 `422`, UTF-8 decode 실패와 multipart boundary 같은 framework parsing 오류는 stable envelope의 `400`이다.
- 파일은 기본 10 MiB로 제한하고, ASGI middleware가 여기에 multipart overhead 1 MiB를 더한 전체 request body를 parsing 전에 streaming 제한한다. 초과는 `413`이다.
- query는 `top_k`를 1–100으로 제한하고 answer와 user-scoped context chunks를 반환하지만 내부 prompt, `user_id`, DMS asset reference는 공개하지 않는다.
- chunk metadata는 allowlist의 `source`만 공개해 향후 adapter가 추가하는 token/storage metadata가 transport DTO로 새지 않게 한다.
- DMS 오류는 `recommended_http_error()`의 status/body/header projection을 사용하고, 예상하지 못한 오류는 내부 exception 문자열 없는 `500`으로 바꾼다.
- OpenAPI의 protected route `401`/`4xx`/`5xx` response는 runtime과 같은 `ApiErrorResponse` schema를 선언한다. FastAPI의 `/openapi.json`, `/docs`, `/redoc`과 `/health/*`는 public이고 business route만 Bearer authentication을 요구한다.
- readiness dependency 실패와 Keycloak JWKS 연결 실패는 secret-safe `503`; invalid/expired/audience/issuer/access-token-type 불일치 token은 `401`이다.

DMS는 `error_descriptor()`와 `recommended_http_error()`를 제공해 canonical `code`, `category`, `retryable`을 transport-neutral하게 유지한다. 권장 projection은 access 403, validation 400, payload-too-large 413, not-found 404, conflict/deleted 409, idempotency-in-progress 425, storage/metadata/health 503 등의 status를 제공하지만, DMS 자체가 HTTP server나 exception을 생성하는 것은 아니다. [[dms-error-and-http-contract]] ^[raw/articles/dms-api-reference-v0.7.0.md]

일반 문서 응답에는 `PublicDocumentMetadata`만 사용하고 내부 `DocumentMetadata.storage_key`는 관리·복구 경계에 남겨야 한다. 목록은 opaque cursor와 동일한 status/limit을 유지하며, 본문 stream은 caller-owned input과 SDK-owned output의 close 책임을 구분해야 한다. [[dms-document-lifecycle]] ^[raw/articles/dms-api-reference-v0.7.0.md]

특히 text upload에는 `job_id`가 DMS idempotency key로 전달되지만 현재 file-stream/path adapter는 method 인자의 idempotency key를 DMS request에 전달하지 않는다는 제한이 있다. 따라서 file endpoint는 자체 idempotency layer를 두거나, 해당 library 구현을 먼저 보완해야 한다. ^[raw/articles/docmesh-api-reference.md]

## 운영 경계

설정은 `DOCMESH_`, `MILVUS_`, `OLLAMA_`, `DMS_` namespace로 나뉘고 `.env` 자동 로드는 없다. FastAPI process startup에서 configuration을 로드하고, 명시적 runtime mapping을 사용하면 process의 DocMesh namespace를 assembly 동안 격리한 뒤 복원한다. ServiceBundle/Factory가 소유하는 자원과 host-owned 자원을 구분해 shutdown해야 한다. ^[raw/articles/docmesh-configuration.md]

현재 composition root는 Keycloak issuer/audience/expiration과 payload `typ=Bearer`를 확인하는 RS256 JWKS 검증기를 만들고, loopback 이외의 identity URL에는 기본적으로 HTTPS를 요구한다. 이어 Ollama/Milvus bundle, DMS SQLAlchemy Engine와 MinIO client, 별도 RAG metadata Engine, `DocmeshRAGServiceFactory`, `RAGCore`를 조립한다. FastAPI lifespan 종료 시 metadata store, factory, host-owned MinIO HTTP pool, metadata/DMS Engine, bundle 순으로 역정리한다. SQLite `:memory:`는 `StaticPool`과 `check_same_thread=False`로 구성해 synchronous route worker thread 사이에서 같은 database를 공유한다. [[runtime-configuration-and-lifecycle]]

health response는 `run_health_checks`의 service별 `ok`, duration, error를 기반으로 만들 수 있다. 단, liveness/readiness 경로와 외부 dependency를 어느 정도까지 required로 볼지는 서비스 운영 정책이다. ^[raw/articles/docmesh-api-reference.md]

RAGCore의 `AuthenticatedUser.sub`와 DMS `AccessContext.subject/tenant/roles`를 FastAPI dependency에서 매핑하되, RAG user scope와 DMS `DocumentAccessPolicy`를 중복·혼동하지 않는다. `access_policy`가 없는 DMS SDK는 기본적으로 제한 없이 동작하므로 production adapter에서 정책을 명시해야 한다. [[dms-access-idempotency-and-metadata-policy]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 남은 경계 결정

- file ingestion의 caller-provided idempotency key는 아직 HTTP 계약에 없다.
- document list pagination과 opaque cursor는 core facade가 지원할 때 추가해야 한다.
- role/claim 기반 endpoint authorization은 아직 없고 모든 인증 사용자가 같은 use case 집합을 가진다.
- readiness는 RAG/DMS dependency를 검사하지만 Keycloak 자체 proactive health check는 하지 않는다.
- distributed transaction이 없으므로 partial ingestion/deletion recovery와 operator reconciliation은 여전히 별도 운영 절차가 필요하다.

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[dms-core]]
- [[dms-document-lifecycle]]
- [[dms-error-and-http-contract]]
