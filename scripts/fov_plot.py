"""Plot what the Turtle V2 sees: scene points projected with the fisheye model, image frames overlaid."""
import sys, os, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
sys.path.insert(0, os.getcwd())
import fov
from render import load_stl
for f in ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"):
    fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "font.size": 15})
D = "out/parts/"
def verts(n, step=1):
    v = load_stl(D + n).reshape(-1, 3)[::step]; return v
groups = [("frame", np.vstack([verts("Chassis.stl", 7), verts("Lid.stl")]), "#F06A1A", 1.0),
          ("battery", verts("ref_Battery_4S1P_18650.stl"), "#2F6FD0", 4.0),
          ("GPS", verts("ref_GPS.stl"), "#444", 4.0),
          ("motors", np.vstack([verts(f"ref_Motor{i}.stl") for i in range(4)]), "#222", 3.0),
          ("prop disks", np.vstack([fov.disk_points(*(verts(f"ref_Prop{i}.stl").mean(0)[:2]), 36.0, 44.45, 14, 180) for i in range(4)]), "#D21F3C", 2.0)]
piv = (95.0, 0.0, 17.0)
for up in (10, 40):
    L = fov.lens_position(piv, up, 9.0)
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    for name, P, col, s in groups:
        d = np.linalg.norm(P - L, axis=1); P = P[d > 2.5]
        xs, ys, th = fov.project(P, L, up)
        k = th < 120
        ax.scatter(-xs[k], ys[k], s=s, c=col, label=name, alpha=0.6, linewidths=0)
    for (nm, (Hh, Vh)), ls in zip(fov.FORMATS.items(), ("-", "--")):
        ax.add_patch(plt.Rectangle((-Hh, -Vh), 2 * Hh, 2 * Vh, fill=False, lw=2.5, ls=ls, ec="#111"))
        ax.text(-Hh + 2, Vh - 7, "DVR 16:9, 170°" if "rec" in nm else "FPV 4:3, 155°", fontsize=13)
    ax.set_xlim(-120, 120); ax.set_ylim(-70, 70); ax.set_aspect("equal")
    ax.set_xlabel("image x (deg off axis, equidistant fisheye)"); ax.set_ylabel("image y (deg)")
    m = json.load(open("out/fov_margins.json"))[str(up)]["props+motors"]
    ax.set_title(f"Turtle V2 view at {up}° uptilt: nothing inside the frames"
                 + (f"  (props {100 * (m - 1):.1f}% outside)" if np.isfinite(m) else "  (props behind the lens)"),
                 loc="left", fontweight="semibold", fontsize=19)
    ax.legend(loc="lower right", markerscale=4, frameon=False, ncol=5, fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout(); plt.savefig(f"out/video/raw/fpv_{up}deg.png"); plt.close()
print("ok")
