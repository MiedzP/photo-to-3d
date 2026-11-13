"""Repair a raw FreeCAD STL and make it print-ready: watertight, on the bed, scaled."""
from pathlib import Path

import numpy as np
import trimesh


def prepare_for_print(
    src: Path,
    dst: Path,
    longest_side_mm: float | None = None,
    height_mm: float | None = None,
) -> dict:
    mesh = trimesh.load(str(src), force="mesh")
    warnings: list[str] = []

    mesh.merge_vertices()
    trimesh.repair.fix_normals(mesh)
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_normals(mesh)
    watertight = bool(mesh.is_watertight)
    if not watertight:
        warnings.append("mesh is not watertight after repair; check the model for open edges")

    # Sit on the bed: centre in XY, lowest point at Z = 0.
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])

    if longest_side_mm and height_mm:
        raise ValueError("pass longest_side_mm or height_mm, not both")
    extents = mesh.extents
    if longest_side_mm:
        mesh.apply_scale(longest_side_mm / float(extents.max()))
    elif height_mm:
        mesh.apply_scale(height_mm / float(extents[2]))

    if watertight and mesh.volume < 0:
        warnings.append("negative volume: normals were inverted")
        mesh.invert()

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(dst))

    return {
        "watertight": watertight,
        "volume_mm3": float(mesh.volume) if watertight else None,
        "extents_mm": [round(float(v), 2) for v in mesh.extents],
        "faces": int(len(mesh.faces)),
        "warnings": warnings,
    }
