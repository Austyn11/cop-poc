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
