# Wiki Index

> FastAPI 기반 RAG Flow 기능의 RESTful API 지식 카탈로그.
> 이 파일을 먼저 읽고 관련 페이지를 찾는다.
> Last updated: 2026-08-26 | Total pages: 11

## Entities
<!-- Alphabetical within section -->

- [[dms-core]] — host가 client/component를 주입해 사용하는 dms-core v0.7.0 문서 관리 SDK.
- [[docmesh-rag-system-core]] — v0.5.0 기준 FastAPI 애플리케이션에 주입·조립해 사용하는 동기식 RAG core library.

## Concepts
<!-- RAG flow, API contract, ingestion, retrieval, generation, and operations concepts -->

- [[dms-access-idempotency-and-metadata-policy]] — DMS 접근 context, 멱등 업로드, metadata 검증과 관찰 policy.
- [[dms-document-lifecycle]] — DMS 업로드·공개 metadata·stream·삭제·reset·reconciliation lifecycle.
- [[dms-error-and-http-contract]] — stable DMS error code/category/retryability와 HTTP projection.
- [[fastapi-rest-adapter-boundary]] — RAGCore를 application 계층으로 호출하는 FastAPI REST·직접 user scope·오류·lifecycle 계약.
- [[rag-ingestion-pipeline]] — asset 저장부터 chunking, embedding, vector/metadata 기록까지의 ingestion 흐름.
- [[rag-query-flow]] — 질문 embedding, user-scoped retrieval, prompt 구성, generation 흐름.
- [[ragcore-facade-and-user-scope]] — RAGCore dependency injection과 AuthenticatedUser.sub 기반 scope.
- [[runtime-configuration-and-lifecycle]] — 명시적 RAG/DMS 설정 객체, runtime plan, health API 부재, 자원 소유권.

## Comparisons
<!-- Architecture and technology comparisons -->

- [[docmesh-v0-5-host-compatibility]] — rag-system-core v0.5.0 문서 계약과 현재 ragflow-api host 호출 사이의 compatibility gap.

## Queries
<!-- Filed research answers and design decisions -->

## Summaries
<!-- Bounded subsystem and end-to-end flow overviews -->
