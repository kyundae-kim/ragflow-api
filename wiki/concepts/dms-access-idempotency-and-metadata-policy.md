---
title: DMS access context, idempotency와 metadata policy
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [auth, reliability, data-model, api, observability]
sources:
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
  - raw/articles/docmesh-api-reference.md
confidence: high
---

# DMS access context, idempotency와 metadata policy

## 접근 context

`AccessContext`는 `subject`, `tenant`, `roles`를 표현하고, `DocumentAccessPolicy`는 operation·context·public metadata를 받아 허용 여부를 결정한다. DMS SDK는 특정 user/tenant/role 체계를 해석하지 않으며, `access_policy`가 없으면 기존 호환 동작처럼 접근을 제한하지 않는다. ^[raw/articles/dms-api-reference-v0.7.0.md]

`DmsOperationContext`와 `sdk.scoped(context)`는 shared SDK를 변경하지 않는 immutable facade다. context에서 `created_by`, `idempotency_scope`, `audit_actor`, 기본 metadata를 주입하고 작업 호출의 명시값을 우선한다. 목록에도 허용된 범위에 대한 cursor/page semantics가 유지된다. ^[raw/articles/dms-api-reference-v0.7.0.md]

FastAPI adapter에서는 [[ragcore-facade-and-user-scope]]의 `AuthenticatedUser.sub`와 tenant/roles를 `AccessContext`로 매핑하되, RAG `user_id` scope와 DMS access policy를 별도 검증 층으로 유지한다.

## Idempotent upload

bytes upload의 idempotency를 사용하려면 persistent `operation_store`, non-empty `idempotency_scope`, `idempotency_key`가 필요하다.

| 상황 | 결과 |
|---|---|
| 같은 scope/key + 같은 fingerprint | 기존 결과 replay, `created=False` |
| 같은 scope/key + 다른 fingerprint | `IdempotencyConflictError` |
| 기존 작업이 pending | `IdempotencyInProgressError` |
| scope가 없거나 operation 조회 조건이 불완전 | `ValidationError` 또는 not found |

operation의 외부 상태는 `pending`, `succeeded`, `failed`이며 fingerprint 자체는 외부 결과에 노출하지 않는다. ^[raw/articles/dms-api-reference-v0.7.0.md]

이는 [[rag-ingestion-pipeline]]에서 기록한 `job_id`와 DMS idempotency 전달 차이를 설계할 때 중요하다. docmesh adapter의 text upload와 file/stream path 경로가 동일한 idempotency semantics를 보장하는지는 adapter 구현을 별도로 확인해야 한다. ^[raw/articles/docmesh-api-reference.md]

## Metadata validation

기본 `DefaultMetadataPolicy`는 JSON-serializable mapping, 문자열 key, 최대 serialized byte(기본 16,384), 최대 depth(기본 8), credential 성격의 key를 검사한다. `password`, `secret`, `token`, `api_key`, `authorization`, `credential` 등은 차단 대상이며, 실패는 storage 쓰기 전에 `ValidationError` 계열로 반환된다. ^[raw/articles/dms-api-reference-v0.7.0.md]

`StructuredMetadataValidator`는 schema version을 먼저 확인하고 parser/projector를 수행한 뒤 공통 policy를 적용한다. field-level 오류는 `MetadataValidationIssue`와 `MetadataSchemaValidationError`로 표현한다. validator는 입력 mapping을 변형하지 않고 독립된 normalized mapping을 만든다. ^[raw/articles/dms-configuration-v0.7.0.md]

## 관찰과 감사

`OperationObserver`는 성공·실패 `OperationEvent`를 받고, `recovery_audit_hook`은 복구 시도별 `RecoveryAuditEvent`를 받는다. observer/hook 자체의 실패는 원래 작업 결과를 바꾸지 않고 로그로 남긴다. 이벤트에는 본문, credential, 내부 storage key를 포함하지 않는다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## 관련 페이지

- [[dms-core]]
- [[dms-document-lifecycle]]
- [[dms-error-and-http-contract]]
- [[ragcore-facade-and-user-scope]]
- [[fastapi-rest-adapter-boundary]]
