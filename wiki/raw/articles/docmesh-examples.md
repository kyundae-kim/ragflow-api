---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Examples
ingested: 2026-08-10
sha256: bf00b5f4f94f4a74da212af4fbb525eea417cda700fa2fead58601bc382dae28
---
# 사용 예제

이 문서는 현재 `rag-system-core` 공개 import를 사용해 복사·조정할 수 있는 예제 모음입니다. 모든 예제는 현재 `RAGCore` dependency-injection API와 composition API를 기준으로 합니다.

- API 계약: [API-Reference](API-Reference)
- 환경변수·기본값: [Configuration](Configuration)
- 권장 첫 실행: §1의 외부 서비스 없는 직접 조립

> 현재 버전은 환경변수만으로 완성된 `RAGCore`를 반환하는 단일 bootstrap helper를 제공하지 않습니다. 외부 설정과 collaborator를 명시적으로 조립해야 합니다.

## 1. 외부 서비스 없는 첫 성공: 직접 `RAGCore` 조립

다음 예제는 Ollama, Milvus, MinIO 없이 공개 port 계약과 SQLite metadata store를 사용합니다. `sqlalchemy`는 DMS/runtime dependency set을 통해 설치됩니다.

```python
from sqlalchemy import create_engine

from rag_system_core import AuthenticatedUser, RAGCore
from rag_system_core.adapters import FixedWindowChunker
from rag_system_core.composition import run_health_checks
from rag_system_core.storage import MetadataStore
from rag_system_core.types import ChunkRecord, DocumentRecord


class LocalEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


class LocalGenerationClient:
    def generate(self, prompt: str) -> str:
        question = prompt.rsplit("[User Query]", 1)[-1].strip()
        return f"local answer: {question}"


class MemoryVectorStore:
    def __init__(self) -> None:
        self.rows: list[ChunkRecord] = []
        self.next_id = 1

    def add(self, chunks: list[ChunkRecord], vectors: list[list[float]]) -> list[str]:
        del vectors
        ids: list[str] = []
        for chunk in chunks:
            chunk_id = str(self.next_id)
            self.next_id += 1
            ids.append(chunk_id)
            self.rows.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    doc_id=chunk.doc_id,
                    user_id=chunk.user_id,
                    content=chunk.content,
                    metadata=dict(chunk.metadata),
                )
            )
        return ids

    def search(
        self,
        *,
        user_id: str,
        query_vector: list[float],
        top_k: int,
    ) -> list[ChunkRecord]:
        del query_vector
        return [row for row in self.rows if row.user_id == user_id][:top_k]

    def delete_document(self, doc_id: str) -> None:
        self.rows = [row for row in self.rows if row.doc_id != doc_id]

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        ids = set(chunk_ids)
        self.rows = [row for row in self.rows if row.chunk_id not in ids]


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store_text(
        self,
        *,
        doc_id: str,
        user_id: str,
        text: str,
        source: str,
        idempotency_key: str,
    ) -> str:
        del user_id, source, idempotency_key
        self.values[doc_id] = text
        return doc_id

    def store_file_stream(
        self,
        *,
        doc_id: str,
        user_id: str,
        file_stream,
        size: int,
        source: str,
        idempotency_key: str,
    ) -> str:
        del user_id, size, source, idempotency_key
        self.values[doc_id] = file_stream.read().decode("utf-8")
        return doc_id

    def store_file_path(
        self,
        *,
        doc_id: str,
        user_id: str,
        file_path,
        source: str | None = None,
        idempotency_key: str,
    ) -> str:
        del user_id, source, idempotency_key
        self.values[doc_id] = file_path.read_text(encoding="utf-8")
        return doc_id

    def load(self, document: DocumentRecord) -> str | None:
        return self.values.get(document.asset_reference or document.doc_id)

    def delete(self, document: DocumentRecord) -> None:
        self.values.pop(document.asset_reference or document.doc_id, None)


user = AuthenticatedUser(
    sub="user-a",
    preferred_username="user-a",
    email=None,
    given_name=None,
    family_name=None,
    name=None,
    realm_roles=[],
    client_roles={},
    claims={},
)

metadata_engine = create_engine("sqlite+pysqlite:///:memory:")
metadata_store = MetadataStore(metadata_engine)
core = RAGCore(
    embedding_client=LocalEmbeddingClient(),
    generation_client=LocalGenerationClient(),
    vector_store=MemoryVectorStore(),
    metadata_store=metadata_store,
    document_storage=MemoryDocumentStorage(),
    chunker=FixedWindowChunker(chunk_size=512, chunk_overlap=64),
    health_check_runner=run_health_checks,
)

try:
    ingested = core.ingest_text(
        user=user,
        text="RAG 코어는 사용자 스코프를 적용합니다.",
        source="guide.txt",
    )
    result = core.query(user=user, question="어떤 스코프를 적용하나요?", top_k=3)
    assert ingested.chunk_count > 0
    print(result.answer)
    print([chunk.content for chunk in result.context_chunks])
finally:
    metadata_store.close()
```

이 경로의 resource owner는 호출자입니다. `RAGCore`는 주입된 client/store를 닫지 않습니다.

