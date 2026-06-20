from pathlib import Path
from app.features.base import HandleFeature, BodyFeature
from app.graph.model import DAG, Edge, ParamNode


class RingHandle(HandleFeature):
    def get_default_params(self) -> dict[str, float]:
        return {
            "ring_outer_r": 19.5,
            "ring_inner_r": 10.5,
            "ring_width": 15.0,
            "ring_attach_z": 72.0,
        }

    def get_template_path(self) -> Path:
        return Path(__file__).parent / "ring_handle.js.j2"

    def build_joint_nodes(self, dag: DAG, body: BodyFeature) -> None:
        t = body.wall_thickness_param

        # ── ring_attach_z는 user-facing, 이미 DAG에 존재 ────────────
        body.add_outer_r_node(dag, at_z="ring_attach_z", result="ring_outer_r_at_attach")

        # ── ring 중심 X 좌표 (body 우측 양수 방향) ──────────────────
        dag.add_node(ParamNode(
            "ring_attach_x", 0.0, "joint", False,
            formula=lambda d, t=t: (
                d.get("ring_outer_r_at_attach")
                + d.get("ring_outer_r")
                - d.get(t) * 0.75
            ),
            dependencies=["ring_outer_r_at_attach", "ring_outer_r", t],
        ))

        for name in ["ring_outer_r_at_attach", "ring_attach_x"]:
            dag.add_edge(Edge("BELONGS_TO", name, "RingHandle"))
