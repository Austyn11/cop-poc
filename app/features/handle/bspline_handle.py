from pathlib import Path
from app.features.base import HandleFeature, BodyFeature
from app.graph.model import DAG, Edge, ParamNode


class BSplineHandle(HandleFeature):
    def get_default_params(self) -> dict[str, float]:
        return {
            "section_width": 14.0,
            "section_height": 8.0,
            "lower_attach_z": 12.6,
            "upper_attach_z": 56.0,
            "handle_outward_depth": 24.0,
        }

    def get_template_path(self) -> Path:
        return Path(__file__).parent / "bspline_handle.js.j2"

    def build_joint_nodes(self, dag: DAG, body: BodyFeature) -> None:
        t = body.wall_thickness_param

        # ── lower/upper attach Z는 user-facing, 이미 DAG에 존재 ──────
        dag.add_node(ParamNode(
            "handle_span_z", 0.0, "joint", False,
            formula=lambda d: d.get("upper_attach_z") - d.get("lower_attach_z"),
            dependencies=["upper_attach_z", "lower_attach_z"],
        ))

        # ── body 인터페이스: 각 Z에서 외면 반경 ──────────────────────
        body.add_outer_r_node(dag, at_z="lower_attach_z", result="lower_outer_r")
        body.add_outer_r_node(dag, at_z="upper_attach_z", result="upper_outer_r")

        # ── body 두께 기반 penetration depth ─────────────────────────
        dag.add_node(ParamNode(
            "penetration_depth", 0.0, "joint", False,
            formula=lambda d, t=t: d.get(t) * 0.75,
            dependencies=[t],
        ))

        # ── attach X 좌표 (body 좌측 음수 방향) ─────────────────────
        dag.add_node(ParamNode(
            "lower_attach_x", 0.0, "joint", False,
            formula=lambda d: -d.get("lower_outer_r") + d.get("penetration_depth"),
            dependencies=["lower_outer_r", "penetration_depth"],
        ))
        dag.add_node(ParamNode(
            "upper_attach_x", 0.0, "joint", False,
            formula=lambda d: -d.get("upper_outer_r") + d.get("penetration_depth"),
            dependencies=["upper_outer_r", "penetration_depth"],
        ))

        # ── bspline 고유: 중간점 외면 반경 ──────────────────────────
        dag.add_node(ParamNode(
            "handle_mid_z", 0.0, "joint", False,
            formula=lambda d: (d.get("lower_attach_z") + d.get("upper_attach_z")) / 2,
            dependencies=["lower_attach_z", "upper_attach_z"],
        ))
        body.add_outer_r_node(dag, at_z="handle_mid_z", result="handle_mid_outer_r")
        # handle_outward_depth는 user-facing, 이미 DAG에 존재

        for name in ["handle_span_z", "lower_outer_r", "upper_outer_r",
                     "penetration_depth", "lower_attach_x", "upper_attach_x",
                     "handle_mid_z", "handle_mid_outer_r"]:
            if name in dag._nodes:
                dag.add_edge(Edge("BELONGS_TO", name, "BSplineHandle"))
