import pytest
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize
from app.graph.validator import check_constraints


def _violation_ids(violations):
    return {v["constraint"] for v in violations}


# ── 정상 케이스 ───────────────────────────────────────────────

def test_no_violations_on_valid_height_change():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    assert check_constraints(dag, {"height": 90.0}) == []


def test_no_violations_on_valid_radius_change():
    dag = build_dag("tapered", None)
    initialize(dag)
    assert check_constraints(dag, {"outer_top_r": 50.0}) == []


def test_no_violations_on_simultaneous_valid_change():
    """height와 upper_attach_z를 같이 올려서 둘 다 유효한 경우."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    # height 100, upper_attach_z 80 → 80 < 100 ✓, 12.6 < 80 ✓
    assert check_constraints(dag, {"height": 100.0, "upper_attach_z": 80.0}) == []


# ── attach_z_order: lower_attach_z < upper_attach_z ──────────

def test_lower_attach_z_above_upper_violates():
    """lower_attach_z를 upper_attach_z(56) 이상으로 올리면 위반."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    violations = check_constraints(dag, {"lower_attach_z": 60.0})
    assert "attach_z_order" in _violation_ids(violations)


def test_upper_attach_z_below_lower_violates():
    """upper_attach_z를 lower_attach_z(12.6) 이하로 내리면 위반."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    violations = check_constraints(dag, {"upper_attach_z": 10.0})
    assert "attach_z_order" in _violation_ids(violations)


# ── attach_within_body: upper_attach_z < height ──────────────

def test_upper_attach_z_above_height_violates():
    """upper_attach_z를 height(70) 이상으로 올리면 위반."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    violations = check_constraints(dag, {"upper_attach_z": 80.0})
    assert "attach_within_body" in _violation_ids(violations)


def test_height_decrease_below_upper_attach_z_violates():
    """height를 upper_attach_z(56) 이하로 낮추면 위반."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    violations = check_constraints(dag, {"height": 50.0})
    assert "attach_within_body" in _violation_ids(violations)


# ── positive_inner_top_r: outer_top_r > thickness ────────────

def test_thickness_exceeds_outer_top_r_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"thickness": 45.0})
    assert "positive_inner_top_r" in _violation_ids(violations)


def test_outer_top_r_below_thickness_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"outer_top_r": 2.0})
    assert "positive_inner_top_r" in _violation_ids(violations)


# ── positive_inner_bottom_r: outer_bottom_r > thickness ──────

def test_outer_bottom_r_below_thickness_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"outer_bottom_r": 1.0})
    assert "positive_inner_bottom_r" in _violation_ids(violations)


# ── positive_inner_radius (cylinder): cylinder_radius > cylinder_thickness

def test_cylinder_thickness_exceeds_radius_violates():
    dag = build_dag("cylinder", None)
    initialize(dag)
    violations = check_constraints(dag, {"cylinder_thickness": 50.0})
    assert "positive_inner_radius" in _violation_ids(violations)


# ── ring_r_order: ring_inner_r < ring_outer_r ────────────────

def test_ring_inner_r_above_outer_r_violates():
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    violations = check_constraints(dag, {"ring_inner_r": 25.0})
    assert "ring_r_order" in _violation_ids(violations)


# ── ring_within_body: ring_attach_z < cylinder_height ────────

def test_ring_attach_z_above_height_violates():
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    violations = check_constraints(dag, {"ring_attach_z": 100.0})
    assert "ring_within_body" in _violation_ids(violations)


# ── 중복 제거 ─────────────────────────────────────────────────

def test_no_duplicate_violation_when_both_params_change():
    """같은 constraint에 관여된 파라미터 둘 다 바꿔도 같은 constraint는 한 번만 보고."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    # lower=70, upper=60 → lower > upper, attach_z_order 위반
    violations = check_constraints(dag, {"lower_attach_z": 70.0, "upper_attach_z": 60.0})
    ids = [v["constraint"] for v in violations]
    assert ids.count("attach_z_order") == 1


def test_violation_has_description():
    """위반 항목에 description 필드가 있어야 함."""
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    violations = check_constraints(dag, {"lower_attach_z": 60.0})
    assert all("description" in v for v in violations)
    assert all(len(v["description"]) > 0 for v in violations)


# ── 최소 치수 제약 (height, radius) ──────────────────────────

def test_height_below_minimum_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"height": -10.0})
    assert "min_height" in _violation_ids(violations)


def test_height_at_minimum_passes():
    dag = build_dag("tapered", None)
    initialize(dag)
    assert check_constraints(dag, {"height": 5.0}) == []


def test_outer_top_r_below_minimum_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"outer_top_r": 3.0})
    assert "min_outer_top_r" in _violation_ids(violations)


def test_outer_bottom_r_below_minimum_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"outer_bottom_r": 3.0})
    assert "min_outer_bottom_r" in _violation_ids(violations)


def test_cylinder_height_below_minimum_violates():
    dag = build_dag("cylinder", None)
    initialize(dag)
    violations = check_constraints(dag, {"cylinder_height": 0.0})
    assert "min_cylinder_height" in _violation_ids(violations)


def test_cylinder_radius_below_minimum_violates():
    dag = build_dag("cylinder", None)
    initialize(dag)
    violations = check_constraints(dag, {"cylinder_radius": 5.0})
    assert "min_cylinder_radius" in _violation_ids(violations)


# ── 최소 두께 제약 ────────────────────────────────────────────

def test_thickness_below_minimum_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"thickness": 2.0})
    assert "min_thickness" in _violation_ids(violations)


def test_thickness_at_minimum_passes():
    dag = build_dag("tapered", None)
    initialize(dag)
    assert check_constraints(dag, {"thickness": 3.0}) == []


def test_bottom_thickness_below_minimum_violates():
    dag = build_dag("tapered", None)
    initialize(dag)
    violations = check_constraints(dag, {"bottom_thickness": 1.5})
    assert "min_bottom_thickness" in _violation_ids(violations)


def test_cylinder_thickness_below_minimum_violates():
    dag = build_dag("cylinder", None)
    initialize(dag)
    violations = check_constraints(dag, {"cylinder_thickness": 2.9})
    assert "min_cylinder_thickness" in _violation_ids(violations)


def test_cylinder_bottom_thickness_below_minimum_violates():
    dag = build_dag("cylinder", None)
    initialize(dag)
    violations = check_constraints(dag, {"cylinder_bottom_thickness": 0.5})
    assert "min_cylinder_bottom_thickness" in _violation_ids(violations)
