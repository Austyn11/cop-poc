from pathlib import Path
from app.features.base import BodyFeature
from app.graph.model import DAG, ParamNode


class TaperedBody(BodyFeature):
    height_param = "height"
    wall_thickness_param = "thickness"
    reference_radius_param = "outer_top_r"

    def get_default_params(self) -> dict[str, float]:
        return {
            "height": 70.0,
            "outer_top_r": 40.0,
            "outer_bottom_r": 29.0,
            "thickness": 3.0,
            "bottom_thickness": 3.0,
        }

    def get_template_path(self) -> Path:
        return Path(__file__).parent / "tapered_body.js.j2"

    def add_outer_r_node(self, dag: DAG, at_z: str, result: str) -> None:
        """테이퍼드 body: Z에 따라 선형 보간된 외면 반경."""
        dag.add_node(ParamNode(
            result, 0.0, "joint", False,
            formula=lambda d, z=at_z: (
                d.get("outer_bottom_r")
                + (d.get("outer_top_r") - d.get("outer_bottom_r"))
                * (d.get(z) / d.get("height"))
            ),
            dependencies=["outer_bottom_r", "outer_top_r", "height", at_z],
        ))
