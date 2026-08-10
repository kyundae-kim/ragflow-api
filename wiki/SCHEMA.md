# Wiki Schema

## Domain
FastAPI 기반 RAG Flow 기능의 RESTful API 설계, 구현, 운영 지식. 검색·수집·문서 처리·임베딩·벡터 저장소·생성 응답·인증·관측성 등 API 경계와 데이터 흐름을 기록한다.

## Conventions
- File names: lowercase, hyphens, no spaces (예: `retrieval-endpoint.md`)
- Wiki page language: 기본 한국어; 코드·프로토콜명·고유명사는 원문 표기
- Every wiki page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages; every page should have at least 2 outbound links
- When updating a page, bump the `updated` date
- Add every new page to `index.md` under the correct section
- Append every action to `log.md`
- API examples should use valid HTTP method, path, request/response shape, and status code
- Distinguish normative API contracts from implementation notes and open decisions
- Record compatibility, idempotency, pagination, error format, authentication, and observability details when relevant
- On pages synthesizing 3+ sources, add `^[raw/<path>]` provenance markers to source-specific paragraphs

## Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [from taxonomy below]
sources: [raw/articles/source-name.md]
confidence: high | medium | low
contested: true
contradictions: [other-page-slug]
---
```

`confidence`, `contested`, and `contradictions` are optional. Use `confidence: medium` or `low` for decisions based on limited evidence.

## Raw Source Frontmatter
```yaml
---
source_url: https://example.com/source
ingested: YYYY-MM-DD
sha256: <sha256 of body below frontmatter>
---
```
Raw sources are immutable after ingestion.

## Tag Taxonomy
- `api`: REST resource, endpoint, schema, or contract
- `fastapi`: FastAPI framework and Python web implementation
- `rag`: retrieval-augmented generation concepts and flows
- `retrieval`: query rewriting, search, ranking, filtering, hybrid retrieval
- `ingestion`: file upload, parsing, chunking, indexing pipelines
- `embedding`: embedding models and vectorization
- `vector-store`: vector databases and index behavior
- `llm`: language models and generation
- `workflow`: orchestration of RAG Flow stages
- `data-model`: request, response, persistence, and domain models
- `auth`: authentication, authorization, and tenant isolation
- `reliability`: retries, idempotency, timeouts, and failure handling
- `observability`: logs, metrics, traces, and audit events
- `deployment`: containers, configuration, scaling, and release operations
- `comparison`: alternatives evaluated side by side

Every tag used on a page must appear above. Add new tags here before using them.

## Page Thresholds
- Create a page when a concept is central to one source or appears in 2+ sources
- Add to an existing page when a source extends an already-covered topic
- Do not create pages for passing mentions
- Split pages above roughly 200 lines
- Archive fully superseded pages under `_archive/`

## Page Types
### Entity
One page per notable component, service, model, database, or external system. Include purpose, interfaces, relationships, and sources.

### Concept
Explain an API/RAG concept, its lifecycle, constraints, and related concepts.

### Comparison
Compare implementation or architecture alternatives using explicit dimensions and a synthesis.

### Query
File substantial answers that would be expensive to recreate.

### Summary
Capture a bounded overview of a subsystem or end-to-end flow.

## Update Policy
When sources conflict:
1. Compare publication or implementation dates.
2. Preserve both claims with dates and citations when the conflict is genuine.
3. Mark the page with `contested: true` and `contradictions:`.
4. Surface the issue in lint reports rather than silently overwriting content.

## API Documentation Minimums
For endpoint pages, document:
- Method and path
- Authentication and tenant scope
- Request headers, path/query parameters, and body
- Success response and status code
- Validation and error responses
- Idempotency and pagination semantics where applicable
- Dependencies on ingestion, retrieval, generation, or storage stages
- At least 2 related wiki links
