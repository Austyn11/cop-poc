import pytest
from app.graph.cup_graph import build_dag
from app.graph.solver import initialize
from app.codegen.renderer import render


def test_render_tapered_no_handle():
    dag = build_dag("tapered", None)
    initialize(dag)
    code = render("tapered", None, dag)
    assert "cupBody" in code
    assert "cupHandle" not in code
    assert "Union" not in code


def test_render_tapered_with_bspline():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    code = render("tapered", "bspline", dag)
    assert "cupBody" in code
    assert "cupHandle" in code
    assert "Union" in code


def test_render_cylinder_no_handle():
    dag = build_dag("cylinder", None)
    initialize(dag)
    code = render("cylinder", None, dag)
    assert "Cylinder" in code
    assert "cupHandle" not in code


def test_render_cylinder_with_ring():
    dag = build_dag("cylinder", "ring")
    initialize(dag)
    code = render("cylinder", "ring", dag)
    assert "cupBody" in code
    assert "cupHandle" in code
    assert "Union" in code


def test_render_injects_computed_height():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    dag.set("height", 90.0)
    from app.graph.solver import recompute
    recompute(dag, ["height"])
    code = render("tapered", "bspline", dag)
    assert "const height = 90" in code


def test_render_joint_params_in_handle_code():
    dag = build_dag("tapered", "bspline")
    initialize(dag)
    code = render("tapered", "bspline", dag)
    # joint 파라미터가 손잡이 템플릿에 주입되었는지 확인
    assert "const lowerAttachZ" in code
    assert "const upperAttachZ" in code
