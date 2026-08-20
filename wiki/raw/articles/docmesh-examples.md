---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Examples
ingested: 2026-08-20
sha256: cb950fa6b08a8010dd1f882d6de7829c28747b0c186b75f065da271cb10cd67c
---
# 사용 예제

이 문서는 현재 `rag-system-core` 공개 import를 사용해 복사·조정할 수 있는 예제 모음입니다. 모든 예제는 현재 `RAGCore` dependency-injection API와 composition API를 기준으로 합니다.

- API 계약: [API-Reference](API-Reference)
- 설정·lifecycle: [Configuration](Configuration)
- 권장 첫 실행: §1의 외부 서비스 없는 직접 조립

> 현재 구현은 환경변수만으로 완성된 `RAGCore`를 반환하는 bootstrap helper를 제공하지 않습니다. 외부 설정과 collaborator를 명시적으로 조립해야 합니다.

## 1. 외부 서비스 없는 첫 성공: 직접 `RAGCore` 조립

다음 예제는 Ollama, Milvus, MinIO 없이 public port 계약과 SQLite metadata store를 사용합니다.

```python
from pathlib import Path

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
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
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
        file_path: Path,
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


user = AuthenticatedUser(sub="user-a")
metadata_store = MetadataStore(create_engine("sqlite+pysqlite:///:memory:"))
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

`RAGCore`는 주입된 client/store의 lifecycle을 소유하지 않습니다. 직접 조립한 `MetadataStore`와 raw client는 호출자가 정리합니다. §2를 같은 프로세스에서 이어서 실행하려면 위 `finally`의 `metadata_store.close()`를 §2의 마지막으로 옮기고, 각 section을 독립 실행할 때는 현재 위치를 유지하십시오.

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
path_result = core.ingest_file_path(user=user, file_path=sample_path)

for document in core.list_documents(user=user):
    print(document.doc_id, document.source, document.asset_reference)
    print(core.list_document_chunks(document.doc_id, user=user))
    print(core.list_ingestion_progress(document.doc_id, user=user))

assert core.get_document(stream_result.doc_id, user=user) is not None
assert core.delete_document(stream_result.doc_id, user=user) is True
assert core.get_document(stream_result.doc_id, user=user) is None
sample_path.unlink()
```

- stream `source`는 필수이며 없거나 공백이면 `ValueError`입니다.
- path `source`를 생략하면 파일명이 사용됩니다.
- stream/path bytes는 UTF-8이어야 합니다.
- 다른 사용자의 `doc_id`는 조회되지 않으며 삭제 결과는 `False`입니다.

## 3. 이미 만든 collaborator로 Factory 조립

다음은 `from_clients`의 signature와 ownership을 보여주는 조립 예제입니다. `minio_client`, RAG collaborator, `user`는 호출 애플리케이션이 준비해야 합니다.

```python
from sqlalchemy import create_engine

from rag_system_core import DocmeshRAGServiceFactory


dms_engine = create_engine("sqlite+pysqlite:///:memory:")
rag_metadata_engine = create_engine("sqlite+pysqlite:///:memory:")

# embedding_client, generation_client, vector_store, minio_client, user를 준비했다고 가정합니다.
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
```

`metadata_engine`은 classmethod signature에서는 optional이지만 `create_rag_core()`의 정상 경로에는 필요합니다. 없으면 `create_metadata_store(metadata_path=...)`를 별도로 호출해야 합니다.

주의: dms-core v0.9 SDK에는 `close()` lifecycle이 없습니다. Factory context는 생성한 DMS SDK, host Engine, MinIO client, 주입된 RAG collaborator를 닫지 않습니다. `check_on_startup`은 이 두 classmethod에서 호환성을 위해 유지되지만 startup health check를 실행하지 않습니다.

## 4. Host-owned raw client에서 시작하기

외부 서비스 연결이 필요합니다. 구체적인 client 준비와 model/collection/timeout은 [Configuration](Configuration)을 확인하십시오.

```python
from minio import Minio
from ollama import Client as OllamaClient
from pymilvus import MilvusClient
from sqlalchemy import create_engine

from rag_system_core import AuthenticatedUser, DocmeshRAGServiceFactory


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
user = AuthenticatedUser(sub="user-a")

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
    print(core.health_check().to_dict())
    print(core.ingest_text(user=user, text="host client path", source="host.txt"))
```

이 경로는 RAG/DMS 환경변수를 읽지 않습니다. host-owned Engine과 raw transport client lifecycle은 호출자가 정리합니다.

## 5. 명시적 settings와 `ServiceBundle`

`build_docmesh_runtime_plan`은 plan만 만들고, `assemble_docmesh_services`는 명시적 `ServiceConfigs`로 client를 조립합니다.

