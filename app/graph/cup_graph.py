from app.graph.model import DAG, ParamNode, Edge
from app.features.base import BodyFeature, HandleFeature
from app.features.body.tapered_body import TaperedBody
from app.features.body.cylinder_body import CylinderBody
from app.features.handle.bspline_handle import BSplineHandle
from app.features.handle.ring_handle import RingHandle

# ── 기본값 ────────────────────────────────────────────────────────────────────

TAPERED_BODY_DEFAULTS: dict[str, float] = {
    "height": 90.0,
    "outer_top_r": 40.0,
    "outer_bottom_r": 29.0,
    "thickness": 3.0,
    "bottom_thickness": 3.0,
}

BSPLINE_HANDLE_DEFAULTS: dict[str, float] = {
    "section_width": 14.0,
    "section_height": 8.0,
    "lower_attach_z": TAPERED_BODY_DEFAULTS["height"] * 0.18,
    "upper_attach_z": TAPERED_BODY_DEFAULTS["height"] * 0.80,
    "handle_outward_depth": TAPERED_BODY_DEFAULTS["outer_top_r"] * 0.6,
}

CYLINDER_BODY_DEFAULTS: dict[str, float] = {
    "cylinder_height": 90.0,
    "cylinder_radius": 40.0,
    "cylinder_thickness": 2.5,
    "cylinder_bottom_thickness": 2.5,
}

RING_HANDLE_DEFAULTS: dict[str, float] = {
    "ring_outer_r": 19.5,
    "ring_inner_r": 10.5,
    "ring_width": 15.0,
    "ring_attach_z": CYLINDER_BODY_DEFAULTS["cylinder_height"] * 0.8,
}

# ── feature 레지스트리 ────────────────────────────────────────────────────────

_BODY_FEATURES: dict[str, BodyFeature] = {
    "tapered": TaperedBody(),
    "cylinder": CylinderBody(),
}

_HANDLE_FEATURES: dict[str, HandleFeature] = {
    "bspline": BSplineHandle(),
    "ring": RingHandle(),
}

# ── body sub-graph 빌더 ───────────────────────────────────────────────────────

def _build_tapered_body(dag: DAG, params: dict) -> None:
    p = {**TAPERED_BODY_DEFAULTS, **params}
    dag.add_node(ParamNode("height", p["height"], "body", True))
    dag.add_node(ParamNode("outer_top_r", p["outer_top_r"], "body", True))
    dag.add_node(ParamNode("outer_bottom_r", p["outer_bottom_r"], "body", True))
    dag.add_node(ParamNode("thickness", p["thickness"], "body", True))
    dag.add_node(ParamNode(
        "inner_top_r", 0.0, "body", False,
        formula=lambda d: d.get("outer_top_r") - d.get("thickness"),
        dependencies=["outer_top_r", "thickness"],
    ))
    dag.add_node(ParamNode(
        "inner_bottom_r", 0.0, "body", False,
        formula=lambda d: d.get("outer_bottom_r") - d.get("thickness"),
        dependencies=["outer_bottom_r", "thickness"],
    ))
    dag.add_node(ParamNode("bottom_thickness", p["bottom_thickness"], "body", True))

    for name in ["height", "outer_top_r", "outer_bottom_r", "thickness",
                 "inner_top_r", "inner_bottom_r", "bottom_thickness"]:
        dag.add_edge(Edge("BELONGS_TO", name, "TaperedBody"))


def _build_cylinder_body(dag: DAG, params: dict) -> None:
    p = {**CYLINDER_BODY_DEFAULTS, **params}
    dag.add_node(ParamNode("cylinder_height", p["cylinder_height"], "body", True))
    dag.add_node(ParamNode("cylinder_radius", p["cylinder_radius"], "body", True))
    dag.add_node(ParamNode("cylinder_thickness", p["cylinder_thickness"], "body", True))
    dag.add_node(ParamNode(
        "cylinder_inner_radius", 0.0, "body", False,
        formula=lambda d: d.get("cylinder_radius") - d.get("cylinder_thickness"),
        dependencies=["cylinder_radius", "cylinder_thickness"],
    ))
    dag.add_node(ParamNode("cylinder_bottom_thickness", p["cylinder_bottom_thickness"], "body", True))

    for name in ["cylinder_height", "cylinder_radius", "cylinder_thickness",
                 "cylinder_inner_radius", "cylinder_bottom_thickness"]:
        dag.add_edge(Edge("BELONGS_TO", name, "CylinderBody"))


# ── handle sub-graph 빌더 ─────────────────────────────────────────────────────

