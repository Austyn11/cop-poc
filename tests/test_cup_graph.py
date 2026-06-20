import pytest
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize, recompute


def _edge_set(dag, *, type, source=None, target=None):
    """엣지 필터링 헬퍼 — source/target 집합 반환."""
    edges = dag.get_edges(type=type, source=source, target=target)
    if source is None:
        return {e.source for e in edges}
    return {e.target for e in edges}


# ── Tapered body ──────────────────────────────────────────────

def test_tapered_body_defaults():
    dag = build_dag("tapered", None)
    initialize(dag)
    assert dag.get("height") == 70.0
    assert dag.get("outer_top_r") == 40.0
    assert dag.get("inner_top_r") == pytest.approx(40.0 - 3.0)
    assert dag.get("inner_bottom_r") == pytest.approx(29.0 - 3.0)


def test_tapered_body_param_override():
    dag = build_dag("tapered", None, {"height": 90.0})
    initialize(dag)
    assert dag.get("height") == 90.0


def test_tapered_no_handle_has_no_joint_nodes():
    dag = build_dag("tapered", None)
    assert "lower_attach_z" not in dag._nodes


# ── Tapered + BSpline joint ───────────────────────────────────

def test_tapered_bspline_attach_z_defaults():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    assert dag.get("lower_attach_z") == pytest.approx(12.6)
    assert dag.get("upper_attach_z") == pytest.approx(56.0)


def test_tapered_bspline_attach_z_is_user_facing():
    dag = build_dag("tapered", "bspline")
    assert dag._nodes["lower_attach_z"].is_user_facing
    assert dag._nodes["upper_attach_z"].is_user_facing
    assert dag._nodes["handle_outward_depth"].is_user_facing


def test_tapered_bspline_lower_outer_r():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    lz = dag.get("lower_attach_z")  # 12.6
    bot, top, h = 29.0, 40.0, 70.0
    expected = bot + (top - bot) * (lz / h)
    assert dag.get("lower_outer_r") == pytest.approx(expected)


def test_tapered_bspline_lower_attach_x():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    expected = -dag.get("lower_outer_r") + dag.get("penetration_depth")
    assert dag.get("lower_attach_x") == pytest.approx(expected)


