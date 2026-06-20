import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _mock_parse(result: dict):
    mock = MagicMock(return_value=result)
    return patch("app.api.routes.parse_command", mock)


def _create_result(body_template="tapered", handle_template="bspline"):
    return {
        "intent": "create",
        "body_template": body_template,
        "handle_template": handle_template,
        "changes": [],
    }


def _modify_result(changes: list):
    return {
        "intent": "modify",
        "body_template": None,
        "handle_template": None,
        "changes": changes,
    }


# ── create intent ─────────────────────────────────────────────

def test_create_tapered_no_handle():
    with _mock_parse(_create_result("tapered", None)):
        resp = client.post("/api/generate", json={"command": "손잡이 없는 컵 만들어줘"})
    assert resp.status_code == 200
    data = resp.json()
    assert "cupBody" in data["code"]
    assert "cupHandle" not in data["code"]
    assert data["state"]["body_template"] == "tapered"
    assert data["state"]["handle_template"] is None


def test_create_tapered_with_bspline():
    with _mock_parse(_create_result("tapered", "bspline")):
        resp = client.post("/api/generate", json={"command": "테이퍼드 컵 만들어줘"})
    assert resp.status_code == 200
    data = resp.json()
    assert "cupBody" in data["code"]
    assert "cupHandle" in data["code"]
    assert "Union" in data["code"]


def test_create_cylinder_with_ring():
    with _mock_parse(_create_result("cylinder", "ring")):
        resp = client.post("/api/generate", json={"command": "원통형 컵 링 손잡이로 만들어줘"})
    assert resp.status_code == 200
    data = resp.json()
    assert "cupBody" in data["code"]
    assert "cupHandle" in data["code"]


def test_create_state_includes_all_params():
    with _mock_parse(_create_result("tapered", "bspline")):
        resp = client.post("/api/generate", json={"command": "컵 만들어줘"})
    params = resp.json()["state"]["params"]
    assert "height" in params
    assert "lower_attach_z" in params
    assert "upper_attach_x" in params


def test_create_diff_is_empty():
    with _mock_parse(_create_result()):
        resp = client.post("/api/generate", json={"command": "컵 만들어줘"})
    diff = resp.json()["diff"]
    assert diff["changed"] == []
    assert diff["recomputed"] == []


def test_create_graph_has_subgraphs():
    """graph 필드: body·handle·joint 서브그래프가 각각 존재해야 함."""
    with _mock_parse(_create_result("tapered", "bspline")):
        resp = client.post("/api/generate", json={"command": "컵 만들어줘"})
    graph = resp.json()["graph"]
    assert "body" in graph
    assert "handle" in graph
    assert "joint" in graph


def test_create_graph_node_structure():
    """각 노드는 name·value·user_facing 필드를 가짐."""
    with _mock_parse(_create_result("tapered", "bspline")):
        resp = client.post("/api/generate", json={"command": "컵 만들어줘"})
    body_nodes = resp.json()["graph"]["body"]
    height_node = next(n for n in body_nodes if n["name"] == "height")
    assert height_node["value"] == pytest.approx(90.0)
    assert height_node["user_facing"] is True
    inner_top = next(n for n in body_nodes if n["name"] == "inner_top_r")
    assert inner_top["user_facing"] is False


def test_modify_graph_joint_nodes_present():
    """modify 후에도 joint 서브그래프가 반환됨."""
    with _mock_parse(_modify_result([{"param": "height", "value": 90}])):
        resp = client.post("/api/generate", json={
            "command": "높이 90",
            "state": {
                "body_template": "tapered", "handle_template": "bspline",
                "params": {
                    "height": 70.0, "outer_top_r": 40.0, "outer_bottom_r": 29.0, "thickness": 3.0,
                    "section_width": 14.0, "section_height": 8.0,
                    "lower_attach_z": 12.6, "upper_attach_z": 56.0,
                    "handle_outward_depth": 24.0,
                },
            },
        })
    graph = resp.json()["graph"]
    joint_names = [n["name"] for n in graph["joint"]]
    assert "lower_outer_r" in joint_names
    assert "upper_attach_x" in joint_names


# ── modify intent ─────────────────────────────────────────────