def _build_bspline_handle(dag: DAG, params: dict) -> None:
    p = {**BSPLINE_HANDLE_DEFAULTS, **params}
    dag.add_node(ParamNode("section_width", p["section_width"], "handle", True))
    dag.add_node(ParamNode("section_height", p["section_height"], "handle", True))
    dag.add_node(ParamNode("lower_attach_z", p["lower_attach_z"], "handle", True))
    dag.add_node(ParamNode("upper_attach_z", p["upper_attach_z"], "handle", True))
    dag.add_node(ParamNode("handle_outward_depth", p["handle_outward_depth"], "handle", True))

    for name in ["section_width", "section_height", "lower_attach_z",
                 "upper_attach_z", "handle_outward_depth"]:
        dag.add_edge(Edge("BELONGS_TO", name, "BSplineHandle"))


def _build_ring_handle(dag: DAG, params: dict) -> None:
    p = {**RING_HANDLE_DEFAULTS, **params}
    dag.add_node(ParamNode("ring_outer_r", p["ring_outer_r"], "handle", True))
    dag.add_node(ParamNode("ring_inner_r", p["ring_inner_r"], "handle", True))
    dag.add_node(ParamNode("ring_width", p["ring_width"], "handle", True))
    dag.add_node(ParamNode("ring_attach_z", p["ring_attach_z"], "handle", True))

    for name in ["ring_outer_r", "ring_inner_r", "ring_width", "ring_attach_z"]:
        dag.add_edge(Edge("BELONGS_TO", name, "RingHandle"))


# ── 타입별 엣지 추가 ──────────────────────────────────────────────────────────

# 템플릿을 가로지르는 의미적 동치 쌍. 현재 DAG에 두 노드가 모두 없어도 등록.
_EQUIVALENT_PAIRS: list[tuple[str, str, str]] = [
    ("height",           "cylinder_height",           "컵 높이"),
    ("thickness",        "cylinder_thickness",         "벽 두께"),
    ("bottom_thickness", "cylinder_bottom_thickness",  "바닥 두께"),
    ("outer_top_r",      "cylinder_radius",            "몸통 윗면 반경"),
]


def _add_equivalences(dag: DAG) -> None:
    for a, b, concept in _EQUIVALENT_PAIRS:
        dag.add_edge(Edge("EQUIVALENT_TO", a, b, {"concept": concept}))
        dag.add_edge(Edge("EQUIVALENT_TO", b, a, {"concept": concept}))


