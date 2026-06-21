from app.graph.model import DAG
from app.graph.cup_graph import available_templates as _available_templates


class GraphRetriever:
    def retrieve(
        self,
        dag: DAG,
        body_template: str,
        handle_template: str | None,
        selection: dict | None = None,
    ) -> dict:
        return {
            "nodes": self._build_nodes(dag),
            "templates": self._build_templates(body_template, handle_template),
            "intents": self._build_intents(selection),
        }

    # ── nodes ────────────────────────────────────────────────────────────

    def _build_nodes(self, dag: DAG) -> dict:
        result = {}
        for name, node in dag.nodes().items():
            result[name] = {
                "value": node.value,
                "subgraph": node.subgraph,
                "user_facing": node.is_user_facing,
                "controls": self._get_controls(dag, name),
                "constraints": self._get_constraints(dag, name),
                "affects": self._get_affects(dag, name),
            }
        return result

    def _get_controls(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="CONTROLS", source=name)]

    def _get_constraints(self, dag: DAG, name: str) -> list[str]:
        seen: dict[str, None] = {}
        for e in dag.get_edges(type="CONSTRAINS", target=name):
            if "rule" in e.properties:
                seen[e.properties["rule"]] = None
        return list(seen)

    def _get_affects(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="AFFECTS_GEOMETRY", source=name)]

    # ── templates ────────────────────────────────────────────────────────

    def _build_templates(self, body_template: str, handle_template: str | None) -> dict:
        return {
            "current": {"body": body_template, "handle": handle_template},
            "available": _available_templates(),
        }

    # ── intents ──────────────────────────────────────────────────────────

    def _build_intents(self, selection: dict | None) -> dict:
        return {
            "create": {
                "available": True,
                "description": "새 컵 모델을 처음부터 생성",
            },
            "modify": {
                "available": True,
                "description": "현재 모델의 파라미터 수정",
            },
            "post_process": {
                "available": selection is not None,
                "description": "선택된 엣지에 필렛/라운드 적용",
                "requires": "Edge selection",
            },
        }
