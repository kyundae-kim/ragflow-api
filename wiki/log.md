# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, update, query, lint, create, archive, delete

## [2026-08-10] create | Wiki initialized
- Domain: FastAPI 기반 RAG Flow 기능의 RESTful API 설계, 구현, 운영 지식
- Structure created with `SCHEMA.md`, `index.md`, `log.md`
- Source directories created under `raw/`

## [2026-08-10] ingest | docmesh-rag-system-core 공개 Wiki 문서
- Sources captured:
  - `raw/articles/docmesh-api-reference.md`
  - `raw/articles/docmesh-configuration.md`
  - `raw/articles/docmesh-examples.md`
- Pages created:
  - `entities/docmesh-rag-system-core.md`
  - `concepts/fastapi-rest-adapter-boundary.md`
  - `concepts/rag-ingestion-pipeline.md`
  - `concepts/rag-query-flow.md`
  - `concepts/ragcore-facade-and-user-scope.md`
  - `concepts/runtime-configuration-and-lifecycle.md`
- Source scope: `rag-system-core` v0.3.0 공개 API, 설정, 실행 예제 및 FastAPI 통합 경계 synthesis

## [2026-08-10] ingest | dms-core v0.7.0 공개 Wiki 문서
- Sources captured:
  - `raw/articles/dms-api-reference-v0.7.0.md`
  - `raw/articles/dms-configuration-v0.7.0.md`
  - `raw/articles/dms-examples-v0.7.0.md`
- Pages created:
  - `entities/dms-core.md`
  - `concepts/dms-access-idempotency-and-metadata-policy.md`
  - `concepts/dms-document-lifecycle.md`
  - `concepts/dms-error-and-http-contract.md`
- Pages updated:
  - `entities/docmesh-rag-system-core.md`
  - `concepts/fastapi-rest-adapter-boundary.md`
  - `concepts/rag-ingestion-pipeline.md`
  - `concepts/ragcore-facade-and-user-scope.md`
  - `concepts/runtime-configuration-and-lifecycle.md`
- Source scope: `dms-core` v0.7.0 공개 API, 설정, lifecycle, recovery, metadata policy 및 FastAPI HTTP error projection