def _add_constraints(dag: DAG, body_template: str, handle_template: str | None) -> None:
    if body_template == "tapered":
        dag.add_edge(Edge("CONSTRAINS", "min_height", "height",
                          {"rule": "height >= 5.0",
                           "description": "높이는 최소 5mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_outer_top_r", "outer_top_r",
                          {"rule": "outer_top_r >= 7.0",
                           "description": "윗면 반경은 최소 7mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_outer_bottom_r", "outer_bottom_r",
                          {"rule": "outer_bottom_r >= 7.0",
                           "description": "아랫면 반경은 최소 7mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_thickness", "thickness",
                          {"rule": "thickness >= 3.0",
                           "description": "벽 두께는 최소 3mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_bottom_thickness", "bottom_thickness",
                          {"rule": "bottom_thickness >= 3.0",
                           "description": "바닥 두께는 최소 3mm 이상이어야 합니다"}))
        for p in ["outer_top_r", "thickness"]:
            dag.add_edge(Edge("CONSTRAINS", "positive_inner_top_r", p,
                              {"rule": "outer_top_r > thickness",
                               "description": "안쪽 윗면 반경이 0보다 커야 함"}))
        for p in ["outer_bottom_r", "thickness"]:
            dag.add_edge(Edge("CONSTRAINS", "positive_inner_bottom_r", p,
                              {"rule": "outer_bottom_r > thickness",
                               "description": "안쪽 아랫면 반경이 0보다 커야 함"}))

    if body_template == "cylinder":
        dag.add_edge(Edge("CONSTRAINS", "min_cylinder_height", "cylinder_height",
                          {"rule": "cylinder_height >= 5.0",
                           "description": "높이는 최소 5mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_cylinder_radius", "cylinder_radius",
                          {"rule": "cylinder_radius >= 7.0",
                           "description": "반경은 최소 7mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_cylinder_thickness", "cylinder_thickness",
                          {"rule": "cylinder_thickness >= 3.0",
                           "description": "벽 두께는 최소 3mm 이상이어야 합니다"}))
        dag.add_edge(Edge("CONSTRAINS", "min_cylinder_bottom_thickness", "cylinder_bottom_thickness",
                          {"rule": "cylinder_bottom_thickness >= 3.0",
                           "description": "바닥 두께는 최소 3mm 이상이어야 합니다"}))
        for p in ["cylinder_radius", "cylinder_thickness"]:
            dag.add_edge(Edge("CONSTRAINS", "positive_inner_radius", p,
                              {"rule": "cylinder_radius > cylinder_thickness",
                               "description": "안쪽 반경이 0보다 커야 함"}))

    if handle_template == "bspline":
        for p in ["lower_attach_z", "upper_attach_z"]:
            dag.add_edge(Edge("CONSTRAINS", "attach_z_order", p,
                              {"rule": "lower_attach_z < upper_attach_z",
                               "description": "손잡이 하단 부착점이 상단보다 낮아야 함"}))
        h = "height" if body_template == "tapered" else "cylinder_height"
        for p in ["upper_attach_z", h]:
            dag.add_edge(Edge("CONSTRAINS", "attach_within_body", p,
                              {"rule": f"upper_attach_z < {h}",
                               "description": "손잡이 상단 부착점이 컵 높이를 넘을 수 없음"}))

    if handle_template == "ring":
        for p in ["ring_inner_r", "ring_outer_r"]:
            dag.add_edge(Edge("CONSTRAINS", "ring_r_order", p,
                              {"rule": "ring_inner_r < ring_outer_r",
                               "description": "링 안쪽 반경이 바깥 반경보다 작아야 함"}))
        h = "cylinder_height" if body_template == "cylinder" else "height"
        for p in ["ring_attach_z", h]:
            dag.add_edge(Edge("CONSTRAINS", "ring_within_body", p,
                              {"rule": f"ring_attach_z < {h}",
                               "description": "링 부착 위치가 컵 높이 안에 있어야 함"}))


def _add_geometry_relations(dag: DAG, body_template: str, handle_template: str | None) -> None:
    if body_template == "tapered":
        for p in ["height", "outer_top_r", "outer_bottom_r"]:
            dag.add_edge(Edge("AFFECTS_GEOMETRY", p, "Face:side_wall"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "thickness",        "Face:inner_wall"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "bottom_thickness", "Face:bottom"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "outer_top_r",      "Edge:top_rim"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "outer_bottom_r",   "Edge:bottom_rim"))

    if body_template == "cylinder":
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "cylinder_height",           "Face:side_wall"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "cylinder_radius",           "Face:side_wall"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "cylinder_radius",           "Edge:top_rim"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "cylinder_thickness",        "Face:inner_wall"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "cylinder_bottom_thickness", "Face:bottom"))

    if handle_template == "bspline":
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "lower_attach_z",      "Edge:handle_lower_junction"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "upper_attach_z",      "Edge:handle_upper_junction"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "section_width",       "Face:handle_section"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "section_height",      "Face:handle_section"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "handle_outward_depth","Face:handle_section"))

    if handle_template == "ring":
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "ring_outer_r",  "Face:ring_outer"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "ring_inner_r",  "Face:ring_inner"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "ring_width",    "Face:ring_side"))
        dag.add_edge(Edge("AFFECTS_GEOMETRY", "ring_attach_z", "Edge:ring_junction"))


# ── 공개 API ──────────────────────────────────────────────────────────────────

def build_dag(body_template: str, handle_template: str | None, params: dict | None = None) -> DAG:
    """
    body_template: "tapered" | "cylinder"
    handle_template: "bspline" | "ring" | None
    params: 사용자 입력값 오버라이드 (user-facing 파라미터만 유효)

    joint sub-graph는 body/handle feature 인스턴스가 직접 조립.
    새 body나 handle을 추가해도 cup_graph.py 수정 불필요.
    """
    dag = DAG()
    p = params or {}

    if body_template not in _BODY_FEATURES:
        raise ValueError(f"Unknown body_template: {body_template}")
    if handle_template is not None and handle_template not in _HANDLE_FEATURES:
        raise ValueError(f"Unknown handle_template: {handle_template}")

    body_feature = _BODY_FEATURES[body_template]

    # body sub-graph
    if body_template == "tapered":
        _build_tapered_body(dag, p)
    else:
        _build_cylinder_body(dag, p)

    # handle sub-graph + joint (동적 조립)
    if handle_template is not None:
        handle_feature = _HANDLE_FEATURES[handle_template]

        if handle_template == "bspline":
            _build_bspline_handle(dag, p)
        else:
            _build_ring_handle(dag, p)

        # body 인터페이스를 handle에 주입 → handle이 joint 노드 직접 조립
        handle_feature.build_joint_nodes(dag, body_feature)

    # 타입별 엣지
    _add_equivalences(dag)
    _add_constraints(dag, body_template, handle_template)
    _add_geometry_relations(dag, body_template, handle_template)

    return dag
