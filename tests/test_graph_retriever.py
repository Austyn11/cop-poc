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
    for name in dag_tapered_bspline.nodes():
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
    assert context["nodes"]["inner_top_r"]["controls"] == []


def test_constraints_field_contains_rule_string(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "height >= 5.0" in context["nodes"]["height"]["constraints"]


def test_constraints_empty_for_unconstrained_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert context["nodes"]["inner_top_r"]["constraints"] == []


def test_affects_field_lists_geometry_elements(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert "Face:side_wall" in context["nodes"]["height"]["affects"]


def test_affects_empty_for_non_geometry_node(dag_tapered_bspline):
    context = GraphRetriever().retrieve(dag_tapered_bspline)
    assert context["nodes"]["inner_top_r"]["affects"] == []


def test_body_only_dag_has_no_handle_nodes(dag_tapered_only):
    context = GraphRetriever().retrieve(dag_tapered_only)
    assert "lower_attach_z" not in context["nodes"]
    assert "height" in context["nodes"]