## 2. 사용자 스코프와 문서 lifecycle

§1의 `core`와 `user`를 유지한 상태에서 다음 API를 호출할 수 있습니다.

```python
from io import BytesIO
from pathlib import Path

stream_result = core.ingest_file_stream(
    user=user,
    file_stream=BytesIO("stream 문서".encode("utf-8")),
    source="stream.txt",
)

sample_path = Path("sample.txt")
sample_path.write_text("path 문서", encoding="utf-8")
path_result = core.ingest_file_path(
    user=user,
    file_path=sample_path,
)

for document in core.list_documents(user=user):
    print(document.doc_id, document.source, document.asset_reference)
    print(core.list_document_chunks(document.doc_id, user=user))
    print(core.list_ingestion_progress(document.doc_id, user=user))

assert core.get_document(stream_result.doc_id, user=user) is not None
assert core.delete_document(stream_result.doc_id, user=user) is True
assert core.get_document(stream_result.doc_id, user=user) is None
sample_path.unlink()
```

- stream `source`는 필수입니다.
- path `source`를 생략하면 파일명이 사용됩니다.
- stream/path bytes는 UTF-8이어야 합니다.
- 다른 사용자의 `doc_id`는 조회되지 않고 삭제도 `False`입니다.

## 3. Factory를 사용한 RAGCore 조립

`DocmeshRAGServiceFactory`는 설정 객체를 보관하지 않습니다. 이미 만든 RAG collaborator와 DMS용 Engine/MinIO client를 받아 DMS SDK를 생성합니다.

```python
from sqlalchemy import create_engine

from rag_system_core import DocmeshRAGServiceFactory

# DMS metadata용 Engine과 RAG metadata용 Engine은 별도입니다.
dms_engine = create_engine("sqlite+pysqlite:///:memory:")
rag_metadata_engine = create_engine("sqlite+pysqlite:///:memory:")

# embedding_client, generation_client, vector_store는 애플리케이션이 만든
# EmbeddingClient/GenerationClient/VectorStore 구현체라고 가정합니다.
with DocmeshRAGServiceFactory.from_clients(
    engine=dms_engine,
    minio_client=minio_client,
    bucket_name="documents",
    embedding_client=embedding_client,
    generation_client=generation_client,
    vector_store=vector_store,
    metadata_engine=rag_metadata_engine,
    check_on_startup=False,
) as factory:
    core = factory.create_rag_core()
    result = core.ingest_text(user=user, text="factory path", source="factory.txt")
    print(result.doc_id)

# from_clients가 생성한 DMS SDK만 Factory가 닫습니다.
# dms_engine, rag_metadata_engine, minio_client와 주입 collaborator는 caller-owned입니다.
```

`minio_client`, `embedding_client`, `generation_client`, `vector_store`, `user`는 앞선 예제 또는 애플리케이션 구현으로 준비해야 합니다. `metadata_engine` 없이 `create_rag_core()`를 호출하면 `metadata_path is required when metadata_engine is not provided` 오류가 발생합니다.

## 4. Host-owned raw client에서 시작하기

Ollama, Milvus, MinIO, DMS metadata backend가 준비된 환경에서 사용합니다. 이 예제는 실제 외부 서비스 연결이 필요하므로 실행 전 [Configuration](Configuration)을 확인합니다.

```python
from minio import Minio
from ollama import Client as OllamaClient
from pymilvus import MilvusClient
from sqlalchemy import create_engine

from rag_system_core import AuthenticatedUser, DocmeshRAGServiceFactory

# 외부 서비스에 맞게 endpoint와 credential을 변경합니다.
dms_engine = create_engine("sqlite+pysqlite:///./data/dms.db")
rag_metadata_engine = create_engine("sqlite+pysqlite:///./data/rag-metadata.db")
minio_client = Minio(
    "minio:9000",
    access_key="replace-me",
    secret_key="replace-me",
    secure=False,
)
ollama_client = OllamaClient(host="http://ollama:11434")
milvus_client = MilvusClient(uri="./data/rag-vectors.db")

user = AuthenticatedUser(
    sub="user-a",
    preferred_username=None,
    email=None,
    given_name=None,
    family_name=None,
    name=None,
    realm_roles=[],
    client_roles={},
    claims={},
)

with DocmeshRAGServiceFactory.from_host_clients(
    engine=dms_engine,
    metadata_engine=rag_metadata_engine,
    minio_client=minio_client,
    bucket_name="documents",
    ollama_client=ollama_client,
    milvus_client=milvus_client,
    embedding_model="bge-m3",
    generation_model="gpt-oss:20b",
    collection_name="rag_chunks",
    timeout=30.0,
    check_on_startup=False,
) as factory:
    core = factory.create_rag_core()
    health = core.health_check()
    print(health.to_dict() if hasattr(health, "to_dict") else health)
    print(core.ingest_text(user=user, text="host client path", source="host.txt"))

# host-owned Engine, transport client, and injected adapter lifecycle은 caller가 정리합니다.
```

