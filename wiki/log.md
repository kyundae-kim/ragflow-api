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

## [2026-08-10] update | FastAPI API 계층 구현 계약 확정
- Pages updated:
  - `concepts/fastapi-rest-adapter-boundary.md`
  - `entities/docmesh-rag-system-core.md`
  - `index.md`
- Recorded implemented endpoint/status contracts, strict Keycloak access-token/HTTPS policy, public DTO filtering, UTF-8/whitespace and upload/body limits, DMS error projection, runtime composition and reverse-order shutdown.
- Applied independent-review follow-ups: documented public FastAPI discovery routes, aligned every protected operation's OpenAPI errors—including query `400`/`413`—and framework parser errors with runtime bodies, made explicit runtime mappings drive DocMesh loaders deterministically, and added deterministic MinIO HTTP-pool cleanup.
- Remaining decisions retained explicitly: file idempotency, pagination, role authorization, proactive Keycloak readiness, and partial-failure recovery.

## [2026-08-20] ingest | docmesh-rag-system-core v0.4.0 공개 Wiki 문서
- Sources refreshed after live-source drift from the 2026-08-10 captures:
  - `raw/articles/docmesh-api-reference.md`
  - `raw/articles/docmesh-configuration.md`
  - `raw/articles/docmesh-examples.md`
- Current source hashes:
  - API Reference: `3c82155cb4aafe6ec87ea9da10e1e08931cd8cef487e77d6507871f648572e6f`
  - Configuration: `77b5cdf6aab72c708be695c774f30789d2344011bbab02fc895027ca93e5ce4b`
  - Examples: `cb950fa6b08a8010dd1f882d6de7829c28747b0c186b75f065da271cb10cd67c`
- Pages updated:
  - `entities/docmesh-rag-system-core.md`
  - `entities/dms-core.md`
  - `concepts/runtime-configuration-and-lifecycle.md`
  - `concepts/ragcore-facade-and-user-scope.md`
  - `concepts/rag-ingestion-pipeline.md`
  - `concepts/fastapi-rest-adapter-boundary.md`
  - `index.md`
- Source scope: package `0.4.0` public API, explicit configuration/client assembly, `AuthenticatedUser(sub)` user boundary, ServiceBundle/Factory lifecycle, DMS `>=0.9.0` dependency, and runnable examples.
