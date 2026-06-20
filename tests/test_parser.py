# tests/test_parser.py
import json
from unittest.mock import MagicMock, patch
from app.llm.parser import parse_command


def _mock_response(text: str):
    """OpenAI ChatCompletion 응답 구조 mock."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = text
    return mock


def _patch(text: str):
    return patch(
        "app.llm.parser.client.chat.completions.create",
        return_value=_mock_response(text),
    )


_CTX = {"nodes": {}}  # LLM이 mock되므로 내용 무관


def test_parse_modify_single_param():
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 90}]}'
    with _patch(resp):
        result = parse_command("컵 높이를 90으로 바꿔줘", _CTX)
    assert result["intent"] == "modify"
    assert result["changes"] == [{"param": "height", "value": 90}]


def test_parse_modify_multiple_params():
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "outer_top_r", "value": 45}, {"param": "height", "value": 80}]}'
    with _patch(resp):
        result = parse_command("입구 반지름 45로, 높이 80으로", _CTX)
    assert result["intent"] == "modify"
    assert len(result["changes"]) == 2
    assert {"param": "outer_top_r", "value": 45} in result["changes"]


def test_parse_create_tapered_bspline():
    resp = '{"intent": "create", "body_template": "tapered", "handle_template": "bspline", "changes": []}'
    with _patch(resp):
        result = parse_command("테이퍼드 컵 만들어줘", _CTX)
    assert result["intent"] == "create"
    assert result["body_template"] == "tapered"
    assert result["handle_template"] == "bspline"


def test_parse_create_cylinder_ring():
    resp = '{"intent": "create", "body_template": "cylinder", "handle_template": "ring", "changes": []}'
    with _patch(resp):
        result = parse_command("원통형 컵 링 손잡이로 만들어줘", _CTX)
    assert result["intent"] == "create"
    assert result["body_template"] == "cylinder"
    assert result["handle_template"] == "ring"


def test_parse_extracts_json_from_prose():
    """LLM이 JSON 앞뒤에 텍스트를 붙여도 파싱 성공."""
    resp = 'Here is the result: {"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 100}]} Done.'
    with _patch(resp):
        result = parse_command("높이 100", _CTX)
    assert result["intent"] == "modify"
    assert result["changes"][0]["value"] == 100


def test_parse_defaults_on_missing_fields():
    """intent 필드만 있어도 나머지 필드는 기본값으로 채워짐."""
    resp = '{"intent": "modify", "changes": [{"param": "height", "value": 80}]}'
    with _patch(resp):
        result = parse_command("높이 80", _CTX)
    assert result["body_template"] is None
    assert result["handle_template"] is None


def test_parse_op_set_absolute():
    """'10mm로 수정해줘' → op: set, 절댓값."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "ring_outer_r", "op": "set", "value": 10}]}'
    with _patch(resp):
        result = parse_command("원형 손잡이 지름을 10mm로 수정해줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "set"
    assert change["value"] == 10
    assert change["param"] == "ring_outer_r"


def test_parse_op_delta_positive():
    """'15mm 더 크게' → op: delta, 양수."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "ring_outer_r", "op": "delta", "value": 15}]}'
    with _patch(resp):
        result = parse_command("원형 손잡이 지름을 15mm 더 크게 해줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "delta"
    assert change["value"] == 15


def test_parse_op_delta_negative():
    """'5mm 작게' → op: delta, 음수."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "op": "delta", "value": -5}]}'
    with _patch(resp):
        result = parse_command("높이를 5mm 줄여줘", _CTX)
    change = result["changes"][0]
    assert change["op"] == "delta"
    assert change["value"] == -5


def test_parse_post_process_fillet():
    """selection 컨텍스트 + 필렛 명령 → post_process intent."""
    resp = '{"intent": "post_process", "operation": "fillet_edge", "radius": 2.0}'
    with _patch(resp):
        result = parse_command(
            "선택된 엣지에 필렛 2 넣어줘",
            _CTX,
            selection={"type": "Edge", "index": 1},
        )
    assert result["intent"] == "post_process"
    assert result["operation"] == "fillet_edge"
    assert result["radius"] == 2.0


def test_parse_op_missing_passes_through():
    """LLM이 op 필드를 빠뜨려도 파서는 그대로 통과 (라우트에서 기본값 처리)."""
    resp = '{"intent": "modify", "body_template": null, "handle_template": null, "changes": [{"param": "height", "value": 90}]}'
    with _patch(resp):
        result = parse_command("높이 90", _CTX)
    change = result["changes"][0]
    assert "value" in change
    assert change["value"] == 90
