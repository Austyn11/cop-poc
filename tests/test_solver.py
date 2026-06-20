import pytest
from app.graph.model import ParamNode, DAG
from app.graph.solver import initialize, recompute


def _make_two_node_dag() -> DAG:
    """A → B where B = A * 2"""
    dag = DAG()
    dag.add_node(ParamNode("a", 5.0, "body", True))
    dag.add_node(ParamNode(
        "b", 0.0, "body", False,
        formula=lambda d: d.get("a") * 2,
        dependencies=["a"],
    ))
    return dag


def _make_chain_dag() -> DAG:
    """height → lower_z (= height * 0.18) → lower_r (= lower_z + 10)"""
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    dag.add_node(ParamNode(
        "lower_z", 0.0, "joint", False,
        formula=lambda d: d.get("height") * 0.18,
        dependencies=["height"],
    ))
    dag.add_node(ParamNode(
        "lower_r", 0.0, "joint", False,
        formula=lambda d: d.get("lower_z") + 10,
        dependencies=["lower_z"],
    ))
    return dag


def test_initialize_computes_derived_values():
    dag = _make_two_node_dag()
    initialize(dag)
    assert dag.get("b") == 10.0


def test_initialize_chain():
    dag = _make_chain_dag()
    initialize(dag)
    assert dag.get("lower_z") == pytest.approx(70.0 * 0.18)
    assert dag.get("lower_r") == pytest.approx(70.0 * 0.18 + 10)


def test_recompute_after_change():
    dag = _make_two_node_dag()
    initialize(dag)
    dag.set("a", 10.0)
    changed, recomputed = recompute(dag, ["a"])
    assert dag.get("b") == 20.0
    assert "a" in changed
    assert "b" in recomputed


def test_recompute_chain():
    dag = _make_chain_dag()
    initialize(dag)
    dag.set("height", 90.0)
    _, recomputed = recompute(dag, ["height"])
    assert dag.get("lower_z") == pytest.approx(90.0 * 0.18)
    assert dag.get("lower_r") == pytest.approx(90.0 * 0.18 + 10)
    assert "lower_z" in recomputed
    assert "lower_r" in recomputed


def test_recompute_returns_only_affected_nodes():
    """Changing 'a' should not list unrelated nodes in recomputed."""
    dag = DAG()
    dag.add_node(ParamNode("a", 1.0, "body", True))
    dag.add_node(ParamNode("x", 99.0, "body", True))
    dag.add_node(ParamNode(
        "b", 0.0, "body", False,
        formula=lambda d: d.get("a") * 2,
        dependencies=["a"],
    ))
    initialize(dag)
    dag.set("a", 5.0)
    _, recomputed = recompute(dag, ["a"])
    assert "b" in recomputed
    assert "x" not in recomputed
