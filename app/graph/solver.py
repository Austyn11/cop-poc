from collections import defaultdict, deque
from app.graph.model import DAG


def _dependents_map(dag: DAG) -> dict[str, list[str]]:
    """노드 이름 → 이 노드에 의존하는 노드 이름 목록"""
    result: dict[str, list[str]] = defaultdict(list)
    for node in dag._nodes.values():
        for dep in node.dependencies:
            result[dep].append(node.name)
    return result


def _topo_sort_affected(dag: DAG, changed_names: list[str]) -> list[str]:
    """changed_names 로부터 영향받는 파생 노드를 위상 정렬 순서로 반환."""
    dependents = _dependents_map(dag)

    # BFS로 영향받는 노드 집합 수집
    visited: set[str] = set()
    queue: deque[str] = deque()
    for name in changed_names:
        for dep in dependents.get(name, []):
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)
    while queue:
        current = queue.popleft()
        for dep in dependents.get(current, []):
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)

    # 위상 정렬 (의존성 만족된 노드부터 처리)
    result: list[str] = []
    processed: set[str] = set(dag._nodes.keys()) - visited  # 영향 없는 노드는 처리된 것으로
    remaining = list(visited)

    while remaining:
        progress = False
        for name in remaining[:]:
            node = dag._nodes[name]
            if all(dep in processed for dep in node.dependencies):
                result.append(name)
                processed.add(name)
                remaining.remove(name)
                progress = True
        if not progress:
            break  # 순환 의존이 있는 경우 (POC 범위에서는 발생하지 않음)

    return result


def initialize(dag: DAG) -> None:
    """모든 파생 노드를 처음부터 위상 정렬 순서로 계산."""
    user_nodes = {n for n, node in dag._nodes.items() if node.formula is None}
    remaining = [n for n in dag._nodes if dag._nodes[n].formula is not None]
    processed = set(user_nodes)

    while remaining:
        progress = False
        for name in remaining[:]:
            node = dag._nodes[name]
            if all(dep in processed for dep in node.dependencies):
                dag.set(name, node.formula(dag))
                processed.add(name)
                remaining.remove(name)
                progress = True
        if not progress:
            break


def recompute(dag: DAG, changed_names: list[str]) -> tuple[list[str], list[str]]:
    """
    변경된 노드 목록을 받아 영향받는 파생 노드를 순서대로 재계산.
    반환: (changed_names, recomputed_names)
    """
    order = _topo_sort_affected(dag, changed_names)
    recomputed: list[str] = []
    for name in order:
        node = dag._nodes[name]
        if node.formula is not None:
            dag.set(name, node.formula(dag))
            recomputed.append(name)
    return changed_names, recomputed
