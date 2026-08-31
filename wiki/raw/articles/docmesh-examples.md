---
source_url: https://github.com/kyundae-kim/docmesh-rag-system-core/wiki/Examples
ingested: 2026-08-26
sha256: 299b06d14b7752d5ba88a4657f3dfce46f9149db0484061949f63d8ee1eeab50
---
# 사용 예제

> **문서 기준 (version-identifiable)**
>
> | 항목 | 값 |
> |---|---|
> | package | `rag-system-core` |
> | package version | `0.5.0` (`pyproject.toml`) |
> | 구현 기준 source revision | `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3` |
> | runtime dependencies | `dms-core>=0.10.0`, `ollama>=0.6.2`, `pydantic-settings>=2.14.1`, `pymilvus[milvus-lite]>=3.0.1` |
> | Python | `>=3.11` |
>
> 예제는 위 source revision의 public import와 signature를 기준으로 합니다. `v0.5.0` tag가 없으므로 재현 시 package version과 source commit을 함께 확인하십시오.

이 문서는 현재 `rag-system-core` 공개 import를 사용해 복사·조정할 수 있는 예제 모음입니다.

- API 계약: [API-Reference](API-Reference)
- 설정·lifecycle: [Configuration](Configuration)
- 권장 첫 실행: §1의 외부 서비스 없는 직접 조립

## 사전 조건과 예제 유형

- Python `>=3.11`과 `rag-system-core` runtime dependencies가 필요합니다.
- §1은 Ollama, Milvus, MinIO 없이 실행하는 dependency-light first-success 예제입니다.
- §3–§7은 외부 client/service가 준비된 integration 예제입니다. code fence는 실제 public import와 signature를 사용하지만 외부 인프라가 없으면 실행되지 않습니다.
- 모든 예제는 health-check runner, startup check 옵션, 환경변수 자동 loader를 사용하지 않습니다. 현재 구현의 public API가 아니기 때문입니다.

## 1. 외부 서비스 없는 첫 성공: 직접 `RAGCore` 조립

다음 예제는 public port 계약과 SQLite metadata store를 사용합니다. 외부 Ollama, Milvus, MinIO 없이 ingestion → retrieval → generation을 한 프로세스에서 확인할 수 있습니다.

```python
from pathlib import Path

from sqlalchemy import create_engine

from rag_system_core import AuthenticatedUser, RAGCore
from rag_system_core.adapters import FixedWindowChunker
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
)

try:
    ingested = core.ingest_text(
        user=user,
        text="RAG 코어는 사용자 스코프를 적용합니다.",
        source="guide.txt",
    )
    result = core.query(user=user, question="어떤 스코프를 적용하나요?", top_k=3)
    assert ingested.chunk_count > 0
    assert result.context_chunks[0].user_id == "user-a"
    print(result.answer)
    print([chunk.content for chunk in result.context_chunks])
finally:
    metadata_store.close()
```

`RAGCore`는 주입된 client/store lifecycle을 소유하지 않습니다. 직접 조립한 `MetadataStore`와 raw client는 호출자가 정리합니다. 이 예제는 `RAGCore` 생성자에 실제 public collaborator contract를 구현해 전달하는 normative example입니다.

## 2. 파일 입력·문서 lifecycle·단계별 상태

§1의 `core`, `user`가 살아 있는 동안 다음 API를 호출할 수 있습니다.

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
    print(core.get_ingestion_step_statuses(document.doc_id, user=user))

assert core.get_document(stream_result.doc_id, user=user) is not None
assert core.delete_document(stream_result.doc_id, user=user) is True
assert core.get_document(stream_result.doc_id, user=user) is None
sample_path.unlink()
```

동작 계약:

- stream `source`는 필수이며 없거나 공백이면 `ValueError`입니다.
- path `source`를 생략하면 파일명이 사용됩니다.
- stream/path bytes는 UTF-8이어야 합니다.
- `list_ingestion_progress`는 transition history이고 `get_ingestion_step_statuses`는 단계별 final status map입니다.
- 다른 사용자의 `doc_id`는 조회되지 않으며 삭제 결과는 `False`입니다.

## 3. 이미 만든 collaborator로 `DocmeshRAGServiceFactory` 조립

`from_clients`는 caller가 만든 DMS용 Engine/MinIO와 RAG collaborator를 사용합니다. `metadata_engine`을 전달해야 `create_rag_core()`를 정상 호출할 수 있습니다.

```python
from sqlalchemy import create_engine

