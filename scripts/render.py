"""Shaded matplotlib renders of STL meshes (no GPU needed)."""
import struct, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def load_stl(fn):
    with open(fn, "rb") as f:
        data = f.read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        v = [list(map(float, l.split()[1:4])) for l in data.decode().splitlines() if l.strip().startswith("vertex")]
        return np.array(v).reshape(-1, 3, 3)
    n = struct.unpack("<I", data[80:84])[0]
    a = np.frombuffer(data[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return a["v"].reshape(-1, 3, 3).astype(float)

def shade(tris, rgb, light, view):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    n = np.where((n @ view)[:, None] < 0, -n, n)          # face the viewer
    d = np.clip(n @ light, 0, 1)
    spec = np.clip(n @ ((light + view) / np.linalg.norm(light + view)), 0, 1) ** 30
    c = np.asarray(rgb)[None, :] * (0.32 + 0.68 * d[:, None]) + 0.25 * spec[:, None]
    return np.clip(c, 0, 1)

def view_vec(elev, azim):
    e, a = np.radians(elev), np.radians(azim)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])

def draw(ax, parts, elev, azim, bounds=None, alpha=None):
    """parts: list of (tris, rgb[, alpha])"""
    vv = view_vec(elev, azim)
    light = view_vec(elev + 35, azim - 40)
    allp = []
    for p in parts:
        tris, rgb = p[0], p[1]
        al = p[2] if len(p) > 2 else 1.0
        fc = shade(tris, rgb, light, vv)
        pc = Poly3DCollection(tris, facecolors=np.c_[fc, np.full(len(fc), al)], edgecolors="none", linewidths=0)
        ax.add_collection3d(pc)
        allp.append(tris.reshape(-1, 3))
    P = np.vstack(allp)
    if bounds is None:
        lo, hi = P.min(0), P.max(0)
    else:
        lo, hi = bounds
    c = (lo + hi) / 2; r = (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_proj_type("persp", focal_length=0.35)

def decimate(tris, maxn):
    if len(tris) <= maxn:
        return tris
    idx = np.random.default_rng(0).choice(len(tris), maxn, replace=False)
    return tris[np.sort(idx)]
