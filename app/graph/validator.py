from app.graph.model import DAG


def check_constraints(dag: DAG, proposed: dict[str, float]) -> list[dict]:
    """
    제안된 파라미터 변경이 CONSTRAINS 엣지 규칙을 위반하는지 검사.

    proposed: {param_name: new_value} — 적용 예정인 값
    반환: [{"constraint": id, "rule": str, "description": str}, ...]

    같은 constraint는 중복 없이 한 번만 보고한다.
    규칙은 파라미터 이름을 변수로 쓰는 Python 비교 표현식.
    예: "lower_attach_z < upper_attach_z"
    """
    context = {**dag.get_all(), **proposed}
    violations: list[dict] = []
    seen: set[str] = set()

    for param in proposed:
        for edge in dag.get_edges(type="CONSTRAINS", target=param):
            cid = edge.source
            if cid in seen:
                continue
            seen.add(cid)

            rule = edge.properties.get("rule", "")
            description = edge.properties.get("description", rule)

            try:
                if not eval(rule, {"__builtins__": {}}, context):
                    violations.append({
                        "constraint": cid,
                        "rule": rule,
                        "description": description,
                    })
            except Exception:
                pass

    return violations