from rag_system_core import DocmeshRAGServiceFactory


dms_engine = create_engine("sqlite+pysqlite:///./data/dms.db")
rag_metadata_engine = create_engine("sqlite+pysqlite:///./data/rag-metadata.db")

# 아래 client/collaborator는 상위 애플리케이션이 준비합니다.
with DocmeshRAGServiceFactory.from_clients(
    engine=dms_engine,
    minio_client=minio_client,
    bucket_name="documents",
    embedding_client=embedding_client,
    generation_client=generation_client,
    vector_store=vector_store,
    metadata_engine=rag_metadata_engine,
) as factory:
    core = factory.create_rag_core(chunk_size=512, chunk_overlap=64)
    result = core.ingest_text(user=user, text="factory path", source="factory.txt")
    print(result.doc_id)
```

Factory context는 DMS SDK, Engine, MinIO, 주입 collaborator를 닫지 않습니다. `metadata_path` compatibility path로 Factory가 직접 만든 `MetadataStore`만 Factory `close()`에서 추적·정리합니다.

## 4. host-owned raw client에서 시작하기

외부 서비스 연결이 필요할 때는 상위 애플리케이션이 만든 raw client를 전달합니다.

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
) as factory:
    core = factory.create_rag_core()
    print(core.ingest_text(user=user, text="host client path", source="host.txt"))
```

이 경로는 RAG/DMS environment loader를 호출하지 않습니다. Engine과 raw transport client lifecycle은 caller가 관리하며 startup health check도 자동 실행하지 않습니다.

## 5. 명시적 settings와 `ServiceBundle`

`build_docmesh_runtime_plan`과 `assemble_docmesh_services`는 명시적 `ServiceConfigs`를 사용합니다. 다음 예제는 Ollama/Milvus 서비스가 실행 중인 integration 환경에서 사용합니다.

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
    milvus=MilvusConfig(
        endpoint="./data/rag-vectors.db",
        collection="rag_chunks",
        request_timeout_seconds=30,
    ),
    ollama=OllamaConfig(
        host="http://ollama:11434",
        embedding_model="bge-m3",
        generation_model="gpt-oss:20b",
    ),
)
plan = build_docmesh_runtime_plan(
    services={"ollama", "milvus"},
    one_of=(),
)
bundle = assemble_docmesh_services(plan=plan, settings=settings)
try:
    embedding = create_rag_embedding_client(bundle=bundle)
    generation = create_rag_generation_client(bundle=bundle)
    vectors = create_rag_vector_store(bundle=bundle)
    print(embedding, generation, vectors)
finally:
    bundle.close()
```

해석 우선순위는 명시적 인자 → `settings` → `bundle.configs` → vector 기본값 `rag_chunks`/`30.0`입니다. model이 settings에도 없으면 Ollama adapter가 `ValueError`를 발생시키고, client를 만들 수 없으면 factory helper가 `RuntimeError`를 발생시킵니다. `ServiceBundle`은 context manager가 아니므로 `bundle.close()`를 직접 호출하십시오.

## 6. Built-in adapter와 storage 직접 사용

### `FixedWindowChunker`

```python
from rag_system_core.adapters import FixedWindowChunker

chunker = FixedWindowChunker(chunk_size=32, chunk_overlap=4)
assert chunker.chunk("alpha   beta\n gamma")
```

`chunk_size > 0`, `0 <= chunk_overlap < chunk_size`를 요구합니다.

### Ollama adapter contract

```python
from rag_system_core import OllamaEmbeddingClient, OllamaGenerationClient


class FakeOllamaClient:
    def embed(self, *, model: str, input: list[str]) -> dict[str, list[list[float]]]:
        return {"embeddings": [[float(len(text))] for text in input]}

    def chat(self, *, model: str, messages: list[dict[str, str]]) -> dict[str, dict[str, str]]:
        return {"message": {"content": messages[0]["content"]}}


