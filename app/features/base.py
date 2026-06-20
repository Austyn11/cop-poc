from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.graph.model import DAG


class FeatureTemplate(ABC):
    @abstractmethod
    def get_default_params(self) -> dict[str, float]: ...

    @abstractmethod
    def get_template_path(self) -> Path: ...


class BodyFeature(FeatureTemplate, ABC):
    """body feature가 handle에 노출하는 기하 인터페이스."""

    @property
    @abstractmethod
    def height_param(self) -> str:
        """body 높이 파라미터 이름 ('height', 'cylinder_height' 등)."""

    @property
    @abstractmethod
    def wall_thickness_param(self) -> str:
        """body 벽 두께 파라미터 이름 ('thickness', 'cylinder_thickness' 등)."""

    @property
    @abstractmethod
    def reference_radius_param(self) -> str:
        """outward depth 계산에 쓸 기준 반경 파라미터 이름 ('outer_top_r', 'cylinder_radius' 등)."""

    @abstractmethod
    def add_outer_r_node(self, dag: "DAG", at_z: str, result: str) -> None:
        """at_z 파라미터 이름의 Z 위치에서 외면 반경을 계산하는 노드를 dag에 추가."""


class HandleFeature(FeatureTemplate, ABC):
    """handle feature가 body 인터페이스를 받아 joint sub-graph를 직접 조립."""

    @abstractmethod
    def build_joint_nodes(self, dag: "DAG", body: BodyFeature) -> None:
        """body 인터페이스를 주입받아 joint sub-graph 노드들을 dag에 추가."""
