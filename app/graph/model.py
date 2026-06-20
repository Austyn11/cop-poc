from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ParamNode:
    name: str
    value: float
    subgraph: str  # "body", "handle", "joint"
    is_user_facing: bool
    formula: Optional[Callable[["DAG"], float]] = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Edge:
    type: str       # "CONTROLS" | "BELONGS_TO" | "EQUIVALENT_TO" | "CONSTRAINS" | "AFFECTS_GEOMETRY"
    source: str     # 출발 노드 이름 (또는 제약 식별자)
    target: str     # 도착 노드 이름 (또는 기하 요소 식별자)
    properties: dict = field(default_factory=dict)


class DAG:
    def __init__(self) -> None:
        self._nodes: dict[str, ParamNode] = {}
        self._edges: list[Edge] = []

    def add_node(self, node: ParamNode) -> None:
        self._nodes[node.name] = node
        # CONTROLS 엣지 자동 생성: 각 dependency → 이 파생 노드
        for dep in node.dependencies:
            self._edges.append(Edge("CONTROLS", dep, node.name))

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)

    def get_edges(
        self,
        type: str | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> list[Edge]:
        result = self._edges
        if type is not None:
            result = [e for e in result if e.type == type]
        if source is not None:
            result = [e for e in result if e.source == source]
        if target is not None:
            result = [e for e in result if e.target == target]
        return result

    def get(self, name: str) -> float:
        return self._nodes[name].value

    def set(self, name: str, value: float) -> None:
        self._nodes[name].value = value

    def get_all(self) -> dict[str, float]:
        return {name: node.value for name, node in self._nodes.items()}

    def get_user_facing(self) -> dict[str, float]:
        return {name: node.value for name, node in self._nodes.items() if node.is_user_facing}

    def nodes(self) -> dict[str, "ParamNode"]:
        """모든 노드를 {name: ParamNode} 사전으로 반환 (복사본)."""
        return dict(self._nodes)