`from_host_clients`는 RAG 환경변수를 읽지 않습니다. Ollama/Milvus model·collection·timeout은 인자로 전달됩니다.

## 5. Runtime plan과 ServiceBundle

환경 기반으로 Ollama/Milvus client를 조립해야 할 때 사용합니다. DMS SDK는 이 bundle에 포함되지 않습니다.

```python
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)

plan = build_docmesh_runtime_plan(
    services={"ollama", "milvus"},
    required={"ollama", "milvus"},
    check_on_startup=True,
    parallel_healthchecks=True,
)

with assemble_docmesh_services(plan=plan) as bundle:
    embedding = create_rag_embedding_client(
        bundle=bundle,
        model="bge-m3",
    )
    generation = create_rag_generation_client(
        bundle=bundle,
        model="gpt-oss:20b",
    )
    vectors = create_rag_vector_store(
        bundle=bundle,
        collection_name="rag_chunks",
        timeout=30.0,
    )
    print(embedding.embed(["bundle example"]))
    print(generation.generate("Say bundle example"))
    vectors.check()
```

`assemble_docmesh_services`는 `plan`에 선택된 RAG service 설정을 process environment에서 읽습니다. 반환된 `ServiceBundle`이 생성 client lifecycle을 소유합니다.

## 6. Settings, DMS 설정, health 집계

```python
from rag_system_core.composition import (
    load_docmesh_settings,
    run_health_checks,
)
from rag_system_core.composition.configuration import (
    load_available_service_configs,
    load_service_configs,
)
from rag_system_core.composition.dms_runtime import load_dms_settings

# RAG service 설정은 MILVUS_* / OLLAMA_* / DOCMESH_*를 사용합니다.
rag_settings = load_docmesh_settings(services={"ollama", "milvus"})
available = load_available_service_configs(services={"ollama", "milvus"})
strict_rag = load_service_configs(services={"ollama"})

# DMS 설정은 DMS_* namespace를 사용합니다.
dms_settings = load_dms_settings()
print(rag_settings.common.env, available.common.env, strict_rag.common.env)
print(dms_settings)

result = run_health_checks(
    {
        "metadata": lambda: None,
        "custom": lambda: None,
    },
    required_services={"metadata", "custom"},
    parallel=False,
)
assert result.ok
print(result.to_dict())
```

`load_dms_settings()`는 필요한 DMS 환경이 없으면 `dms.ConfigurationError`를 발생시킵니다. `run_health_checks`는 check 예외를 `ServiceHealthStatus(ok=False, error=...)`로 변환합니다.

## 7. Concrete adapter 직접 사용

### Ollama adapter

```python
from ollama import Client as OllamaClient

from rag_system_core import OllamaEmbeddingClient, OllamaGenerationClient

client = OllamaClient(host="http://ollama:11434")
embedding = OllamaEmbeddingClient(client=client, model="bge-m3")
generation = OllamaGenerationClient(client=client, model="gpt-oss:20b")

vectors = embedding.embed(["hello"])
answer = generation.generate("Say hello")
print(len(vectors), answer)
```

주입 Ollama client는 embedding에 `embed(model=..., input=...)`, generation에 `chat(model=..., messages=...)`를 제공해야 합니다.

### MetadataStore

```python
from sqlalchemy import create_engine

from rag_system_core.storage import MetadataStore

engine = create_engine("sqlite+pysqlite:///./data/rag-metadata.db")
store = MetadataStore(engine)
try:
    store.check()
finally:
    store.close()
```

`MetadataStore`는 SQLAlchemy `Engine`을 받고 `documents`, `chunks`, `ingestion_progress` 테이블을 초기화합니다. 파일 경로를 직접 받지 않습니다.

### Milvus vector store

```python
from pymilvus import MilvusClient

from rag_system_core.storage import MilvusLiteVectorStore

client = MilvusClient(uri="./data/rag-vectors.db")
store = MilvusLiteVectorStore(
    client=client,
    collection_name="rag_chunks",
    timeout=30.0,
)
store.check()
```

## 8. Advanced domain service

일반 애플리케이션은 `RAGCore`를 사용합니다. 이미 `user_id`를 해석했고 ingestion/retrieval/generation 단계를 직접 조정해야 할 때만 advanced service를 사용합니다.

```python
from rag_system_core.domain.core import GenerationService, RetrievalService

retrieval = RetrievalService(
    embedding_client=embedding_client,
    vector_store=vector_store,
)
generation = GenerationService(
    generation_client,
    system_prompt="주어진 context만 사용하세요.",
)

chunks = retrieval.search(user_id="user-a", question="alpha", top_k=3)
result = generation.generate(question="alpha", context_chunks=chunks)
print(result.answer)
```

이 경로는 `AuthenticatedUser`를 받지 않으며 user-scope·인증 보장은 호출자 책임입니다.

## 9. 테스트

저장소 전체 테스트:

```bash
uv run --locked pytest -q
```

Wiki 예제의 `python` fenced code는 현재 public import path와 signature 기준으로 작성되었습니다. 외부 서비스가 필요한 예제는 서비스 연결 상태와 [Configuration](Configuration)을 먼저 확인하십시오.
