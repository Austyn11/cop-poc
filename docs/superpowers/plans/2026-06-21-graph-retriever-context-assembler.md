# GraphRetriever Context Assembler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GraphRetriever.retrieve()`가 DAG 외에 `body_template`, `handle_template`, `selection`을 받아 `templates` 와 `intents` 서브그래프를 포함한 완전한 LLM 컨텍스트를 조립하도록 확장한다.

**Architecture:** GraphRetriever가 Context Assembler 역할을 맡아 단일 `retrieve()` 호출로 LLM에 필요한 모든 컨텍스트(`nodes` + `templates` + `intents`)를 반환한다. `cup_graph.py`에 `available_templates()` 공개 함수를 추가하고, `parser.py` system prompt를 새 필드를 참조하도록 업데이트한다.

**Tech Stack:** Python, 기존 `app/graph/cup_graph.DAG`, `app/llm/graph_retriever.GraphRetriever`, FastAPI `routes.py`

---

## 파일 구조

| 파일 | 변경 유형 | 내용 |
|---|---|---|
| `app/graph/cup_graph.py` | 수정 | `available_templates()` 공개 함수 추가 |
| `app/llm/graph_retriever.py` | 수정 | `retrieve()` 시그니처 확장, `_build_templates()`, `_build_intents()` 추가 |
| `tests/test_graph_retriever.py` | 수정 | 기존 13개 테스트 시그니처 업데이트 + 신규 8개 테스트 추가 |
| `app/api/routes.py` | 수정 | `_retriever.retrieve(dag)` → 확장 호출 |
| `app/llm/parser.py` | 수정 | system prompt에 `templates`, `intents` 필드 설명 추가 |

---

## Task 1: cup_graph.py — available_templates() 추가

