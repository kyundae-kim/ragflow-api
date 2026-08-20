---
title: DMS error model과 HTTP contract
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [api, reliability, observability, auth, deployment, data-model]
sources:
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
confidence: high
---

# DMS error model과 HTTP contract

## Stable error model

공개 DMS 오류는 모두 `DmsError`에서 파생되며 class-level `code`, `category`, `retryable`을 가진다. 외부 adapter는 Python exception class명이나 내부 storage 메시지보다 이 세 값을 stable branching 기준으로 사용해야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

| 오류 category/code | 권장 HTTP status | 일반 처리 |
|---|---:|---|
| access / `access_denied` | 403 | 권한 확인 |
| validation / `validation_invalid` | 400 | 요청·metadata·cursor 수정 |
| `document_too_large` | 413 | 파일 크기 제한 확인 |
| not found | 404 | document id/scope 확인 |
| conflict 또는 deleted | 409 | 충돌·삭제 상태 처리 |
| `idempotency_in_progress` | 425 | operation 조회 후 재시도 |
| storage/metadata/health | 503 | dependency 상태 확인 후 재시도 |
| configuration/consistency/reset/기타 | 500 | 운영자 조사·복구 |

`retryable` 값은 status만으로 추측하지 말고 descriptor에 보존한다. `ConsistencyError`는 무조건 blind retry하기보다 inspect/reconciliation 경로로 보내야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## Transport-neutral projection

`error_descriptor(error)`는 canonical code/category/retryability를 유지하면서 configuration/storage 계열의 내부 message를 secret-safe public message로 바꾼다. `merge_error_descriptor`는 host message, external code, retry-after만 합성하고 canonical 분류를 덮어쓰지 않는다. `recommended_http_error`는 HTTP exception 자체가 아니라 권장 status, JSON body, headers를 가진 모델을 반환한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

FastAPI exception handler는 이 projection을 이용해 공통 error body를 만들고, 내부 exception text·connection string·storage key·credential은 응답에 넣지 않아야 한다. [[fastapi-rest-adapter-boundary]]와 [[dms-document-lifecycle]]의 public/internal metadata 분리를 함께 적용한다.

## Retry와 operation 상태

`StorageError`, `MetadataStoreError`, 일부 health/reset 오류는 retryable일 수 있지만, `DuplicateDocumentError`, `IdempotencyConflictError`, validation, access denial은 요청 수정 없이는 재시도해도 해결되지 않는다. `IdempotencyInProgressError`는 같은 scope/key의 operation 상태를 확인한 후 처리해야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

Async facade에서 이미 시작된 동기 변경 작업이 취소되면 하위 작업이 즉시 중단되지 않을 수 있다. 호출자는 취소를 성공/rollback 완료로 가정하지 말고 `get_upload_operation()` 또는 metadata 조회로 최종 상태를 확인한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## Health와 observability

`check_health()`는 등록된 service check를 모두 실행해 `HealthStatus(ok, services, checked_at)`를 반환한다. 하나의 check가 실패해도 나머지를 계속 확인한다. startup `check_on_startup=True`에서 실패하면 `HealthCheckFailedError`가 발생하고 SDK-owned resource rollback을 수행한다. ^[raw/articles/dms-configuration-v0.7.0.md]

`OperationObserver`의 event에는 operation, 성공 여부, 시간, document id, error code가 포함되며 본문과 secret은 포함되지 않는다. 외부 API logging/metrics/tracing은 observer와 FastAPI middleware를 조합하되 DMS 내부 storage locator는 내부 로그에만 제한한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## 관련 페이지

- [[dms-core]]
- [[dms-access-idempotency-and-metadata-policy]]
- [[dms-document-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
- [[runtime-configuration-and-lifecycle]]
