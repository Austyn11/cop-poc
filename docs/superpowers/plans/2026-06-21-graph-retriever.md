# Graph Retriever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DAG에서 파라미터 노드·엣지 정보를 구조화된 JSON으로 추출하는 `GraphRetriever` 레이어를 도입하고, `parse_command`에 현재 flat params 대신 graph context를 주입한다.

**Architecture:** `app/llm/graph_retriever.py`에 `GraphRetriever` 클래스를 추가한다. `routes.py`에서 `parse_command` 호출 전에 DAG를 빌드하고 `retrieve(dag)`로 context를 생성해 LLM user message에 주입한다. `parse_command` 시그니처는 `current_params: dict` → `graph_context: dict`로 변경한다.

**Tech Stack:** Python, `app.graph.model.DAG` (`get_edges`, `_nodes`), pytest, unittest.mock

---

## 파일 구조

| 파일 | 변경 |
|---|---|
| `app/llm/graph_retriever.py` | 신규 생성 |
| `tests/test_graph_retriever.py` | 신규 생성 |
| `app/llm/parser.py` | 시그니처 변경, system prompt 수정 |
| `tests/test_parser.py` | 시그니처 변경 반영 |
| `app/api/routes.py` | Retriever 호출 추가, dag 빌드 순서 변경 |

---

## Task 1: GraphRetriever 클래스 구현

**Files:**
- Create: `app/llm/graph_retriever.py`
- Create: `tests/test_graph_retriever.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_graph_retriever.py
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


def test_retrieve_returns_nodes_key(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "nodes" in context


def test_retrieve_contains_all_dag_nodes(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    nodes = context["nodes"]
    for name in dag_tapered_bspline._nodes:
        assert name in nodes, f"Missing node: {name}"


def test_node_has_required_fields(dag_tapered_bspline):
    node = GraphRetriever().retrieve(dag_tapered_bspline)["nodes"]["height"]
    assert "value" in node
    assert "subgraph" in node
    assert "user_facing" in node
    assert "controls" in node
    assert "constraints" in node
    assert "affects" in node


def test_node_value_matches_dag(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert context["nodes"]["height"]["value"] == dag_tapered_bspline.get("height")


def test_user_facing_true_for_editable_param(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert context["nodes"]["height"]["user_facing"] is True


def test_user_facing_false_for_derived_param(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert context["nodes"]["inner_top_r"]["user_facing"] is False


def test_controls_field_lists_derived_nodes(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "inner_top_r" in context["nodes"]["outer_top_r"]["controls"]


def test_controls_empty_for_leaf_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    # inner_top_r는 다른 노드를 control하지 않음
    assert context["nodes"]["inner_top_r"]["controls"] == []


def test_constraints_field_contains_rule_string(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "height >= 5.0" in context["nodes"]["height"]["constraints"]


def test_constraints_empty_for_unconstrained_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    # inner_top_r에는 직접 걸린 CONSTRAINS 엣지가 없음
    assert context["nodes"]["inner_top_r"]["constraints"] == []


def test_affects_field_lists_geometry_elements(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "Face:side_wall" in context["nodes"]["height"]["affects"]


def test_affects_empty_for_non_geometry_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    # inner_top_r는 AFFECTS_GEOMETRY 엣지가 없음
    assert context["nodes"]["inner_top_r"]["affects"] == []


def test_body_only_dag_has_no_handle_nodes(dag_tapered_only):
    context = GraphRetriever().retrieve(dag_tapered_only)
    assert "lower_attach_z" not in context["nodes"]
    assert "height" in context["nodes"]
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
pytest tests/test_graph_retriever.py -v
```

예상: `ModuleNotFoundError: No module named 'app.llm.graph_retriever'`

- [ ] **Step 3: GraphRetriever 구현**

```python
# app/llm/graph_retriever.py
from app.graph.model import DAG


class GraphRetriever:
    def retrieve(self, dag: DAG) -> dict:
        return {"nodes": self._build_nodes(dag)}

    def _build_nodes(self, dag: DAG) -> dict:
        result = {}
        for name, node in dag._nodes.items():
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
        return [
            e.properties["rule"]
            for e in dag.get_edges(type="CONSTRAINS", target=name)
            if "rule" in e.properties
        ]

    def _get_affects(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="AFFECTS_GEOMETRY", source=name)]
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```bash
pytest tests/test_graph_retriever.py -v
```

예상: 14개 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/llm/graph_retriever.py tests/test_graph_retriever.py
git commit -m "feat: add GraphRetriever to extract DAG context for LLM"
```

---

## Task 2: parse_command 시그니처 변경