client = FakeOllamaClient()
embedding = OllamaEmbeddingClient(client=client, model="bge-m3")
generation = OllamaGenerationClient(client=client, model="gpt-oss:20b")

assert embedding.embed(["hello"])[0] == [5.0]
assert generation.generate("Say hello") == "Say hello"
```

실제 Ollama client도 동일하게 `embed(model=..., input=...)`와 `chat(model=..., messages=...)` 응답 shape를 제공해야 합니다. 빈 model은 `ValueError`, transport/malformed response는 `RuntimeError`입니다.

### `MetadataStore`와 `MilvusLiteVectorStore`

```python
from sqlalchemy import create_engine
from pymilvus import MilvusClient

from rag_system_core.storage import MetadataStore, MilvusLiteVectorStore

metadata = MetadataStore(create_engine("sqlite+pysqlite:///./data/rag-metadata.db"))
try:
    print(metadata.list_documents("user-a"))
finally:
    metadata.close()

vectors = MilvusLiteVectorStore(
    client=MilvusClient(uri="./data/rag-vectors.db"),
    collection_name="rag_chunks",
    timeout=30.0,
)
```

Milvus adapter는 첫 insert 시 collection을 만들 수 있습니다. metadata/vector/raw client lifecycle은 caller가 관리합니다.

## 7. DMS asset adapter와 advanced domain service

### DMS asset storage

```python
from rag_system_core.composition import create_dms_sdk_from_clients
from rag_system_core.storage import DmsDocumentStorage

sdk = create_dms_sdk_from_clients(
    engine=dms_engine,
    minio_client=minio_client,
    bucket_name="documents",
)
storage = DmsDocumentStorage(sdk)
asset_reference = storage.store_text(
    doc_id="doc-1",
    user_id="user-a",
    text="UTF-8 source",
    source="note.txt",
    idempotency_key="job-1",
)
print(asset_reference)
```

현재 구현에서 text upload만 idempotency key/scope를 DMS request에 전달합니다. stream/path API는 signature에 key가 있지만 DMS request에는 전달하지 않습니다.

### `domain.core` advanced path

일반 애플리케이션은 `RAGCore`를 사용하고, 이미 `user_id`를 해석해 domain 단계만 직접 조정할 때 아래 path를 사용합니다.

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

이 path는 `AuthenticatedUser`를 받지 않으며 인증·scope 보장은 호출자 책임입니다. `IngestionService`의 direct API와 전체 signature는 [API-Reference §8](API-Reference)의 계약을 따릅니다.

## 8. Export-to-example coverage index

API export가 어느 예제에서 실제로 사용되는지 모듈별로 추적합니다.

| source `__all__` module | example sections |
|---|---|
| `rag_system_core` | §1–§4, §6 |
| `rag_system_core.adapters` | §1, §6 |
| `rag_system_core.ports` | §1, §7 |
| `rag_system_core.types` | §1–§2, §7 |
| `rag_system_core.composition` | §3–§5, §7 |
| `rag_system_core.composition.configuration` | §5 |
| `rag_system_core.composition.dms_runtime` | §7 |
| `rag_system_core.composition.docmesh_runtime` | §5 |
| `rag_system_core.composition.factories` | §3, §5 |
| `rag_system_core.composition.rag_factories` | §5 |
| `rag_system_core.composition.service_factory` | §3–§4 |
| `rag_system_core.domain.core` | §1, §7 |
| `rag_system_core.storage` | §1, §6–§7 |
| `rag_system_core.storage.dms_document_storage` | §7 |

환경변수 key는 이 package의 public configuration surface가 아닙니다. settings 기반 예제도 모두 `ServiceConfigs`를 명시적으로 생성합니다.

## 9. 검증

저장소 root에서 canonical test command를 실행합니다.

```bash
uv run pytest -q
```

문서 검증 시 다음도 확인하십시오.

```bash
git diff --check
```

§1은 dependency-light first-success 실행 대상으로 사용하고, §3–§7은 외부 service/client가 준비된 환경에서 실행합니다. 예제의 public import가 현재 package version/source revision과 맞지 않으면 API page의 version block과 source export를 먼저 대조하십시오.
