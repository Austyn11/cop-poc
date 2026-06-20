from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize, recompute
from app.graph.validator import check_constraints
from app.codegen.renderer import render
from app.llm.parser import parse_command

router = APIRouter(prefix="/api")

_DEFAULT_BODY = "tapered"
_DEFAULT_HANDLE = "bspline"


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

    parsed = parse_command(req.command, state.params, selection)
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
        try:
            dag = _build_and_init(state.body_template, state.handle_template, state.params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
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
    try:
        dag = _build_and_init(state.body_template, state.handle_template, state.params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 적용 예정 값 계산 (아직 DAG에 반영 안 함)
    proposed: dict[str, float] = {}
    for change in parsed.get("changes", []):
        param = change.get("param")
        op = change.get("op", "set")
        value = change.get("value")
        if param and param in dag._nodes and dag._nodes[param].is_user_facing:
            proposed[param] = (
                dag.get(param) + float(value) if op == "delta" else float(value)
            )

    # 제약 위반 검사 — 위반 시 현재 상태 그대로 반환
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

    # 위반 없음 — DAG 업데이트 및 재계산
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