**Files:**
- Modify: `app/llm/parser.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: test_parser.py 업데이트**

`parse_command`의 두 번째 인자를 모든 테스트에서 `graph_context` dict로 교체한다.  
LLM이 mock되므로 graph_context 내용은 테스트 결과에 영향 없음 → `{"nodes": {}}` 사용.

```python
# tests/test_parser.py
import json
from unittest.mock import MagicMock, patch
from app.llm.parser import parse_command


def _mock_response(text: str):
    """OpenAI ChatCompletion 응답 구조 mock."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = text
    return mock


def _patch(text: str):
    return patch(
        "app.llm.parser.client.chat.completions.create",
        return_value=_mock_response(text),
    )


_CTX = {"nodes": {}}  # LLM이 mock되므로 내용 무관


def test_parse_modify_single_param():
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 90}]}'
    with _patch(resp):
        result = parse_command("컵 높이를 90으로 바꿔줘", _CTX)
    assert result["intent"] == "modify"
    assert result["changes"] == [{"param": "height", "value": 90}]


def test_parse_modify_multiple_params():
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "outer_top_r", "value": 45}, {"param": "height", "value": 80}]}'
    with _patch(resp):
        result = parse_command("입구 반지름 45로, 높이 80으로", _CTX)
    assert result["intent"] == "modify"
    assert len(result["changes"]) == 2
    assert {"param": "outer_top_r", "value": 45} in result["changes"]


def test_parse_create_tapered_bspline():
    resp = '{"intent": "create", "body_template": "tapered", "handle_template": "bspline", "changes": []}'
    with _patch(resp):
        result = parse_command("테이퍼드 컵 만들어줘", _CTX)
    assert result["intent"] == "create"
    assert result["body_template"] == "tapered"
    assert result["handle_template"] == "bspline"


def test_parse_create_cylinder_ring():
    resp = '{"intent": "create", "body_template": "cylinder", "handle_template": "ring", "changes": []}'
    with _patch(resp):
        result = parse_command("원통형 컵 링 손잡이로 만들어줘", _CTX)
    assert result["intent"] == "create"
    assert result["body_template"] == "cylinder"
    assert result["handle_template"] == "ring"


def test_parse_extracts_json_from_prose():
    """LLM이 JSON 앞뒤에 텍스트를 붙여도 파싱 성공."""
    resp = 'Here is the result: {"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 100}]} Done.'
    with _patch(resp):
        result = parse_command("높이 100", _CTX)
    assert result["intent"] == "modify"
    assert result["changes"][0]["value"] == 100


def test_parse_defaults_on_missing_fields():
    """intent 필드만 있어도 나머지 필드는 기본값으로 채워짐."""
    resp = '{"intent": "modify", "changes": [{"param": "height", "value": 80}]}'
    with _patch(resp):
        result = parse_command("높이 80", _CTX)
    assert result["body_template"] is None
    assert result["handle_template"] is None


def test_parse_op_set_absolute():
    """'10mm로 수정해줘' → op: set, 절댓값."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "ring_outer_r", "op": "set", "value": 10}]}'
    with _patch(resp):
        result = parse_command("원형 손잡이 지름을 10mm로 수정해줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "set"
    assert change["value"] == 10
    assert change["param"] == "ring_outer_r"


def test_parse_op_delta_positive():
    """'15mm 더 크게' → op: delta, 양수."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "ring_outer_r", "op": "delta", "value": 15}]}'
    with _patch(resp):
        result = parse_command("원형 손잡이 지름을 15mm 더 크게 해줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "delta"
    assert change["value"] == 15


def test_parse_op_delta_negative():
    """'5mm 작게' → op: delta, 음수."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "op": "delta", "value": -5}]}'
    with _patch(resp):
        result = parse_command("높이를 5mm 줄여줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "delta"
    assert change["value"] == -5


def test_parse_post_process_fillet():
    """selection 컨텍스트 + 필렛 명령 → post_process intent."""
    resp = '{"intent": "post_process", "operation": "fillet_edge", "radius": 2.0}'
    with _patch(resp):
        result = parse_command(
            "선택된 엣지에 필렛 2 넣어줘",
            _CTX,
            selection={"type": "Edge", "index": 1},
        )
    assert result["intent"] == "post_process"
    assert result["operation"] == "fillet_edge"
    assert result["radius"] == 2.0


def test_parse_op_missing_passes_through():
    """LLM이 op 필드를 빠뜨려도 파서는 그대로 통과 (라우트에서 기본값 처리)."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 90}]}'
    with _patch(resp):
        result = parse_command("높이 90", _CTX)
    change = result["changes"][0]
    assert "value" in change
    assert change["value"] == 90
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
pytest tests/test_parser.py -v
```

예상: `TypeError: parse_command() takes 2 positional arguments but got ...` 또는 타입 불일치로 FAIL

- [ ] **Step 3: parser.py 업데이트**

```python
# app/llm/parser.py
import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy-key-for-tests"))

_SYSTEM_PROMPT = """You interpret natural language commands for a mug cup 3D modeling system.

Determine the user's intent and return a JSON object:

1. If the user wants to CREATE a new cup model:
{
  "intent": "create",
  "body_template": "tapered" | "cylinder",
  "handle_template": "bspline" | "ring" | null,
  "changes": []
}

2. If the user wants to MODIFY existing parameters:
{
  "intent": "modify",
  "body_template": null,
  "handle_template": null,
  "changes": [{"param": "param_name", "op": "set"|"delta", "value": number}]
}

op rules:
- "set"   → absolute target value  (e.g. "10mm로 바꿔줘", "set to 50", "make it 30mm")
- "delta" → relative change        (e.g. "15mm 더 크게", "5mm 줄여줘", "increase by 10")
For "delta", value is SIGNED: positive = increase, negative = decrease.
Example: "5mm 작게" → {"op": "delta", "value": -5}
CRITICAL: "X으로/로 수정/변경/바꿔줘" is ALWAYS op:"set" even if X is negative.
  "-10으로 바꿔줘" → {"op": "set", "value": -10}  (NOT delta)

3. If the user wants to apply a POST-PROCESS operation (selection context is provided):
{
  "intent": "post_process",
  "operation": "fillet_edge",
  "radius": number
}
Post-process keywords: fillet/필렛/라운드/round → "fillet_edge"
Use this intent ONLY when a selection context (Edge index) is provided.

The graph_context in each request lists all available parameters with their current
values, constraints, and geometry relationships. Only modify nodes where user_facing is true.

Creation keywords (any language): make, create, generate, new, 만들어, 생성, 새로운, 컵, 머그
Body types: tapered/테이퍼드=tapered, cylinder/원통=cylinder (default: tapered)
Handle types: bspline/손잡이=bspline, ring/링=ring, none/없는=null (default: bspline)

Return ONLY the JSON object, no explanation."""


def parse_command(
    command: str,
    graph_context: dict,
    selection: dict | None = None,
) -> dict:
    """자연어 명령을 파싱하여 intent와 변경 사항을 반환."""
    user_content = f"Current graph state:\n{json.dumps(graph_context, indent=2)}\n"
    if selection:
        user_content += f"Selection: {selection['type']} index {selection['index']}\n"
    user_content += f"\nCommand: {command}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=256,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    text = response.choices[0].message.content.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result = json.loads(text[start:end])
    result.setdefault("intent", "modify")
    result.setdefault("body_template", None)
    result.setdefault("handle_template", None)
    result.setdefault("changes", [])
    return result
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```bash
pytest tests/test_parser.py -v
```

예상: 11개 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/llm/parser.py tests/test_parser.py
git commit -m "feat: update parse_command to accept graph_context instead of flat params"
```

---

## Task 3: routes.py 통합

**Files:**
- Modify: `app/api/routes.py`

- [ ] **Step 1: routes.py 전체 교체**

핵심 변경:
- `GraphRetriever` import 추가
- 모듈 레벨 `_retriever` 싱글턴 추가
- `generate()` 함수 상단에서 DAG를 먼저 빌드하고 graph context 추출
- `parse_command` 호출 인자를 `graph_context`로 변경
- `post_process`, `modify` 분기에서 이미 빌드된 `dag` 재사용 (중복 빌드 제거)

```python
# app/api/routes.py
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize, recompute
from app.graph.validator import check_constraints
from app.codegen.renderer import render
from app.llm.parser import parse_command
from app.llm.graph_retriever import GraphRetriever

router = APIRouter(prefix="/api")

_DEFAULT_BODY = "tapered"
_DEFAULT_HANDLE = "bspline"
_retriever = GraphRetriever()


class ModelState(BaseModel):
    body_template: str
    handle_template: Optional[str] = None
    params: dict = {}
    post_processing: list[dict] = []


class Selection(BaseModel):
    type: str   # "Edge" | "Face"
    index: int


class GenerateRequest(BaseModel):
    command: str
    state: Optional[ModelState] = None
    selection: Optional[Selection] = None


class GraphNode(BaseModel):
    name: str
    value: float
    user_facing: bool


class GenerateResponse(BaseModel):
    code: str
    state: ModelState
    diff: dict
    graph: dict[str, list[GraphNode]]
    edges: list[dict]
    violations: list[str] = []
    message: str = ""


def _extract_graph(dag) -> dict[str, list[GraphNode]]:
    """DAG 노드를 서브그래프별로 묶어 반환."""
    groups: dict[str, list[GraphNode]] = {}
    for node in dag._nodes.values():
        groups.setdefault(node.subgraph, []).append(
            GraphNode(name=node.name, value=node.value, user_facing=node.is_user_facing)
        )
    return groups


def _extract_edges(dag) -> list[dict]:
    return [
        {"type": e.type, "source": e.source, "target": e.target, "properties": e.properties}
        for e in dag._edges
    ]


def _build_and_init(body_template: str, handle_template: Optional[str], params: dict):
    dag = build_dag(body_template, handle_template, params)
    initialize(dag)
    return dag


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    state = req.state or ModelState(body_template=_DEFAULT_BODY, handle_template=_DEFAULT_HANDLE)
    selection = req.selection.model_dump() if req.selection else None

    # 현재 state로 DAG 빌드 → graph context 추출 → LLM 호출
    try:
        dag = _build_and_init(state.body_template, state.handle_template, state.params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    graph_context = _retriever.retrieve(dag)
    parsed = parse_command(req.command, graph_context, selection)
    intent = parsed.get("intent", "modify")

    if intent == "create":
        body_template = parsed.get("body_template") or _DEFAULT_BODY
        handle_template = parsed.get("handle_template", _DEFAULT_HANDLE)
        try:
            dag = _build_and_init(body_template, handle_template, {})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        code = render(body_template, handle_template, dag)
        return GenerateResponse(
            code=code,
            state=ModelState(
                body_template=body_template,
                handle_template=handle_template,
                params=dag.get_all(),
                post_processing=[],
            ),
            diff={"changed": [], "recomputed": []},
            graph=_extract_graph(dag),
            edges=_extract_edges(dag),
            message="생성이 완료되었습니다.",
        )

    if intent == "post_process":
        operation = parsed.get("operation")
        radius = float(parsed.get("radius", 1.0))
        post_processing = list(state.post_processing)
        if operation == "fillet_edge" and req.selection and req.selection.type == "Edge":
            post_processing.append({
                "op": "fillet_edge",
                "index": req.selection.index,
                "radius": radius,
            })
        code = render(state.body_template, state.handle_template, dag, post_processing)
        return GenerateResponse(
            code=code,
            state=ModelState(
                body_template=state.body_template,
                handle_template=state.handle_template,
                params=dag.get_all(),
                post_processing=post_processing,
            ),
            diff={"changed": [], "recomputed": []},
            graph=_extract_graph(dag),
            edges=_extract_edges(dag),
            message="수정이 완료되었습니다.",
        )

    # intent == "modify"
    proposed: dict[str, float] = {}
    for change in parsed.get("changes", []):
        param = change.get("param")
        op = change.get("op", "set")
        value = change.get("value")
        if param and param in dag._nodes and dag._nodes[param].is_user_facing:
            proposed[param] = (
                dag.get(param) + float(value) if op == "delta" else float(value)
            )

    violations = check_constraints(dag, proposed)
    if violations:
        code = render(state.body_template, state.handle_template, dag, state.post_processing)
        descriptions = [v["description"] for v in violations]
        return GenerateResponse(
            code=code,
            state=state,
            diff={"changed": [], "recomputed": []},
            graph=_extract_graph(dag),
            edges=_extract_edges(dag),
            violations=descriptions,
            message="오류가 발생했습니다.\n" + "\n".join(f"- {d}" for d in descriptions),
        )

    changed_names = list(proposed.keys())
    for param, new_value in proposed.items():
        dag.set(param, new_value)

    _, recomputed_names = recompute(dag, changed_names)
    code = render(state.body_template, state.handle_template, dag, state.post_processing)

    return GenerateResponse(
        code=code,
        state=ModelState(
            body_template=state.body_template,
            handle_template=state.handle_template,
            params=dag.get_all(),
            post_processing=state.post_processing,
        ),
        diff={"changed": changed_names, "recomputed": recomputed_names},
        graph=_extract_graph(dag),
        edges=_extract_edges(dag),
        message="수정이 완료되었습니다.",
    )
```

- [ ] **Step 2: 전체 테스트 스위트 실행**

```bash
pytest -v
```

예상: 전체 PASS (기존 routes 테스트 포함)

- [ ] **Step 3: 커밋**

```bash
git add app/api/routes.py
git commit -m "feat: integrate GraphRetriever into generate endpoint"
```
