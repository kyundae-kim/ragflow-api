# RAG Flow API

FastAPI를 HTTP/API 계층으로, `docmesh-rag-system-core v0.5.0`의 `RAGCore`를
application 계층으로 사용하는 동기식 RAG API입니다. API 계층은 사용자 scope 입력, 요청 검증,
multipart 처리, 공개 응답 DTO, HTTP 오류 매핑을 담당하고 ingestion/retrieval/generation
규칙은 `RAGCore`에 위임합니다.

```text
HTTP request
  -> FastAPI (X-User-Id, validation, DTO/error mapping)
  -> RAGCore (user-scoped application use cases)
  -> DMS + RAG metadata DB + Milvus + Ollama
```

## API

문서·query API에는 호출자가 제공하는 `X-User-Id` header가 필요합니다. `/health/*`와 FastAPI가
제공하는 `/openapi.json`, `/docs`, `/redoc`은 운영 점검과 API 탐색을 위해 public입니다.
API는 identity provider 또는 token을 검증하지 않습니다. `X-User-Id` 값이
`AuthenticatedUser.sub`가 되며 모든 문서/청크/검색은 이 사용자 범위로 실행됩니다.
이 header는 신뢰된 gateway 또는 내부 호출자가 설정해야 합니다.

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/health/live` | 프로세스 liveness |
| `GET` | `/health/ready` | RAG dependency readiness; 실패 시 `503` |
| `POST` | `/documents/text` | UTF-8 텍스트 ingestion |
| `POST` | `/documents/file` | multipart UTF-8 파일 ingestion |
| `GET` | `/documents` | 현재 사용자의 문서 목록 |
| `GET` | `/documents/{doc_id}` | 현재 사용자의 문서 조회 |
| `GET` | `/documents/{doc_id}/chunks` | 문서 청크 조회 |
| `GET` | `/documents/{doc_id}/ingestion-progress` | ingestion 진행 기록 조회 |
| `DELETE` | `/documents/{doc_id}` | 문서와 파생 데이터 삭제 |
| `POST` | `/query` | 현재 사용자의 청크로 RAG 질의 |

공개 응답은 application 내부의 `user_id`, DMS `asset_reference`, LLM prompt를 노출하지
않습니다. 다른 사용자의 `doc_id`는 존재 여부를 숨기기 위해 `404`로 응답합니다.

### 예시

```bash
curl -X POST http://localhost:8000/documents/text \
  -H 'X-User-Id: user-a' \
  -H 'Content-Type: application/json' \
  -d '{"text":"FastAPI is the transport layer.","source":"architecture.md"}'

curl -X POST http://localhost:8000/query \
  -H 'X-User-Id: user-a' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the transport layer?","top_k":3}'
```

## 구성

### API와 사용자 scope

| 환경변수 | 기본값 | 설명 |
|---|---:|---|
| `RAGFLOW_METADATA_DATABASE_URL` | `sqlite+pysqlite:///./data/rag-metadata.db` | RAG metadata SQLAlchemy URL |
| `RAGFLOW_CHUNK_SIZE` | `512` | 청크 문자 수 |
| `RAGFLOW_CHUNK_OVERLAP` | `64` | 인접 청크 overlap |
| `RAGFLOW_CHECK_ON_STARTUP` | `true` | startup dependency health check |
| `RAGFLOW_MAX_UPLOAD_BYTES` | `10485760` | UTF-8 파일 최대 크기(기본 10 MiB) |

ASGI middleware는 이 파일 한도에 multipart overhead 1 MiB를 더한 값으로 전체 request
body도 streaming 제한하므로, FastAPI가 multipart를 파싱하기 전에 과도한 요청을 차단합니다.

사용자 scope는 각 business request의 `X-User-Id` header로 직접 전달합니다.
API 자체는 해당 값의 인증·인가를 수행하지 않으므로, 외부 gateway 또는 신뢰된 내부
호출 경계에서 header 위조를 차단해야 합니다.

### RAG runtime

| 환경변수 | 설명 |
|---|---|
| `OLLAMA_HOST` | Ollama endpoint |
| `OLLAMA_EMBEDDING_MODEL` | embedding model |
| `OLLAMA_GENERATION_MODEL` | generation model |
| `MILVUS_ENDPOINT` | Milvus endpoint 또는 Milvus Lite 경로 |
| `MILVUS_COLLECTION` | vector collection; 선택 |
| `MILVUS_TOKEN` | 인증 token; 선택 |

### DMS runtime

| 환경변수 | 설명 |
|---|---|
| `DMS_METADATA_BACKEND` | `sqlite` 또는 `postgresql` |
| `DMS_SQLITE_PATH` | SQLite 사용 시 DMS metadata 경로 |
| `DMS_POSTGRES_HOST`, `DMS_POSTGRES_DB`, `DMS_POSTGRES_USER`, `DMS_POSTGRES_PASSWORD` | PostgreSQL 사용 시 연결 정보 |
| `DMS_MINIO_ENDPOINT` | MinIO endpoint |
| `DMS_MINIO_ACCESS_KEY` | MinIO access key |
| `DMS_MINIO_SECRET_KEY` | MinIO secret key |
| `DMS_MINIO_BUCKET` | DMS object bucket |
| `DMS_MINIO_SECURE` | TLS 사용 여부; 기본 `false` |

DMS metadata와 RAG metadata는 서로 다른 저장소입니다. 로컬 실행 예시는 다음과
같습니다.

```bash
export OLLAMA_HOST='http://localhost:11434'
export OLLAMA_EMBEDDING_MODEL='nomic-embed-text'
export OLLAMA_GENERATION_MODEL='llama3.2'
export MILVUS_ENDPOINT='http://localhost:19530'

export DMS_METADATA_BACKEND='sqlite'
export DMS_SQLITE_PATH='./data/dms.db'
export DMS_MINIO_ENDPOINT='localhost:9000'
export DMS_MINIO_ACCESS_KEY='replace-me'
export DMS_MINIO_SECRET_KEY='replace-me'
export DMS_MINIO_BUCKET='documents'
```

## 실행과 검증

```bash
uv sync

# 개발
uv run fastapi dev

# production-style local process
uv run fastapi run --host 0.0.0.0 --port 8000

# verification
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Docker image는 Python 3.11 multi-stage build를 사용하며 Git/uv가 없는 final stage에서
UID 10001의 non-root 사용자로 production FastAPI command를 실행합니다.

```bash
docker build -t ragflow-api .
docker run --rm -p 8000:8000 --env-file .env ragflow-api
```

## 오류 계약

API가 직접 만드는 오류는 `code`, `category`, `retryable`, `message`를 갖는 JSON으로
응답합니다. `dms.DmsError`의 public `code`/`category`/`retryable`을 host adapter가
secret-safe status/body로 projection합니다. 예상하지 못한 application 오류와 readiness 오류에는
내부 exception 또는 연결 문자열을 노출하지 않습니다. OpenAPI의 `401`/`4xx`/`5xx`
response와 multipart parser를 포함한 framework HTTP 오류도 실제 `ApiErrorResponse`
body와 동일한 schema를 사용합니다.

## Lifecycle

FastAPI lifespan이 Ollama/Milvus service bundle, DMS/RAG SQLAlchemy engine,
`DocmeshRAGServiceFactory`, RAG metadata store를 조립하고 종료 시 metadata store,
factory, MinIO HTTP pool, engine, service client 순서로 정리합니다.
테스트에서는 `create_app(core=...)` 또는 `runtime_factory=`로 실제
외부 서비스 없이 같은 API 경계를 검증할 수 있습니다.