**Files:**
- Modify: `app/graph/cup_graph.py` (맨 아래 공개 API 섹션)
- Test: `tests/test_cup_graph.py` (기존 파일 끝에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_cup_graph.py` 끝에 추가:

```python
# ── available_templates ───────────────────────────────────────

from app.graph.cup_graph import available_templates


def test_available_templates_has_body_and_handle_keys():
    avail = available_templates()
    assert "body" in avail
    assert "handle" in avail


def test_available_templates_body_contains_known_types():
    avail = available_templates()
    assert "tapered" in avail["body"]
    assert "cylinder" in avail["body"]


def test_available_templates_handle_contains_known_types_and_none():
    avail = available_templates()
    assert "bspline" in avail["handle"]
    assert "ring" in avail["handle"]
    assert None in avail["handle"]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
source venv/bin/activate && python -m pytest tests/test_cup_graph.py::test_available_templates_has_body_and_handle_keys -v
```

Expected: `FAILED` with `ImportError: cannot import name 'available_templates'`

- [ ] **Step 3: 구현**

`app/graph/cup_graph.py`의 `build_dag` 함수 아래 (파일 끝)에 추가:

```python
def available_templates() -> dict[str, list]:
    """현재 등록된 body/handle 템플릿 목록 반환."""
    return {
        "body": list(_BODY_FEATURES.keys()),
        "handle": list(_HANDLE_FEATURES.keys()) + [None],
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_cup_graph.py::test_available_templates_has_body_and_handle_keys tests/test_cup_graph.py::test_available_templates_body_contains_known_types tests/test_cup_graph.py::test_available_templates_handle_contains_known_types_and_none -v
```

Expected: `3 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/graph/cup_graph.py tests/test_cup_graph.py
git commit -m "feat: add available_templates() public API to cup_graph"
```

---

## Task 2: GraphRetriever 확장 — templates + intents 서브그래프

**Files:**
- Modify: `app/llm/graph_retriever.py`
- Modify: `tests/test_graph_retriever.py`

### 2-A: 기존 13개 테스트 시그니처 업데이트

- [ ] **Step 1: 기존 테스트에 `body_template`, `handle_template` 인자 추가**

`tests/test_graph_retriever.py`의 `retrieve(dag_...)` 호출을 모두 업데이트.

파일 전체를 아래로 교체:

```python
import pytest
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize
from app.llm.graph_retriever import GraphRetriever


@pytest.fixture
def dag_tapered_bspline():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    return dag


@pytest.fixture
def dag_tapered_only():
    dag = build_dag("tapered", None)
    initialize(dag)
    return dag


# ── nodes 서브그래프 (기존 테스트 — 시그니처 업데이트) ──────────────────

def test_retrieve_returns_nodes_key(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "nodes" in context


def test_retrieve_contains_all_dag_nodes(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    nodes = context["nodes"]
    for name in dag_tapered_bspline.nodes():
        assert name in nodes, f"Missing node: {name}"


def test_node_has_required_fields(dag_tapered_bspline):
    node = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")["nodes"]["height"]
    assert "value" in node
    assert "subgraph" in node
    assert "user_facing" in node
    assert "controls" in node
    assert "constraints" in node
    assert "affects" in node


def test_node_value_matches_dag(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["height"]["value"] == dag_tapered_bspline.get("height")


def test_user_facing_true_for_editable_param(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["height"]["user_facing"] is True


def test_user_facing_false_for_derived_param(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["inner_top_r"]["user_facing"] is False


def test_controls_field_lists_derived_nodes(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "inner_top_r" in context["nodes"]["outer_top_r"]["controls"]


def test_controls_empty_for_leaf_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["inner_top_r"]["controls"] == []


def test_constraints_field_contains_rule_string(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "height >= 5.0" in context["nodes"]["height"]["constraints"]


def test_constraints_empty_for_unconstrained_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["inner_top_r"]["constraints"] == []


def test_affects_field_lists_geometry_elements(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "Face:side_wall" in context["nodes"]["height"]["affects"]


def test_affects_empty_for_non_geometry_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["nodes"]["inner_top_r"]["affects"] == []


def test_body_only_dag_has_no_handle_nodes(dag_tapered_only):
    context = GraphRetriever().retrieve(dag_tapered_only, "tapered", None)
    assert "lower_attach_z" not in context["nodes"]
    assert "height" in context["nodes"]


# ── templates 서브그래프 (신규) ─────────────────────────────────────────

def test_retrieve_returns_templates_key(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "templates" in context


def test_templates_current_matches_input(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["templates"]["current"] == {"body": "tapered", "handle": "bspline"}


def test_templates_available_contains_known_types(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    avail = context["templates"]["available"]
    assert "tapered" in avail["body"]
    assert "cylinder" in avail["body"]
    assert "bspline" in avail["handle"]
    assert None in avail["handle"]


def test_templates_handle_none_when_no_handle(dag_tapered_only):
    context = GraphRetriever().retrieve(dag_tapered_only, "tapered", None)
    assert context["templates"]["current"]["handle"] is None


# ── intents 서브그래프 (신규) ───────────────────────────────────────────

def test_retrieve_returns_intents_key(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert "intents" in context


def test_intents_create_and_modify_always_available(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["intents"]["create"]["available"] is True
    assert context["intents"]["modify"]["available"] is True


def test_intents_post_process_unavailable_without_selection(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline")
    assert context["intents"]["post_process"]["available"] is False


def test_intents_post_process_available_with_selection(dag_tapered_bspline):
    sel = {"type": "Edge", "index": 3}
    context = GraphRetriever().retrieve(dag_tapered_bspline, "tapered", "bspline", selection=sel)
    assert context["intents"]["post_process"]["available"] is True
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_graph_retriever.py -v --tb=short 2>&1 | tail -20
```

Expected: 기존 13개 `TypeError: retrieve() takes 2 positional arguments`, 신규 8개도 동일 오류.

### 2-B: GraphRetriever 구현

- [ ] **Step 3: graph_retriever.py 전체 교체**

```python
from app.graph.model import DAG
from app.graph.cup_graph import available_templates as _available_templates


class GraphRetriever:
    def retrieve(
        self,
        dag: DAG,
        body_template: str,
        handle_template: str | None,
        selection: dict | None = None,
    ) -> dict:
        return {
            "nodes": self._build_nodes(dag),
            "templates": self._build_templates(body_template, handle_template),
            "intents": self._build_intents(selection),
        }

    # ── nodes ────────────────────────────────────────────────────────────

    def _build_nodes(self, dag: DAG) -> dict:
        result = {}
        for name, node in dag.nodes().items():
            result[name] = {
                "value": node.value,
                "subgraph": node.subgraph,
                "user_facing": node.is_user_facing,
                "controls": self._get_controls(dag, name),
                "constraints": self._get_constraints(dag, name),
                "affects": self._get_affects(dag, name),
            }
        return result

    def _get_controls(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="CONTROLS", source=name)]

    def _get_constraints(self, dag: DAG, name: str) -> list[str]:
        seen: dict[str, None] = {}
        for e in dag.get_edges(type="CONSTRAINS", target=name):
            if "rule" in e.properties:
                seen[e.properties["rule"]] = None
        return list(seen)

    def _get_affects(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="AFFECTS_GEOMETRY", source=name)]

    # ── templates ────────────────────────────────────────────────────────

    def _build_templates(self, body_template: str, handle_template: str | None) -> dict:
        return {
            "current": {"body": body_template, "handle": handle_template},
            "available": _available_templates(),
        }

    # ── intents ──────────────────────────────────────────────────────────

    def _build_intents(self, selection: dict | None) -> dict:
        return {
            "create": {
                "available": True,
                "description": "새 컵 모델을 처음부터 생성",
            },
            "modify": {
                "available": True,
                "description": "현재 모델의 파라미터 수정",
            },
            "post_process": {
                "available": selection is not None,
                "description": "선택된 엣지에 필렛/라운드 적용",
                "requires": "Edge selection",
            },
        }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_graph_retriever.py -v 2>&1 | tail -10
```

Expected: `21 passed`

- [ ] **Step 5: graph_retriever 테스트 단독 확인**

```bash
python -m pytest tests/test_graph_retriever.py -q 2>&1 | tail -5
```

Expected: `21 passed`

> ⚠️ `test_routes.py`는 아직 routes.py 호출부가 구버전(`retrieve(dag)`)이라 TypeError로 실패 — Task 3에서 수정.

- [ ] **Step 6: 커밋**

```bash
git add app/llm/graph_retriever.py tests/test_graph_retriever.py
git commit -m "feat: expand GraphRetriever with templates and intents subgraphs"
```

---

## Task 3: routes.py + parser.py 업데이트

**Files:**
- Modify: `app/api/routes.py` (line 86)
- Modify: `app/llm/parser.py` (system prompt)

### 3-A: routes.py 호출부 업데이트

- [ ] **Step 1: retrieve() 호출 1줄 수정**

`app/api/routes.py` 86번째 줄:

```python
# 변경 전
graph_context = _retriever.retrieve(dag)

# 변경 후
graph_context = _retriever.retrieve(dag, state.body_template, state.handle_template, selection)
```

- [ ] **Step 2: 테스트 통과 확인**

```bash
python -m pytest --tb=short -q 2>&1 | tail -10
```

Expected: `148 passed`

### 3-B: parser.py system prompt 업데이트

- [ ] **Step 3: system prompt의 graph_context 설명 교체**

`app/llm/parser.py`에서 아래 문구를:

```python
The graph_context in each request lists all available parameters with their current
values, constraints, and geometry relationships. Only modify nodes where user_facing is true.
```

다음으로 교체:

```python
The graph_context in each request contains:
- nodes: all parameters with current values, constraints, and geometry relationships
- templates.current: active body/handle template ("tapered"/"cylinder", "bspline"/"ring"/null)
- templates.available: all selectable templates for "create" intent
- intents.{create,modify,post_process}.available: whether each intent is applicable

Only modify nodes where user_facing is true.
Use post_process intent ONLY when intents.post_process.available is true.
```

- [ ] **Step 4: 전체 테스트 최종 확인**

```bash
python -m pytest --tb=short -q 2>&1 | tail -10
```

Expected: `148 passed, 1 warning`

- [ ] **Step 5: 커밋**

```bash
git add app/api/routes.py app/llm/parser.py
git commit -m "feat: wire expanded GraphRetriever into routes and update parser system prompt"
```
