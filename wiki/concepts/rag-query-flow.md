---
title: RAG query flow
created: 2026-08-10
updated: 2026-08-10
type: concept
tags: [rag, retrieval, embedding, llm, vector-store, workflow, api]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
confidence: high
---

# RAG query flow

## 정의

`RAGCore.query(user, question, top_k=3)`는 질문을 embedding하고, `user_id` scope로 vector 검색을 수행한 뒤, 검색된 context를 prompt에 넣어 generation client를 호출한다. 반환되는 `QueryResult`에는 `answer`, 실제 LLM에 전달한 `prompt`, `context_chunks`가 포함된다. ^[raw/articles/docmesh-api-reference.md]

흐름은 다음과 같다.

```text
AuthenticatedUser.sub
        ↓
question ──> query embedding ──> VectorStore.search(user_id, vector, top_k)
                                      ↓
                              retrieved ChunkRecord
                                      ↓
                     [System Prompt] + [Retrieved Context] + [User Query]
                                      ↓
                            GenerationClient.generate(prompt)
                                      ↓
                                QueryResult
```

## Protocol 계약

- `EmbeddingClient.embed(texts: list[str]) -> list[list[float]]`
- `VectorStore.search(*, user_id, query_vector, top_k) -> list[ChunkRecord]`
- `GenerationClient.generate(prompt: str) -> str`

기본 generation system prompt는 `You are a helpful RAG assistant. Answer only from the retrieved context.`다. `GenerationService`를 직접 쓰면 system prompt를 바꿀 수 있지만, advanced service는 인증과 user scope를 수행하지 않는다. ^[raw/articles/docmesh-api-reference.md]

## HTTP 변환 시 의미

소스 문서는 HTTP endpoint나 JSON schema를 정의하지 않는다. 따라서 FastAPI 계층은 질문, `top_k`, 인증 principal, 응답의 context 노출 여부를 자체적으로 결정해야 한다. 제안된 adapter 경계는 [[fastapi-rest-adapter-boundary]]에 기록한다.

특히 `context_chunks`는 내부 metadata나 source 정보를 포함할 수 있으므로 public response에 그대로 노출할지 결정해야 한다. 사용자 scope는 [[ragcore-facade-and-user-scope]]의 `AuthenticatedUser.sub`에서 시작해야 한다.

## 품질과 실패 경계

검색 결과가 없을 때의 답변, `top_k <= 0` 처리, embedding 차원 오류, vector store timeout, LLM transport/malformed response, prompt 길이 제한은 이 library의 HTTP 계약으로 정의되어 있지 않다. FastAPI service는 각 경우의 status code, error body, timeout, retry 정책을 별도로 정해야 한다.

외부 Ollama/Milvus를 사용하는 경우 runtime configuration과 health 결과는 [[runtime-configuration-and-lifecycle]]을 따른다. 실행 예제의 직접 조립 경로는 local collaborator로 query를 끝까지 검증하는 최소 사례를 제공한다. ^[raw/articles/docmesh-examples.md]

## 관련 페이지

- [[docmesh-rag-system-core]]
- [[ragcore-facade-and-user-scope]]
- [[rag-ingestion-pipeline]]
- [[runtime-configuration-and-lifecycle]]
- [[fastapi-rest-adapter-boundary]]
