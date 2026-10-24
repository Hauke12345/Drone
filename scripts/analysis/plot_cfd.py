"""Plots for the CFD study."""
import sys, os, json, glob, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.tri as mtri
from matplotlib import font_manager as fm
sys.path.insert(0, "/home/claude/cfd"); sys.path.insert(0, "/home/claude/frame")
import post
from render import load_stl
for f in ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"):
    fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "font.size": 13})
ORANGE, INK = "#F06A1A", "#1F2328"

def section_segments(T, axis, val):
    """Segments where triangles cross the plane coord[axis] = val."""
    d = T[:, :, axis] - val
    segs = []
    for t, dd in zip(T, d):
        if dd.min() > 0 or dd.max() < 0:
            continue
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if dd[i] == dd[j]:
                continue
            if (dd[i] <= 0 <= dd[j]) or (dd[j] <= 0 <= dd[i]):
                s_ = dd[i] / (dd[i] - dd[j]); pts.append(t[i] + s_ * (t[j] - t[i]))
        if len(pts) >= 2:
            segs.append((pts[0], pts[1]))
    return segs

def outline(case, ax, plane="y", surfs=("frame", "frame_flatarms", "battery", "gps", "camera", "motors", "hood"), val=0.0):
    from matplotlib.collections import LineCollection
    ax_i = 1 if plane == "y" else (0 if plane == "x" else 2)
    keep = [i for i in range(3) if i != ax_i]
    for s in surfs:
        fn = f"{case}/constant/triSurface/{s}.stl"
        if not os.path.exists(fn):
            continue
        T = load_stl(fn)
        segs = section_segments(T, ax_i, val)
        if segs:
            L = [[(p[keep[0]], p[keep[1]]), (q[keep[0]], q[keep[1]])] for p, q in segs]
            if s in ("battery", "gps", "camera"):  # hood is a shell: outline only
                from scipy.spatial import ConvexHull
                P = np.array([pt for seg in L for pt in seg])
                if len(P) >= 3:
                    h = ConvexHull(P); ax.fill(P[h.vertices, 0], P[h.vertices, 1], color="#cfd3d8", zorder=3)
            ax.add_collection(LineCollection(L, colors="k", linewidths=1.0, zorder=4))

def slice_plot(case, name, title, out, plane=("y", (0, 1, 0), (0, 0, 0)), lim=((-0.35, 0.2), (-0.15, 0.15)), vmax=20, field="Umag"):
    D = post.sample(case, plane[1], plane[2], name)
    if plane[0] == "y":
        x, y = D[:, 0], D[:, 2]
    else:
        x, y = D[:, 0], D[:, 1]
    val = np.linalg.norm(D[:, 3:6], axis=1)
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    tri = mtri.Triangulation(x, y)
    # mask long triangles (holes inside the body)
    xt, yt = x[tri.triangles], y[tri.triangles]
    edge = np.max(np.hypot(np.roll(xt, 1, 1) - xt, np.roll(yt, 1, 1) - yt), axis=1)
    tri.set_mask(edge > 0.045)
    cs = ax.tricontourf(tri, val, levels=np.linspace(0, vmax, 41), cmap="turbo", extend="max")
    outline(case, ax, plane[0])
    ax.set_xlim(*lim[0]); ax.set_ylim(*lim[1]); ax.set_aspect("equal")
    ax.set_xlabel("x (m)"); ax.set_ylabel("z (m)" if plane[0] == "y" else "y (m)")
    cb = fig.colorbar(cs, ax=ax, shrink=0.8); cb.set_label("|U| (m/s)")
    ax.set_title(title, loc="left", fontweight="semibold", fontsize=17)
    plt.tight_layout(); plt.savefig(out); plt.close()

if __name__ == "__main__":
    what = sys.argv[1]
    if what == "cruise_slices":
        for c in sys.argv[2:]:
            a = int(c.split("_")[-1])
            slice_plot(c, "sliceY", f"Cruise 15 m/s, body pitched {a}° nose-down: centreline velocity",
                       f"/home/claude/cfd/{c}_sliceY.png")

def hover_diag_plot(case, title, out, vmax=16):
    n = np.array([1.0, -1.0, 0.0]) / np.sqrt(2); e1 = np.array([1.0, 1.0, 0.0]) / np.sqrt(2)
    D = post.sample(case, tuple(n), (0, 0, 0), "sliceDiag")
    P = D[:, :3]; s = P @ e1; z = P[:, 2]; val = np.linalg.norm(D[:, 3:6], axis=1)
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    tri = mtri.Triangulation(s, z)
    st, zt = s[tri.triangles], z[tri.triangles]
    edge = np.max(np.hypot(np.roll(st, 1, 1) - st, np.roll(zt, 1, 1) - zt), axis=1)
    tri.set_mask(edge > 0.045)
    cs = ax.tricontourf(tri, val, levels=np.linspace(0, vmax, 33), cmap="turbo", extend="max")
    from matplotlib.collections import LineCollection
    for sname in ("frame", "frame_flatarms", "battery", "gps", "camera", "motors", "hood"):
        fn = f"{case}/constant/triSurface/{sname}.stl"
        if not os.path.exists(fn):
            continue
        T = load_stl(fn); d = T @ n
        segs = []
        for t, dd in zip(T, d):
            if dd.min() > 0 or dd.max() < 0:
                continue
            pts = []
            for i in range(3):
                j = (i + 1) % 3
                if dd[i] != dd[j] and ((dd[i] <= 0 <= dd[j]) or (dd[j] <= 0 <= dd[i])):
                    f = dd[i] / (dd[i] - dd[j]); q = t[i] + f * (t[j] - t[i]); pts.append((q @ e1, q[2]))
            if len(pts) >= 2:
                segs.append(pts[:2])
        if segs:
            ax.add_collection(LineCollection(segs, colors="k", linewidths=1.0, zorder=4))
    for sx in (1, -1):
        c = sx * 0.0775
        ax.plot([c - 0.04445, c + 0.04445], [0.036, 0.036], color="w", lw=2.5, ls="--", zorder=5)
    ax.set_xlim(-0.2, 0.2); ax.set_ylim(-0.16, 0.08); ax.set_aspect("equal")
    ax.set_xlabel("along the FL–RR arm diagonal (m)"); ax.set_ylabel("z (m)")
    cb = fig.colorbar(cs, ax=ax, shrink=0.8); cb.set_label("|U| (m/s)")
    ax.set_title(title, loc="left", fontweight="semibold", fontsize=17)
    plt.tight_layout(); plt.savefig(out); plt.close()

if __name__ == "__main__" and sys.argv[1] == "hover":
    for c in sys.argv[2:]:
        lab = "v2 airfoil arms" if c == "hover_frame" else "flat 12 mm plate arms (carbon-frame style)"
        hover_diag_plot(c, f"Hover, 4 × 0.8 N actuator disks: {lab}", f"/home/claude/cfd/{c}_diag.png")
