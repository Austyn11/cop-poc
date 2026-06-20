from pathlib import Path
from app.features.base import BodyFeature
from app.graph.model import DAG, ParamNode


class CylinderBody(BodyFeature):
    height_param = "cylinder_height"
    wall_thickness_param = "cylinder_thickness"
    reference_radius_param = "cylinder_radius"

    def get_default_params(self) -> dict[str, float]:
        return {
            "cylinder_height": 90.0,
            "cylinder_radius": 40.0,
            "cylinder_thickness": 2.5,
            "cylinder_bottom_thickness": 2.5,
        }

    def get_template_path(self) -> Path:
        return Path(__file__).parent / "cylinder_body.js.j2"

    def add_outer_r_node(self, dag: DAG, at_z: str, result: str) -> None:
        """원통형 body: Z에 무관하게 외면 반경 일정."""
        dag.add_node(ParamNode(
            result, 0.0, "joint", False,
            formula=lambda d: d.get("cylinder_radius"),
            dependencies=["cylinder_radius"],
        ))
