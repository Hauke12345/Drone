import sys, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
sys.path.insert(0, "."); import post
for f in ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"):
    fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "font.size": 14, "axes.spines.top": False, "axes.spines.right": False})
import glob, os
def parts(case):
    return [os.path.basename(p)[2:] for p in glob.glob(f"{case}/postProcessing/f_*")]
def F(case, n=200):
    return {p: post.forces(case, p, n)[0] for p in parts(case)}
q = 0.5 * 1.2 * 15 ** 2
res = {}
fig, axs = plt.subplots(1, 2, figsize=(16, 6.4), dpi=100, gridspec_kw=dict(width_ratios=[1.5, 1]))
a = axs[0]; xs = []; lab = []
groups = [("printed frame", ("frame",), "#F06A1A"), ("battery", ("battery",), "#2F6FD0"), ("nose fairing", ("hood",), "#7FB2F0"),
          ("motors", ("motors",), "#3C4043"), ("GPS + camera", ("gps", "camera"), "#9AA0A6")]
pos = 0
for ang in (0, 20):
    for ver, case in (("v2", f"cruise_{ang:02d}"), ("v3", f"v3_cruise_{ang:02d}")):
        f = F(case); bottom = 0.0
        for gi, (gl, ps, col) in enumerate(groups):
            d = sum(max(-f[p][0], 0) for p in ps if p in f)
            a.bar(pos, d, 0.7, bottom=bottom, color=col, label=gl if pos == 0 else None); bottom += d
        tot = -sum(v[0] for v in f.values()); res[case] = dict(drag=tot, lift=sum(v[2] for v in f.values()))
        neg = sum(-f[p][0] for p in f if -f[p][0] < 0)
        if neg < -0.01:
            a.text(pos, -0.06, f"fairing {neg:+.2f} N\n(suction, not stacked)", ha="center", fontsize=10.5, color="#2F6FD0")
        a.text(pos, bottom + 0.012, f"{tot:.2f} N", ha="center", fontweight="semibold")
        xs.append(pos); lab.append(f"{ver}\n{ang}°"); pos += 1
    pos += 0.6
a.set_xticks(xs); a.set_xticklabels(lab); a.tick_params(axis="x", pad=34); a.set_ylabel("drag at 15 m/s, no props (N)"); a.set_ylim(0, 0.72)

a.legend(frameon=False, fontsize=12, ncol=3, loc="upper left")
a.set_title("Cruise drag by component", loc="left", fontweight="semibold")
a = axs[1]
h2 = -sum(v[2] for v in F("hover_frame", 300).values()); h3 = -sum(v[2] for v in F("v3_hover_frame", 300).values())
res["hover"] = dict(v2=h2, v3=h3)
a.bar([0, 1], [100 * h2 / 3.2, 100 * h3 / 3.2], 0.6, color=["#9AA0A6", "#F06A1A"])
for i, h in enumerate((h2, h3)):
    a.text(i, 100 * h / 3.2 + 0.15, f"{100 * h / 3.2:.1f}%\n({h:.3f} N)", ha="center", fontweight="semibold")
a.set_xticks([0, 1]); a.set_xticklabels(["v2", "v3"]); a.set_ylabel("hover download (% of thrust)"); a.set_ylim(0, 6)
a.set_title("Hover: thrust lost to the airframe", loc="left", fontweight="semibold")
fig.suptitle("CFD v2 → v3 (battery nose fairing, flared roots, fewer openings)", x=0.01, ha="left", fontweight="semibold", fontsize=19)
plt.tight_layout(); plt.savefig("cfd_v2_v3.png"); json.dump(res, open("cfd_v2_v3.json", "w"), indent=1); print(res)
