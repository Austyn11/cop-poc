from app.graph.model import DAG


class GraphRetriever:
    def retrieve(self, dag: DAG) -> dict:
        return {"nodes": self._build_nodes(dag)}

    def _build_nodes(self, dag: DAG) -> dict:
        result = {}
        for name, node in dag._nodes.items():
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
        return [
            e.properties["rule"]
            for e in dag.get_edges(type="CONSTRAINS", target=name)
            if "rule" in e.properties
        ]

    def _get_affects(self, dag: DAG, name: str) -> list[str]:
        return [e.target for e in dag.get_edges(type="AFFECTS_GEOMETRY", source=name)]
