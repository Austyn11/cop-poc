# Graph Retriever Implementation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DAG에서 파라미터 노드·엣지 정보를 구조화된 JSON으로 추출해 LLM user message에 주입하는 GraphRetriever 레이어를 도입한다.

**Architecture:** 별도 모듈 `app/llm/graph_retriever.py`에 `GraphRetriever` 클래스를 구현한다. `routes.py`에서 DAG 초기화 직후 `retrieve(dag)`를 호출해 컨텍스트를 생성하고, `parse_command`에 기존 `current_params` 대신 이 컨텍스트를 전달한다.

**Tech Stack:** Python, 기존 `app/graph/model.DAG` API (`get_all`, `get_edges`, `_nodes`)

---

## 1. 파일 구조

### 신규 파일
- `app/llm/graph_retriever.py` — `GraphRetriever` 클래스
- `tests/test_graph_retriever.py` — 단위 테스트

### 수정 파일
- `app/llm/parser.py` — `parse_command` 시그니처: `current_params: dict` → `graph_context: dict`
- `app/api/routes.py` — Retriever 호출 추가, `parse_command` 호출 인자 변경
- `tests/test_parser.py` — 시그니처 변경 반영

---

## 2. GraphRetriever 클래스

```python
# app/llm/graph_retriever.py
class GraphRetriever:
    def retrieve(self, dag: DAG) -> dict:
        return {"nodes": self._build_nodes(dag)}

    def _build_nodes(self, dag: DAG) -> dict:
        # 노드별 value, subgraph, user_facing, controls, constraints, affects 수집
        ...
```

### 출력 JSON 구조

```json
{
  "nodes": {
    "height": {
      "value": 90.0,
      "subgraph": "body",
      "user_facing": true,
      "controls": [],
      "constraints": ["height >= 5.0"],
      "affects": ["Face:side_wall"]
    },
    "outer_top_r": {
      "value": 40.0,
      "subgraph": "body",
      "user_facing": true,
      "controls": ["inner_top_r"],
      "constraints": ["outer_top_r >= 7.0", "outer_top_r > thickness"],
      "affects": ["Face:side_wall", "Edge:top_rim"]
    },
    "inner_top_r": {
      "value": 37.0,
      "subgraph": "body",
      "user_facing": false,
      "controls": [],
      "constraints": [],
      "affects": []
    }
  }
}
```

### 필드 정의

| 필드 | 소스 엣지 타입 | 설명 |
|---|---|---|
| `value` | `dag.get(name)` | 현재 파라미터 값 |
| `subgraph` | `ParamNode.subgraph` | `"body"` / `"handle"` / `"joint"` |
| `user_facing` | `ParamNode.is_user_facing` | LLM이 직접 수정 가능 여부 |
| `controls` | `CONTROLS` (outgoing) | 이 노드 변경 시 자동 재계산되는 파생 노드 |
| `constraints` | `CONSTRAINS` (target=name) | 이 노드에 걸린 제약 규칙 문자열 |
| `affects` | `AFFECTS_GEOMETRY` (source=name) | 영향을 주는 기하 요소 |

- `user_facing: false` 노드도 포함 — LLM이 직접 수정 불가 파라미터를 인식하도록
- `BELONGS_TO`, `EQUIVALENT_TO` 엣지는 이번 범위에서 제외 (LLM에 불필요한 노이즈)

---

## 3. parse_command 변경

### 시그니처

```python
# 변경 전
def parse_command(command: str, current_params: dict, selection: dict | None) -> dict

# 변경 후
def parse_command(command: str, graph_context: dict, selection: dict | None) -> dict
```

### user message 구성

```python
# 변경 전
user_content = f"Current params: {json.dumps(current_params)}\n"

# 변경 후
user_content = f"Current graph state:\n{json.dumps(graph_context, indent=2)}\n"
```

### system prompt 변경

하드코딩된 파라미터 목록 제거:
```
# 제거 대상 (현재 parser.py의 User-facing parameters 섹션)
- Tapered body: height, outer_top_r, outer_bottom_r, thickness, bottom_thickness
- Cylinder body: cylinder_height, cylinder_radius, ...
- BSpline handle: section_width, section_height, ...
- Ring handle: ring_outer_r, ...
```

대신 아래 문구로 교체:
```
The graph_context in each request contains all available parameters with their
current values, constraints, and geometry relationships. Only modify nodes where
user_facing is true.
```

---

## 4. routes.py 변경

모든 intent 분기(`create`, `modify`, `post_process`)에서 `parse_command` 호출 전에 Retriever를 실행한다.

```python
from app.llm.graph_retriever import GraphRetriever

_retriever = GraphRetriever()

# parse_command 호출 직전 (모든 intent 공통)
dag = _build_and_init(...)
graph_context = _retriever.retrieve(dag)
parsed = parse_command(req.command, graph_context, selection)
```

---

## 5. 테스트 전략

### test_graph_retriever.py

- `retrieve()` 결과에 모든 DAG 노드 이름이 포함되는지 확인
- `controls` 필드: `outer_top_r` → `["inner_top_r"]` 포함
- `constraints` 필드: `height` → `["height >= 5.0"]` 포함
- `affects` 필드: `height` → `["Face:side_wall"]` 포함
- `user_facing: false` 노드(`inner_top_r`)도 출력에 포함되는지 확인
- handle 없는 DAG (body only)도 정상 동작하는지 확인

### test_parser.py

- `parse_command` 호출 인자를 `current_params` dict → `graph_context` dict로 교체
- 기존 테스트 로직은 동일하게 유지

---

## 6. 범위 외 (이번 구현에서 제외)

- Query-relevant 검색 (향후 Approach B로 전환 가능한 구조로 설계)
- `BELONGS_TO`, `EQUIVALENT_TO` 엣지 주입
- Request Router 레이어 분리 (별도 태스크)
- Boolean overlap condition 검증 (별도 태스크)
