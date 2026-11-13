"""Decimate a print-ready STL, export GLB, and embed it in a self-contained 360° viewer HTML."""
import base64
from pathlib import Path

import trimesh

from .config import ROOT

TEMPLATE = ROOT / "templates" / "viewer.html"
SKIN = [214, 210, 200, 255]  # light neutral, reads well on the dark viewer background


def export_viewer(stl_path: Path, out_dir: Path, title: str, max_faces: int = 60000) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh = trimesh.load(str(stl_path), force="mesh")
    original_faces = len(mesh.faces)
    if original_faces > max_faces:
        mesh = mesh.simplify_quadric_decimation(face_count=max_faces)
    mesh.visual.face_colors = SKIN

    glb_path = out_dir / "model.glb"
    mesh.export(str(glb_path), file_type="glb")

    b64 = base64.b64encode(glb_path.read_bytes()).decode("ascii")
    html = TEMPLATE.read_text(encoding="utf-8").replace("{{TITLE}}", title).replace("{{MODEL_B64}}", b64)
    viewer = out_dir / "viewer.html"
    viewer.write_text(html, encoding="utf-8")

    return {
        "glb": str(glb_path),
        "viewer": str(viewer),
        "faces_before": original_faces,
        "faces_after": int(len(mesh.faces)),
        "glb_bytes": glb_path.stat().st_size,
    }
