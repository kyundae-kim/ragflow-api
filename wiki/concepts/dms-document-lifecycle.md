---
title: DMS document lifecycle와 consistency recovery
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [ingestion, data-model, reliability, api, observability, workflow]
sources:
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-examples.md
confidence: high
---

# DMS document lifecycle와 consistency recovery

## 업로드 입력과 결과

DMS SDK는 bytes, file path, 정확한 크기를 선언한 동기 binary stream을 업로드 입력으로 받는다. 빈 content, 잘못된 filename/content type, stream 선언 크기와 실제 읽은 크기의 불일치는 storage에 쓰기 전 또는 rollback 후 `ValidationError`가 된다. unknown-size stream, async input stream, 요청별 checksum/idempotency/chunk size는 현재 stream API의 지원 범위가 아니다. ^[raw/articles/dms-api-reference-v0.7.0.md]

`UploadDocumentRequest`는 content, filename, content type, 선택 document id, metadata, created_by, checksum, idempotency scope/key를 가진다. checksum을 생략하면 SHA-256을 계산하며, `max_file_size`를 설정하면 bytes/file/known-size stream에 같은 양수 byte 한도를 적용한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

본문 object를 먼저 저장하고 metadata를 저장한다. metadata 저장 실패 시 object rollback을 시도하며 rollback까지 실패하면 `ConsistencyError`가 된다. 같은 `document_id`는 duplicate 오류이고, 같은 idempotency 요청의 replay는 `created=False` 결과를 반환한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## 상태와 공개 metadata

문서 상태는 `uploaded`, `available`, `deleting`, `deleted`, `failed`다. 새 업로드의 정상 상태는 `available`이며, 일반 metadata/list는 `deleting`과 `deleted`를 숨긴다. ^[raw/articles/dms-api-reference-v0.7.0.md]

`PublicDocumentMetadata`는 filename, content type, size, status, timestamps, checksum, created_by, extra metadata를 제공하지만 내부 `storage_key`는 포함하지 않는다. `DocumentMetadata`와 `get_internal_document_metadata()`는 관리·복구 전용이며 외부 일반 응답에 사용하지 않는다. [[dms-access-idempotency-and-metadata-policy]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 본문 반환과 목록

본문은 전체 `DocumentContent`, sync `DocumentContentStream`, async `AsyncDocumentContentStream`으로 반환할 수 있다. SDK가 연 source stream은 닫지만 caller가 제공한 sink는 닫지 않는다. stream iterator는 정상 소진·읽기 오류·조기 종료에서 close 책임을 명시해야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

목록은 `created_at`, `document_id` 내림차순 cursor pagination을 사용한다. `limit`은 1~1000이고 cursor는 opaque 값이다. 다음 요청은 이전 cursor와 동일한 status/limit을 사용해야 하며, cursor를 변조하거나 조건을 바꾸면 `ValidationError`다. [[fastapi-rest-adapter-boundary]] ^[raw/articles/dms-api-reference-v0.7.0.md]

## 삭제와 전체 초기화

`delete_document(hard_delete=False)`와 `soft_delete_document()`는 논리 삭제를 수행하고, `hard_delete_document()`는 완전 삭제를 수행한다. 삭제 시 metadata를 `deleting`으로 표시하고 object를 삭제한 뒤 `deleted`로 표시하거나 hard delete한다. object 삭제 실패는 `failed` 상태와 `StorageError`, object 삭제 후 metadata 후속 실패는 `ConsistencyError`가 될 수 있다. ^[raw/articles/dms-api-reference-v0.7.0.md]

`clear_all_data()`와 `initialize_for_data_load()`는 개별 document 삭제와 다른 전역 관리 작업이다. metadata, `documents/` prefix object, upload operation record를 대상으로 하며 orphan object도 정리한다. 여러 store 중 하나가 실패해도 나머지를 시도하고 `DataResetError`에 부분 결과와 failed store를 담는다. 분산 transaction을 주장하지 않으며, `initialize_for_data_load()`는 빈 상태에서도 멱등적이다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## 검사와 복구

`inspect_document()`는 metadata가 없어도 검사 결과를 반환할 수 있으며, metadata/object 존재 여부와 issue를 표현한다. `FAILED` 또는 `DELETING` 후보를 조회하고, `reconcile_document`, dry-run 기반 `ReconciliationPlan`, plan 재검사 후 실행으로 복구한다. orphan object purge에는 public metadata가 아니라 호출자가 별도로 제공한 정확한 `storage_key`가 필요하다. ^[raw/articles/dms-api-reference-v0.7.0.md]

이 recovery 경계는 [[rag-ingestion-pipeline]]에서 설명한 RAG vector·metadata·DMS multi-store 흐름을 보완한다. DMS 내부 recovery와 RAG 전체 pipeline recovery를 하나의 atomic transaction으로 간주해서는 안 된다.

## 관련 페이지

- [[dms-core]]
- [[dms-access-idempotency-and-metadata-policy]]
- [[dms-error-and-http-contract]]
- [[rag-ingestion-pipeline]]
- [[fastapi-rest-adapter-boundary]]
