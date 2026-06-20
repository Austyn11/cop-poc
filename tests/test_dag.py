import pytest
from app.graph.model import ParamNode, Edge, DAG


def test_param_node_user_facing():
    node = ParamNode(name="height", value=70.0, subgraph="body", is_user_facing=True)
    assert node.value == 70.0
    assert node.formula is None
    assert node.dependencies == []


def test_param_node_derived():
    node = ParamNode(
        name="inner_top_r",
        value=37.0,
        subgraph="body",
        is_user_facing=False,
        formula=lambda d: d.get("outer_top_r") - d.get("thickness"),
        dependencies=["outer_top_r", "thickness"],
    )
    assert node.formula is not None
    assert "outer_top_r" in node.dependencies


def test_dag_add_and_get():
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    assert dag.get("height") == 70.0


def test_dag_set():
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    dag.set("height", 90.0)
    assert dag.get("height") == 90.0


def test_dag_get_all_returns_name_value_dict():
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    dag.add_node(ParamNode("outer_top_r", 40.0, "body", True))
    result = dag.get_all()
    assert result == {"height": 70.0, "outer_top_r": 40.0}


def test_dag_get_user_facing():
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    dag.add_node(ParamNode(
        "inner_top_r", 37.0, "body", False,
        formula=lambda d: d.get("outer_top_r") - d.get("thickness"),
        dependencies=["outer_top_r", "thickness"],
    ))
    user_params = dag.get_user_facing()
    assert "height" in user_params
    assert "inner_top_r" not in user_params


def test_dag_missing_key_raises():
    dag = DAG()
    with pytest.raises(KeyError):
        dag.get("nonexistent")


# ── Edge / 타입 엣지 ──────────────────────────────────────────

def test_controls_edge_auto_created_from_dependencies():
    """파생 노드 추가 시 dependency마다 CONTROLS 엣지가 자동 생성됨."""
    dag = DAG()
    dag.add_node(ParamNode("outer_top_r", 40.0, "body", True))
    dag.add_node(ParamNode("thickness", 3.0, "body", True))
    dag.add_node(ParamNode(
        "inner_top_r", 0.0, "body", False,
        formula=lambda d: d.get("outer_top_r") - d.get("thickness"),
        dependencies=["outer_top_r", "thickness"],
    ))
    controls = dag.get_edges(type="CONTROLS", target="inner_top_r")
    sources = {e.source for e in controls}
    assert "outer_top_r" in sources
    assert "thickness" in sources


def test_user_facing_node_has_no_controls_edges():
    """사용자 파라미터(의존성 없음)는 CONTROLS 엣지를 생성하지 않음."""
    dag = DAG()
    dag.add_node(ParamNode("height", 70.0, "body", True))
    assert dag.get_edges(target="height", type="CONTROLS") == []


def test_add_edge_and_get_edges():
    dag = DAG()
    dag.add_edge(Edge("BELONGS_TO", "height", "TaperedBody"))
    dag.add_edge(Edge("BELONGS_TO", "outer_top_r", "TaperedBody"))
    dag.add_edge(Edge("EQUIVALENT_TO", "height", "cylinder_height", {"concept": "컵 높이"}))

    belongs = dag.get_edges(type="BELONGS_TO")
    assert len(belongs) == 2

    equiv = dag.get_edges(type="EQUIVALENT_TO")
    assert len(equiv) == 1
    assert equiv[0].properties["concept"] == "컵 높이"


def test_get_edges_filter_by_source():
    dag = DAG()
    dag.add_edge(Edge("CONTROLS", "height", "lower_outer_r"))
    dag.add_edge(Edge("CONTROLS", "height", "upper_outer_r"))
    dag.add_edge(Edge("CONTROLS", "outer_top_r", "lower_outer_r"))

    from_height = dag.get_edges(type="CONTROLS", source="height")
    assert len(from_height) == 2


def test_get_edges_filter_by_target():
    dag = DAG()
    dag.add_edge(Edge("AFFECTS_GEOMETRY", "outer_top_r", "Face:side_wall"))
    dag.add_edge(Edge("AFFECTS_GEOMETRY", "height", "Face:side_wall"))
    dag.add_edge(Edge("AFFECTS_GEOMETRY", "bottom_thickness", "Face:bottom"))

    to_side_wall = dag.get_edges(type="AFFECTS_GEOMETRY", target="Face:side_wall")
    assert len(to_side_wall) == 2
