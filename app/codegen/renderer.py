from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.graph.model import DAG

_FEATURES_DIR = Path(__file__).parent.parent / "features"
_ENV = Environment(loader=FileSystemLoader(str(_FEATURES_DIR)))


def render(
    body_template: str,
    handle_template: str | None,
    dag: DAG,
    post_processing: list[dict] | None = None,
) -> str:
    """DAG 파라미터 값으로 Jinja2 JS 템플릿을 렌더링하고 조합된 코드를 반환."""
    params = dag.get_all()
    parts: list[str] = []

    body_tmpl = _ENV.get_template(f"body/{body_template}_body.js.j2")
    parts.append(body_tmpl.render(**params))

    if handle_template:
        handle_tmpl = _ENV.get_template(f"handle/{handle_template}_handle.js.j2")
        parts.append(handle_tmpl.render(**params))
        parts.append("\n// === UNION ===\nlet cup = Union([cupBody, cupHandle]);")
        cup_var = "cup"
    else:
        cup_var = "cupBody"

    if post_processing:
        fillet_lines = [
            f"{cup_var} = FilletEdges({cup_var}, {op['radius']}, [{op['index']}], false);"
            for op in post_processing
            if op.get("op") == "fillet_edge"
        ]
        if fillet_lines:
            parts.append("\n// === POST PROCESSING ===\n" + "\n".join(fillet_lines))

    parts.append(f"\n// === RESULT ===\n{cup_var};")

    return "\n\n".join(parts)
