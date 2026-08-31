---
title: rag-system-core v0.5.0과 현재 host compatibility
created: 2026-08-26
updated: 2026-08-26
type: comparison
tags: [comparison, api, deployment, reliability, fastapi, rag]
sources:
  - raw/articles/docmesh-api-reference.md
  - raw/articles/docmesh-configuration.md
  - raw/articles/docmesh-examples.md
confidence: high
contested: true
---

# rag-system-core v0.5.0과 현재 host compatibility

## 범위

2026-08-26에 갱신된 `rag-system-core` v0.5.0 문서와 이 repository의 `ragflow-api` host 코드를 비교한 compatibility 기록이다. package 문서는 source revision `f812b6d78299e9d1179cdbeb88ee9c0aca7864e3` 및 `dms-core>=0.10.0`을 기준으로 하며, 현재 host는 `pyproject.toml`에서 `rag-system-core>=0.5.0`을 선언한다.

## 비교 결과

| 영역 | v0.5.0 package 계약 | 현재 host 관찰 | 판정 |
|---|---|---|---|
| Runtime plan | `build_docmesh_runtime_plan(*, services=None, one_of=())` | `ragflow/runtime.py:108-113`에서 `required`, `check_on_startup`, `parallel_healthchecks`를 전달 | API 인자 불일치 |
| Factory assembly | `DocmeshRAGServiceFactory.from_host_clients(...)`에 startup health 인자 없음 | `ragflow/runtime.py:134-152`에서 `check_on_startup`을 전달 | API 인자 불일치 |
| Health surface | `RAGCore` 생성자와 package public export에 health runner가 없고, 문서는 health-check API가 없다고 명시 | `ragflow/api/health.py:26`에서 `core.health_check()` 호출 | 기능 경계 불일치 |
| Health helper | v0.5 package 공개 export에 `run_health_checks` 없음 | `test_ragflow/test_api.py:12`에서 `rag_system_core.composition.run_health_checks` import | import 불일치 |
| Environment loading | package는 process environment를 자동으로 읽지 않음 | host의 `ragflow/runtime.py`가 환경변수를 읽어 `ServiceConfigs`를 생성 | host-owned 구현으로는 양립 가능 |
| Resource cleanup | `ServiceBundle.close()`는 명시적으로 호출하고 host-owned 자원은 package가 닫지 않음 | host가 `ExitStack` callback으로 bundle, factory, engine, MinIO를 정리 | 방향은 양립 가능 |

## 해석과 조치 경계

현재 상태를 실행 가능한 통합으로 간주하지 않는다. 특히 runtime plan·Factory의 legacy health 인자를 제거하거나 현재 package와 일치하는 버전을 선택해야 하며, readiness는 `RAGCore`의 비공개/부재 health API에 의존하지 않는 host-owned dependency check로 재설계해야 한다. 이 페이지는 코드 수정이나 버전 pinning을 수행하지 않고, 다음 작업의 acceptance criteria를 기록한다.

`ragflow-api`의 HTTP 경계는 [[fastapi-rest-adapter-boundary]]에, package의 명시적 설정과 lifecycle은 [[runtime-configuration-and-lifecycle]]에, package 전체 경계는 [[docmesh-rag-system-core]]에 정리되어 있다.

## Repository evidence

- `pyproject.toml:11` — `rag-system-core>=0.5.0`
- `ragflow/runtime.py:108-152` — runtime plan과 Factory 호출
- `ragflow/api/health.py:22-43` — readiness 구현
- `test_ragflow/test_api.py:12,147` — health helper import와 injection

## Sources

- `raw/articles/docmesh-api-reference.md`
- `raw/articles/docmesh-configuration.md`
- `raw/articles/docmesh-examples.md`