```python
from rag_system_core.composition.configuration import (
    MilvusConfig,
    OllamaConfig,
    ServiceConfigs,
)
from rag_system_core.composition.docmesh_runtime import (
    assemble_docmesh_services,
    build_docmesh_runtime_plan,
)
from rag_system_core.composition.rag_factories import (
    create_rag_embedding_client,
    create_rag_generation_client,
    create_rag_vector_store,
)

settings = ServiceConfigs(
    milvus=MilvusConfig(endpoint="./data/rag-vectors.db"),
    ollama=OllamaConfig(host="http://ollama:11434"),
)
plan = build_docmesh_runtime_plan(
    services={"ollama", "milvus"},
    required={"ollama"},
    check_on_startup=False,
    parallel_healthchecks=False,
)
bundle = assemble_docmesh_services(plan=plan, settings=settings)
try:
    embedding = create_rag_embedding_client(bundle=bundle, model="bge-m3")
    generation = create_rag_generation_client(bundle=bundle, model="gpt-oss:20b")
    vectors = create_rag_vector_store(bundle=bundle, collection_name="rag_chunks", timeout=30.0)
    print(embedding, generation, vectors)
finally:
    bundle.close()
```

`ServiceBundle`은 context manager가 아니므로 `with bundle:`을 사용하지 않습니다. bundle이 생성한 client는 `bundle.close()`로 정리합니다.

## 6. Health aggregation

```python
from rag_system_core.composition.health import run_health_checks

result = run_health_checks(
    {
        "metadata": lambda: None,
        "custom": lambda: None,
    },
    required_services={"metadata", "custom"},
)
assert result.ok
print(result.to_dict())
```

check 예외는 `ServiceHealthStatus(ok=False, error=...)`로 변환되고, required check가 없으면 aggregate가 unhealthy가 됩니다. `parallel=True`이면 checks를 병렬 실행합니다.

## 7. Built-in adapter 직접 사용

### `FixedWindowChunker`

```python
from rag_system_core.adapters import FixedWindowChunker

chunker = FixedWindowChunker(chunk_size=32, chunk_overlap=4)
print(chunker.chunk("alpha   beta\n gamma"))
```

`chunk_size > 0`, `0 <= chunk_overlap < chunk_size`를 요구하며 whitespace를 한 칸으로 정규화합니다.

### Ollama adapter

```python
from ollama import Client as OllamaClient

from rag_system_core import OllamaEmbeddingClient, OllamaGenerationClient

client = OllamaClient(host="http://ollama:11434")
embedding = OllamaEmbeddingClient(client=client, model="bge-m3")
generation = OllamaGenerationClient(client=client, model="gpt-oss:20b")

print(embedding.embed(["hello"]))
print(generation.generate("Say hello"))
```

빈 model은 `ValueError`, transport 또는 malformed response는 `RuntimeError`입니다. 주입 Ollama client는 embedding에 `embed(model=..., input=...)`, generation에 `chat(model=..., messages=...)`를 제공해야 합니다.

### MetadataStore와 Milvus adapter

```python
from sqlalchemy import create_engine
from pymilvus import MilvusClient

from rag_system_core.storage import MetadataStore, MilvusLiteVectorStore

metadata = MetadataStore(create_engine("sqlite+pysqlite:///./data/rag-metadata.db"))
try:
    metadata.check()
finally:
    metadata.close()

vectors = MilvusLiteVectorStore(
    client=MilvusClient(uri="./data/rag-vectors.db"),
    collection_name="rag_chunks",
    timeout=30.0,
)
vectors.check()
```

## 8. Advanced domain service

일반 애플리케이션은 user-aware `RAGCore`를 사용합니다. 이미 `user_id`를 해석하고 domain 단계만 직접 조정할 때만 다음 advanced path를 사용합니다.

```python
from rag_system_core.domain.core import GenerationService, RetrievalService

retrieval = RetrievalService(
    embedding_client=embedding_client,
    vector_store=vector_store,
)
generation = GenerationService(
    generation_client=generation_client,
    system_prompt="주어진 context만 사용하세요.",
)
chunks = retrieval.search(user_id="user-a", question="alpha", top_k=3)
result = generation.generate(question="alpha", context_chunks=chunks)
print(result.answer)
```

이 경로는 `AuthenticatedUser`를 받지 않으며 user-scope·인증 보장은 호출자 책임입니다. `IngestionService`, `RetrievalService`, `GenerationService`의 전체 export와 signature는 [API-Reference §8](API-Reference#8-advanced-domain-service-api)를 참조하십시오.

## 9. 검증

저장소 전체 테스트:

```bash
uv run pytest -q
```

Python fenced example은 public import path와 현재 signature 기준으로 작성했습니다. 외부 서비스 예제는 service 연결 상태와 [Configuration](Configuration)을 먼저 확인하십시오.