def test_generate_height_change_recomputes_joint():
    with _mock_parse(_modify_result([{"param": "height", "value": 90}])):
        resp = client.post("/api/generate", json={
            "command": "컵 높이를 90으로 바꿔줘",
            "state": {
                "body_template": "tapered",
                "handle_template": "bspline",
                "params": {
                    "height": 70.0, "outer_top_r": 40.0, "outer_bottom_r": 29.0, "thickness": 3.0,
                    "section_width": 14.0, "section_height": 8.0,
                    "lower_attach_z": 12.6, "upper_attach_z": 56.0,
                    "handle_outward_depth": 24.0,
                },
            },
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "height" in data["diff"]["changed"]
    assert "lower_attach_z" not in data["diff"]["recomputed"]  # user-facing, 고정
    assert "upper_attach_z" not in data["diff"]["recomputed"]  # user-facing, 고정
    assert "lower_outer_r" in data["diff"]["recomputed"]
    assert "lower_attach_x" in data["diff"]["recomputed"]
    assert "upper_attach_x" in data["diff"]["recomputed"]


def test_generate_updated_height_in_code():
    with _mock_parse(_modify_result([{"param": "height", "value": 90}])):
        resp = client.post("/api/generate", json={
            "command": "높이 90",
            "state": {
                "body_template": "tapered",
                "handle_template": "bspline",
                "params": {
                    "height": 70.0, "outer_top_r": 40.0, "outer_bottom_r": 29.0, "thickness": 3.0,
                    "section_width": 14.0, "section_height": 8.0,
                    "lower_attach_z": 12.6, "upper_attach_z": 56.0,
                    "handle_outward_depth": 24.0,
                },
            },
        })
    assert "const height = 90" in resp.json()["code"]


def test_generate_no_state_uses_defaults():
    with _mock_parse(_modify_result([{"param": "height", "value": 80}])):
        resp = client.post("/api/generate", json={"command": "높이 80"})
    assert resp.status_code == 200
    assert "code" in resp.json()


def test_generate_cylinder_ring_radius_change():
    with _mock_parse(_modify_result([{"param": "cylinder_radius", "value": 50}])):
        resp = client.post("/api/generate", json={
            "command": "컵 반지름을 50으로",
            "state": {
                "body_template": "cylinder",
                "handle_template": "ring",
                "params": {
                    "cylinder_height": 90.0, "cylinder_radius": 40.0, "cylinder_thickness": 2.5,
                    "ring_outer_r": 19.5, "ring_inner_r": 10.5, "ring_width": 15.0, "ring_attach_z": 60.0,
                },
            },
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "cylinder_radius" in data["diff"]["changed"]
    assert "ring_attach_x" in data["diff"]["recomputed"]


# ── op: set vs delta ──────────────────────────────────────────────────────────

_RING_STATE = {
    "body_template": "cylinder",
    "handle_template": "ring",
    "params": {
        "cylinder_height": 90.0, "cylinder_radius": 40.0, "cylinder_thickness": 2.5,
        "ring_outer_r": 19.5, "ring_inner_r": 10.5, "ring_width": 15.0, "ring_attach_z": 72.0,
    },
}


def test_modify_op_set_applies_absolute_value():
    """op='set', value=25 → ring_outer_r는 25.0이 되어야 함 (현재값 무관)."""
    with _mock_parse(_modify_result([{"param": "ring_outer_r", "op": "set", "value": 25}])):
        resp = client.post("/api/generate", json={"command": "ring_outer_r를 25로", "state": _RING_STATE})
    assert resp.status_code == 200
    assert resp.json()["state"]["params"]["ring_outer_r"] == pytest.approx(25.0)


def test_modify_op_delta_adds_to_current():
    """op='delta', value=5 → ring_outer_r는 19.5 + 5 = 24.5가 되어야 함."""
    with _mock_parse(_modify_result([{"param": "ring_outer_r", "op": "delta", "value": 5}])):
        resp = client.post("/api/generate", json={"command": "ring_outer_r를 5 더 크게", "state": _RING_STATE})
    assert resp.status_code == 200
    assert resp.json()["state"]["params"]["ring_outer_r"] == pytest.approx(24.5)


def test_modify_op_delta_negative_subtracts():
    """op='delta', value=-8 → ring_outer_r는 19.5 - 8 = 11.5가 되어야 함."""
    with _mock_parse(_modify_result([{"param": "ring_outer_r", "op": "delta", "value": -8}])):
        resp = client.post("/api/generate", json={"command": "ring_outer_r를 8 줄여줘", "state": _RING_STATE})
    assert resp.status_code == 200
    assert resp.json()["state"]["params"]["ring_outer_r"] == pytest.approx(11.5)


# ── post_process intent ───────────────────────────────────────────────────────

def _post_process_result(operation="fillet_edge", radius=2.0):
    return {"intent": "post_process", "operation": operation, "radius": radius, "changes": []}


def test_fillet_appended_to_code():
    """필렛 명령 → POST PROCESSING 섹션에 FilletEdges 라인 추가."""
    with _mock_parse(_post_process_result(radius=2.0)):
        resp = client.post("/api/generate", json={
            "command": "선택된 엣지에 필렛 2 넣어줘",
            "state": _RING_STATE,
            "selection": {"type": "Edge", "index": 3},
        })
    assert resp.status_code == 200
    code = resp.json()["code"]
    assert "POST PROCESSING" in code
    pp_section = code.split("POST PROCESSING")[1]
    assert "FilletEdges(cup, 2.0, [3], false)" in pp_section


def test_fillet_saved_in_state():
    """필렛 적용 후 state.post_processing에 저장됨."""
    with _mock_parse(_post_process_result(radius=1.5)):
        resp = client.post("/api/generate", json={
            "command": "선택된 엣지에 필렛 1.5 넣어줘",
            "state": _RING_STATE,
            "selection": {"type": "Edge", "index": 5},
        })
    pp = resp.json()["state"]["post_processing"]
    assert len(pp) == 1
    assert pp[0] == {"op": "fillet_edge", "index": 5, "radius": 1.5}


def test_fillet_accumulates_across_requests():
    """두 번 필렛 → post_processing에 두 항목."""
    state_with_fillet = dict(_RING_STATE)
    state_with_fillet["post_processing"] = [{"op": "fillet_edge", "index": 3, "radius": 2.0}]
    with _mock_parse(_post_process_result(radius=1.0)):
        resp = client.post("/api/generate", json={
            "command": "선택된 엣지에 필렛 1 넣어줘",
            "state": state_with_fillet,
            "selection": {"type": "Edge", "index": 7},
        })
    pp = resp.json()["state"]["post_processing"]
    assert len(pp) == 2


def test_fillet_preserved_on_modify():
    """파라미터 수정 후에도 기존 필렛이 코드에 유지됨."""
    state_with_fillet = dict(_RING_STATE)
    state_with_fillet["post_processing"] = [{"op": "fillet_edge", "index": 3, "radius": 2.0}]
    with _mock_parse(_modify_result([{"param": "ring_outer_r", "op": "set", "value": 25}])):
        resp = client.post("/api/generate", json={
            "command": "ring_outer_r를 25로",
            "state": state_with_fillet,
        })
    assert resp.status_code == 200
    assert "FilletEdges" in resp.json()["code"]
    assert resp.json()["state"]["post_processing"] == [{"op": "fillet_edge", "index": 3, "radius": 2.0}]


def test_fillet_reset_on_create():
    """새 모델 생성 시 post_processing 초기화."""
    with _mock_parse(_create_result()):
        resp = client.post("/api/generate", json={"command": "컵 만들어줘"})
    assert resp.json()["state"]["post_processing"] == []


def test_fillet_ignored_without_selection():
    """selection 없이 post_process intent → POST PROCESSING 섹션 추가 안 됨."""
    with _mock_parse(_post_process_result(radius=2.0)):
        resp = client.post("/api/generate", json={
            "command": "필렛 2 넣어줘",
            "state": _RING_STATE,
            # selection 없음
        })
    assert resp.status_code == 200
    assert "POST PROCESSING" not in resp.json()["code"]


def test_modify_op_missing_defaults_to_set():
    """op 필드가 없으면 'set'으로 처리 — 절댓값 적용."""
    # op 없이 기존 방식 (하위 호환)
    with _mock_parse(_modify_result([{"param": "ring_outer_r", "value": 30}])):
        resp = client.post("/api/generate", json={"command": "ring_outer_r를 30으로", "state": _RING_STATE})
    assert resp.status_code == 200
    assert resp.json()["state"]["params"]["ring_outer_r"] == pytest.approx(30.0)


# ── 제약 위반 감지 ────────────────────────────────────────────

_BSPLINE_STATE = {
    "body_template": "tapered",
    "handle_template": "bspline",
    "params": {
        "height": 70.0, "outer_top_r": 40.0, "outer_bottom_r": 29.0, "thickness": 3.0,
        "section_width": 14.0, "section_height": 8.0,
        "lower_attach_z": 12.6, "upper_attach_z": 56.0,
        "handle_outward_depth": 24.0,
    },
}


def test_constraint_violation_blocks_change():
    """lower_attach_z > upper_attach_z → 위반, 변경 없이 violations 반환."""
    with _mock_parse(_modify_result([{"param": "lower_attach_z", "op": "set", "value": 70}])):
        resp = client.post("/api/generate", json={
            "command": "lower_attach_z를 70으로", "state": _BSPLINE_STATE,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["violations"]) > 0
    assert data["diff"]["changed"] == []
    assert data["state"]["params"]["lower_attach_z"] == pytest.approx(12.6)  # 변경 안 됨


def test_constraint_violation_preserves_state():
    """위반 시 state가 요청 이전 값 그대로 반환됨."""
    with _mock_parse(_modify_result([{"param": "upper_attach_z", "op": "set", "value": 80}])):
        resp = client.post("/api/generate", json={
            "command": "upper_attach_z를 80으로", "state": _BSPLINE_STATE,
        })
    data = resp.json()
    assert data["state"]["params"]["upper_attach_z"] == pytest.approx(56.0)


def test_no_violation_returns_empty_violations():
    """정상 변경이면 violations 빈 리스트."""
    with _mock_parse(_modify_result([{"param": "height", "op": "set", "value": 90}])):
        resp = client.post("/api/generate", json={
            "command": "높이 90", "state": _BSPLINE_STATE,
        })
    assert resp.json()["violations"] == []


def test_simultaneous_change_avoids_violation():
    """height와 upper_attach_z를 같이 올리면 위반 없음."""
    with _mock_parse(_modify_result([
        {"param": "height", "op": "set", "value": 100},
        {"param": "upper_attach_z", "op": "set", "value": 80},
    ])):
        resp = client.post("/api/generate", json={
            "command": "height 100, upper_attach_z 80", "state": _BSPLINE_STATE,
        })
    data = resp.json()
    assert data["violations"] == []
    assert data["state"]["params"]["height"] == pytest.approx(100.0)
    assert data["state"]["params"]["upper_attach_z"] == pytest.approx(80.0)
