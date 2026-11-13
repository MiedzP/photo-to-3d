"""Fast static 3-view render of an STL (front, right, top) with matplotlib. No GUI needed.

View conventions match the reference-photo naming used by the agent:
  front = camera at -Y looking toward +Y (X to the right, Z up)
  right = camera at +X looking toward -X (Y to the right, Z up)
  top   = camera at +Z looking down      (X to the right, Y up)
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

# name: (right axis, up axis, direction from the object toward the camera)
VIEWS = {
    "front": (np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, -1.0, 0])),
    "right": (np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])),
    "top": (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])),
}


def render_views(stl_path: Path, out_png: Path) -> Path:
    mesh = trimesh.load(str(stl_path), force="mesh")
    all_tris = mesh.triangles
    all_normals = mesh.face_normals
    # Sharp creases (>25 deg between neighbouring faces) show features that flat shading hides,
    # such as a shallow door recess. Only edges touching a camera-facing face are drawn.
    crease = mesh.face_adjacency_angles > np.radians(25)
    crease_pairs = mesh.face_adjacency[crease]
    crease_edges = mesh.face_adjacency_edges[crease]
    crease_verts = mesh.vertices[crease_edges]                # (m, 2, 3)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), dpi=110)
    for ax, (name, (right, up, toward)) in zip(axes, VIEWS.items()):
        facing = all_normals @ toward
        keep = facing > 1e-6                                   # back-face culling: only faces toward the camera
        tris, facing = all_tris[keep], facing[keep]
        pts2d = np.stack([tris @ right, tris @ up], axis=-1)   # (n, 3, 2)
        depth = (tris @ toward).mean(axis=1)                   # larger = nearer camera
        order = np.argsort(depth)                              # paint far faces first
        shade = 0.45 + 0.5 * np.clip(facing, 0, 1)
        colors = np.stack([shade, shade, shade * 1.02, np.ones_like(shade)], axis=1)[order]

        ax.add_collection(PolyCollection(pts2d[order], facecolors=colors, edgecolors="none"))
        if len(crease_verts):
            visible = (all_normals[crease_pairs] @ toward > 1e-6).any(axis=1)
            seg = np.stack([crease_verts[visible] @ right, crease_verts[visible] @ up], axis=-1)
            ax.add_collection(LineCollection(seg, colors="#202028", linewidths=0.7))
        lo = np.stack([tris @ right, tris @ up], axis=-1).reshape(-1, 2).min(axis=0) if len(tris) else np.zeros(2)
        hi = np.stack([tris @ right, tris @ up], axis=-1).reshape(-1, 2).max(axis=0) if len(tris) else np.ones(2)
        pad = 0.05 * float((hi - lo).max() or 1.0)
        ax.set_xlim(lo[0] - pad, hi[0] + pad)
        ax.set_ylim(lo[1] - pad, hi[1] + pad)
        ax.set_aspect("equal")
        ax.set_title(name)
        ax.axis("off")

    fig.tight_layout()
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)
    return out_png
