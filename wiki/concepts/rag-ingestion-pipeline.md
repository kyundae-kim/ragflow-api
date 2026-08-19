---
title: RAG ingestion pipeline
created: 2026-08-10
updated: 2026-08-20
type: concept
tags: [rag, ingestion, embedding, vector-store, data-model, reliability, workflow]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
  - raw/articles/dms-api-reference-v0.7.0.md
  - raw/articles/dms-configuration-v0.7.0.md
  - raw/articles/dms-examples-v0.7.0.md
confidence: high
---

# RAG ingestion pipeline

## 흐름

`RAGCore` ingestion은 대체로 다음 순서로 동작한다.

1. 입력 text·stream·path를 사용자와 source 정보에 연결한다.
2. asset을 document storage에 저장한다.
3. text를 전처리하고 chunking한다.
4. 모든 chunk를 embedding client에 batch로 전달한다.
5. vector store에 chunk/vector를 저장한다.
6. metadata와 ingestion progress를 기록한다.

현재 progress step 순서는 `load`, `preprocess`, `chunking`, `embedding`, `vector_store`, `chunk_persistence`다. ^[raw/articles/docmesh-api-reference.md]

## 입력 계약

- `ingest_text`는 text를 `strip()`한 뒤 저장한다.
- file stream/path 입력은 UTF-8 text로 decode한다.
- stream upload에는 비어 있지 않은 `source`가 필요하다.
- path upload의 source 기본값은 파일명이다.
- 결과는 `job_id`, `doc_id`, `user_id`, source, 생성시각, `chunk_count`를 가진 `IngestResult`다.

직접 조립 예제는 외부 Ollama·Milvus·MinIO 없이 local embedding/generation, memory vector store, SQLite metadata store를 사용해 첫 성공 경로를 구성한다. ^[raw/articles/docmesh-examples.md]

## Collaborator protocol

| 단계 | protocol | 핵심 계약 |
|---|---|---|
| Chunking | `Chunker` | `chunk(text) -> list[str]`; 빈 결과는 `ValueError` |
| Embedding | `EmbeddingClient` | 입력 순서에 대응하는 vector 목록 반환 |
| Vector 저장 | `VectorStore` | chunk와 같은 수의 opaque ID 반환 |
| Metadata | `MetadataRepository` | document/chunk/progress 기록 및 user-scoped 조회 |
| Asset 저장 | `DocumentAssetStorage` | opaque asset reference 반환 |

`VectorStore.search`와 metadata 조회·삭제는 `user_id`를 적용해야 한다. `DocumentAssetStorage`의 stream은 호출자가 소유하며 adapter가 임의로 닫지 않는다. ^[raw/articles/docmesh-api-reference.md]

## DMS asset upload contract

docmesh의 `DmsDocumentStorage`는 DMS document id, asset reference, text/file stream/path upload, content load, soft delete를 RAG ingestion에 연결한다. 현재 `rag-system-core` package는 `dms-core>=0.9.0`을 dependency로 선언하지만, 이 Wiki의 세부 upload 입력·stream 계약은 versioned `dms-core v0.7.0` source에 근거하므로 버전 경계를 구분해 읽어야 한다. 해당 DMS 문서는 bytes, file path, 정확한 크기의 sync binary stream을 지원하고 unknown-size/async input stream은 지원하지 않는다고 기록한다. 따라서 FastAPI multipart 계층은 stream size와 close ownership을 명시적으로 다뤄야 한다. [[dms-core]] ^[raw/articles/docmesh-api-reference.md] ^[raw/articles/dms-api-reference-v0.7.0.md]

현재 docmesh API reference에는 `DmsDocumentStorage`의 `check()`가 공개되어 있지 않다. 따라서 health 집계가 asset adapter까지 포함한다고 가정하지 말고 실제 collaborator가 제공하는 check surface를 기준으로 readiness 범위를 정해야 한다. ^[raw/articles/docmesh-api-reference.md]

DMS upload는 object를 먼저 저장한 뒤 metadata를 기록하고, metadata 오류 시 object rollback을 시도한다. rollback까지 실패하면 `ConsistencyError`가 되며, DMS reset/reconciliation도 분산 transaction을 제공하지 않는다. RAG의 vector·metadata·DMS asset pipeline은 [[dms-document-lifecycle]]의 내부 복구 경계와 별도로 운영 recovery를 가져야 한다. ^[raw/articles/dms-api-reference-v0.7.0.md]

## Idempotency와 보상 동작

Text upload는 생성된 `job_id`를 DMS idempotency key로 전달한다. 반면 현재 file-stream/path upload adapter는 method 인자로 받은 idempotency key를 DMS request에 전달하지 않는다. 이 차이는 FastAPI multipart endpoint에서 재시도 정책을 설계할 때 반드시 노출해야 하는 구현 제한이다. ^[raw/articles/docmesh-api-reference.md]

DMS `0.7.0`의 영속 idempotency는 bytes upload에 operation store, non-empty scope, key가 있어야 하며 동일 fingerprint replay만 `created=False`로 처리한다. 그러므로 docmesh의 text/file/stream 경로가 동일한 멱등 semantics를 제공한다고 가정하지 말고 adapter별 계약을 확인해야 한다. [[dms-access-idempotency-and-metadata-policy]] ^[raw/articles/dms-api-reference-v0.7.0.md]

vector ID 수가 입력 chunk 수와 다르거나 metadata chunk 저장이 실패하면 생성된 vector 삭제를 시도한다. 그러나 전체 ingestion은 distributed transaction이 아니므로 DMS asset, vector, metadata 중 일부만 남을 가능성이 있다. ^[raw/articles/docmesh-api-reference.md]

## REST adapter 고려사항

[[fastapi-rest-adapter-boundary]]에서는 이 pipeline을 text upload와 file upload endpoint로 노출할 때의 요청 검증, idempotency header, 동기 처리 timeout, 오류 매핑을 별도 계약으로 정의해야 한다. 핵심 facade와 사용자 경계는 [[ragcore-facade-and-user-scope]], runtime resource는 [[runtime-configuration-and-lifecycle]]을 참조한다.

## 관련 페이지

- [[ragcore-facade-and-user-scope]]
- [[rag-query-flow]]
- [[runtime-configuration-and-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
- [[dms-core]]
- [[dms-document-lifecycle]]
- [[dms-access-idempotency-and-metadata-policy]]