def test_attach_z_fixed_when_height_changes():
    """height 변경 시 lower_attach_z는 고정, lower_outer_r·lower_attach_x는 재계산."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    lz_before = dag.get("lower_attach_z")

    dag.set("height", 90.0)
    _, recomputed = recompute(dag, ["height"])

    assert dag.get("lower_attach_z") == pytest.approx(lz_before)  # 고정
    assert "lower_attach_z" not in recomputed
    assert "lower_outer_r" in recomputed
    assert "lower_attach_x" in recomputed
    assert "upper_attach_x" in recomputed


def test_joint_recomputes_when_outer_top_r_changes():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    old_lower_outer_r = dag.get("lower_outer_r")
    dag.set("outer_top_r", 50.0)
    recompute(dag, ["outer_top_r"])
    assert dag.get("lower_outer_r") != pytest.approx(old_lower_outer_r)


# ── bottom_thickness (tapered) ───────────────────────────────

def test_tapered_bottom_thickness_default():
    dag = build_dag("tapered", None)
    initialize(dag)
    assert dag.get("bottom_thickness") == pytest.approx(3.0)


def test_tapered_bottom_thickness_is_user_facing():
    dag = build_dag("tapered", None)
    assert dag._nodes["bottom_thickness"].is_user_facing


def test_tapered_bottom_thickness_independent_from_thickness():
    """thickness 변경 시 bottom_thickness는 영향받지 않음."""
    dag = build_dag("tapered", None)
    initialize(dag)
    dag.set("thickness", 5.0)
    _, recomputed = recompute(dag, ["thickness"])
    assert dag.get("bottom_thickness") == pytest.approx(3.0)
    assert "bottom_thickness" not in recomputed


def test_tapered_bottom_thickness_override():
    dag = build_dag("tapered", None, {"bottom_thickness": 8.0})
    initialize(dag)
    assert dag.get("bottom_thickness") == pytest.approx(8.0)


# ── Cylinder body ─────────────────────────────────────────────

def test_cylinder_body_defaults():
    dag = build_dag("cylinder", None)
    initialize(dag)
    assert dag.get("cylinder_radius") == 40.0
    assert dag.get("cylinder_inner_radius") == pytest.approx(40.0 - 2.5)


# ── cylinder_bottom_thickness ────────────────────────────────

def test_cylinder_bottom_thickness_default():
    dag = build_dag("cylinder", None)
    initialize(dag)
    assert dag.get("cylinder_bottom_thickness") == pytest.approx(2.5)


def test_cylinder_bottom_thickness_is_user_facing():
    dag = build_dag("cylinder", None)
    assert dag._nodes["cylinder_bottom_thickness"].is_user_facing


def test_cylinder_bottom_thickness_independent_from_thickness():
    """cylinder_thickness 변경 시 cylinder_bottom_thickness는 영향받지 않음."""
    dag = build_dag("cylinder", None)
    initialize(dag)
    dag.set("cylinder_thickness", 5.0)
    _, recomputed = recompute(dag, ["cylinder_thickness"])
    assert dag.get("cylinder_bottom_thickness") == pytest.approx(2.5)
    assert "cylinder_bottom_thickness" not in recomputed


def test_cylinder_bottom_thickness_override():
    dag = build_dag("cylinder", None, {"cylinder_bottom_thickness": 6.0})
    initialize(dag)
    assert dag.get("cylinder_bottom_thickness") == pytest.approx(6.0)


# ── Cylinder + Ring joint ─────────────────────────────────────

def test_ring_attach_z_default():
    """ring_attach_z 기본값 = cylinder_height * 0.8 = 72.0."""
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    assert dag.get("ring_attach_z") == pytest.approx(72.0)


def test_ring_attach_z_is_user_facing():
    dag = build_dag("cylinder", "ring")
    assert dag._nodes["ring_attach_z"].is_user_facing


def test_ring_attach_z_fixed_when_height_changes():
    """cylinder_height 변경 시 ring_attach_z는 고정, ring_attach_x는 재계산."""
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    rz_before = dag.get("ring_attach_z")

    dag.set("cylinder_height", 100.0)
    _, recomputed = recompute(dag, ["cylinder_height"])

    assert dag.get("ring_attach_z") == pytest.approx(rz_before)  # 고정
    assert "ring_attach_z" not in recomputed


def test_ring_attach_x_derived_from_cylinder_radius():
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    r = dag.get("cylinder_radius")
    outer_r = dag.get("ring_outer_r")
    thickness = dag.get("cylinder_thickness")
    expected = r + outer_r - thickness * 0.75
    assert dag.get("ring_attach_x") == pytest.approx(expected)


def test_ring_attach_x_recomputes_when_radius_changes():
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    old_x = dag.get("ring_attach_x")
    dag.set("cylinder_radius", 50.0)
    recompute(dag, ["cylinder_radius"])
    assert dag.get("ring_attach_x") != pytest.approx(old_x)


# ── CONTROLS 엣지 ─────────────────────────────────────────────

def test_controls_edges_from_thickness():
    """thickness → inner_top_r, inner_bottom_r CONTROLS 엣지 자동 생성."""
    dag = build_dag("tapered", None)
    targets = _edge_set(dag, type="CONTROLS", source="thickness")
    assert "inner_top_r" in targets
    assert "inner_bottom_r" in targets


def test_controls_edges_from_outer_top_r():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    targets = _edge_set(dag, type="CONTROLS", source="outer_top_r")
    assert "inner_top_r" in targets
    assert "lower_outer_r" in targets
    assert "upper_outer_r" in targets


def test_controls_no_edge_for_user_facing():
    """사용자 파라미터 노드는 dependency가 없으므로 CONTROLS 소스로 자동 등록되지 않음."""
    dag = build_dag("tapered", None)
    # height는 formula 없음 → target으로 들어오는 CONTROLS 엣지가 없음
    assert dag.get_edges(type="CONTROLS", target="height") == []


# ── BELONGS_TO 엣지 ───────────────────────────────────────────

def test_belongs_to_tapered_body_nodes():
    dag = build_dag("tapered", None)
    targets = _edge_set(dag, type="BELONGS_TO", source="height")
    assert "TaperedBody" in targets


def test_belongs_to_bspline_handle_nodes():
    dag = build_dag("tapered", "bspline")
    for name in ["section_width", "lower_attach_z", "handle_span_z", "lower_attach_x"]:
        targets = _edge_set(dag, type="BELONGS_TO", source=name)
        assert "BSplineHandle" in targets, f"{name} 이 BSplineHandle에 속하지 않음"


def test_belongs_to_ring_handle_nodes():
    dag = build_dag("cylinder", "ring")
    for name in ["ring_outer_r", "ring_attach_z", "ring_attach_x"]:
        targets = _edge_set(dag, type="BELONGS_TO", source=name)
        assert "RingHandle" in targets, f"{name} 이 RingHandle에 속하지 않음"


# ── EQUIVALENT_TO 엣지 ────────────────────────────────────────

def test_equivalent_to_height_cylinder_height():
    """height ↔ cylinder_height 양방향 동치 엣지."""
    dag = build_dag("tapered", None)
    assert "cylinder_height" in _edge_set(dag, type="EQUIVALENT_TO", source="height")
    assert "height" in _edge_set(dag, type="EQUIVALENT_TO", source="cylinder_height")


def test_equivalent_to_has_concept_property():
    dag = build_dag("tapered", None)
    edges = dag.get_edges(type="EQUIVALENT_TO", source="height")
    assert any(e.properties.get("concept") for e in edges)


def test_equivalent_to_bottom_thickness():
    dag = build_dag("tapered", None)
    assert "cylinder_bottom_thickness" in _edge_set(
        dag, type="EQUIVALENT_TO", source="bottom_thickness"
    )


# ── CONSTRAINS 엣지 ───────────────────────────────────────────

def test_constrains_tapered_inner_r():
    """테이퍼드 바디: 벽 두께 초과 금지 제약."""
    dag = build_dag("tapered", None)
    sources = _edge_set(dag, type="CONSTRAINS", target="thickness")
    assert "positive_inner_top_r" in sources
    assert "positive_inner_bottom_r" in sources


def test_constrains_bspline_attach_order():
    """BSpline: lower_attach_z < upper_attach_z 제약."""
    dag = build_dag("tapered", "bspline")
    sources = _edge_set(dag, type="CONSTRAINS", target="lower_attach_z")
    assert "attach_z_order" in sources


def test_constrains_ring_r_order():
    dag = build_dag("cylinder", "ring")
    sources = _edge_set(dag, type="CONSTRAINS", target="ring_inner_r")
    assert "ring_r_order" in sources


def test_constrains_has_rule_property():
    dag = build_dag("tapered", "bspline")
    edges = dag.get_edges(type="CONSTRAINS", source="attach_z_order")
    assert all("rule" in e.properties for e in edges)


# ── AFFECTS_GEOMETRY 엣지 ─────────────────────────────────────

def test_affects_geometry_tapered_side_wall():
    dag = build_dag("tapered", None)
    sources = _edge_set(dag, type="AFFECTS_GEOMETRY", target="Face:side_wall")
    assert "height" in sources
    assert "outer_top_r" in sources
    assert "outer_bottom_r" in sources


def test_affects_geometry_bottom_face():
    dag = build_dag("tapered", None)
    sources = _edge_set(dag, type="AFFECTS_GEOMETRY", target="Face:bottom")
    assert "bottom_thickness" in sources


def test_affects_geometry_top_rim_edge():
    dag = build_dag("tapered", None)
    sources = _edge_set(dag, type="AFFECTS_GEOMETRY", target="Edge:top_rim")
    assert "outer_top_r" in sources


def test_affects_geometry_bspline_junction_edges():
    dag = build_dag("tapered", "bspline")
    assert "lower_attach_z" in _edge_set(
        dag, type="AFFECTS_GEOMETRY", target="Edge:handle_lower_junction"
    )


def test_affects_geometry_ring_junction():
    dag = build_dag("cylinder", "ring")
    sources = _edge_set(dag, type="AFFECTS_GEOMETRY", target="Edge:ring_junction")
    assert "ring_attach_z" in sources
