"""プレビュー画像（PNG）。部品やアセンブリを4方向から描く。

GUI を開かなくても形を確認できる。Claude Code はこの画像を読んで、作った形が意図どおりか確かめられる。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 画面のない環境でも描けるように
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from .assembly import Assembly  # noqa: E402
from .export import _parts, part_color  # noqa: E402
from .part import Part  # noqa: E402

# (タイトル, 仰角, 方位角)。画像内の文字は、日本語フォントがない環境でも読めるよう英語にしている
VIEWS = [
    ("iso", 25, -60),
    ("front (from -Y)", 0, -90),
    ("top (from +Z)", 90, -90),
    ("right (from +X)", 0, 0),
]
LIGHT = np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8])


def render(obj: Part | list[Part] | Assembly, path: str | Path, title: str = "", size: float = 9.0) -> Path:
    """4方向のプレビューを PNG に描く。寸法の目安として外形のサイズも書き込む。"""
    meshes = []
    for p in _parts(obj):
        verts, tris = p.solid().tessellate(0.1, 0.3)
        v = np.array([(q.X, q.Y, q.Z) for q in verts])
        meshes.append((v, np.array(tris), np.array(to_rgb(part_color(p)))))
    if not meshes:
        raise ValueError("描く部品がありません")

    allv = np.vstack([v for v, _, _ in meshes])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    center, span = (lo + hi) / 2, max((hi - lo).max(), 1e-3)

    fig = plt.figure(figsize=(size, size))
    for k, (name, elev, azim) in enumerate(VIEWS):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        for v, t, rgb in meshes:
            faces = v[t]
            n = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
            shade = 0.45 + 0.55 * np.abs(n @ LIGHT)
            colors = np.clip(rgb[None, :] * shade[:, None], 0, 1)
            ax.add_collection3d(Poly3DCollection(faces, facecolors=colors, edgecolors="none"))
        for i, c in enumerate(center):
            getattr(ax, f"set_{'xyz'[i]}lim")(c - span / 2, c + span / 2)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_proj_type("persp" if k == 0 else "ortho")
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.tick_params(labelsize=7)
    size_txt = f"size {hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} x {hi[2] - lo[2]:.1f} mm"
    fig.suptitle(f"{title}  {size_txt}".strip(), fontsize=12)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
