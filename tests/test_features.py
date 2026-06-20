from pathlib import Path
import pytest
from jinja2 import Environment, FileSystemLoader
from app.features.body.tapered_body import TaperedBody
from app.features.body.cylinder_body import CylinderBody
from app.features.handle.bspline_handle import BSplineHandle
from app.features.handle.ring_handle import RingHandle

FEATURES_DIR = Path(__file__).parent.parent / "app" / "features"


def _render(template_rel_path: str, params: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(FEATURES_DIR)))
    tmpl = env.get_template(template_rel_path)
    return tmpl.render(**params)


def test_tapered_body_has_default_params():
    feat = TaperedBody()
    p = feat.get_default_params()
    assert p["height"] == 70.0
    assert p["outer_top_r"] == 40.0


def test_tapered_body_template_renders_height():
    code = _render("body/tapered_body.js.j2", {
        "height": 90, "outer_bottom_r": 29, "outer_top_r": 40,
        "thickness": 3, "inner_bottom_r": 26, "inner_top_r": 37, "bottom_thickness": 3,
    })
    assert "const height = 90" in code
    assert "cupBody" in code


def test_tapered_body_template_renders_updated_value():
    code = _render("body/tapered_body.js.j2", {
        "height": 120, "outer_bottom_r": 29, "outer_top_r": 40,
        "thickness": 3, "inner_bottom_r": 26, "inner_top_r": 37, "bottom_thickness": 3,
    })
    assert "const height = 120" in code


def test_cylinder_body_template_renders():
    code = _render("body/cylinder_body.js.j2", {
        "cylinder_height": 90, "cylinder_radius": 40,
        "cylinder_thickness": 2.5, "cylinder_inner_radius": 37.5,
        "cylinder_bottom_thickness": 2.5,
    })
    assert "cupBody" in code
    assert "40" in code


def test_bspline_handle_template_renders():
    code = _render("handle/bspline_handle.js.j2", {
        "section_width": 14, "section_height": 8,
        "lower_attach_z": 12.6, "upper_attach_z": 56.0,
        "lower_attach_x": -26.8, "upper_attach_x": -35.2,
        "handle_span_z": 43.4, "handle_outward_depth": 24.0,
        "handle_mid_z": 34.3, "handle_mid_outer_r": 34.5,
    })
    assert "cupHandle" in code
    assert "BSpline" in code


def test_ring_handle_template_renders():
    code = _render("handle/ring_handle.js.j2", {
        "ring_outer_r": 19.5, "ring_inner_r": 10.5,
        "ring_width": 15, "ring_attach_z": 60, "ring_attach_x": 58,
    })
    assert "cupHandle" in code
    assert "19.5" in code
