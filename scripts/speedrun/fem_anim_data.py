"""Map v3 FEM results onto the arms-stage surface mesh for the speedrun animation.

Writes speedrun/fem_anim.npz with, per triangle corner:
  tris (N,3,3) mm, vm_lc2, vm_lc3 (MPa), u_lc2, u_lc3 (mm), u_mode (normalised), plus scalar facts.
Nearest FE node per surface vertex (the arms are identical in the final v3 model; the pod surface
maps to the outer skin of the finished pod + lid).
"""
import sys, json, numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, "/home/claude/frame")
from frd_tools import read_frd, von_mises
from render import load_stl

T = load_stl("/home/claude/frame/out_rec/steps/01/chassis.stl")
V = T.reshape(-1, 3)
out = dict(tris=T.astype(np.float32))

(ids, X), blocks = read_frd("/home/claude/frame/out/fem_static/static.frd")
idx = {n: i for i, n in enumerate(ids)}
tree = cKDTree(X); _, nn = tree.query(V)
disp = [b for b in blocks if b[0] == "DISP"]; strs = [b for b in blocks if b[0] == "STRESS"]
for k, tag in ((1, "lc2"), (2, "lc3")):
    U = np.zeros((len(X), 3)); U[[idx[n] for n in disp[k][1]]] = disp[k][2][:, :3]
    S = np.zeros((len(X), 6)); S[[idx[n] for n in strs[k][1]]] = strs[k][2]
    out["vm_" + tag] = von_mises(S)[nn].astype(np.float32)
    out["u_" + tag] = U[nn].astype(np.float32)
    print(tag, "vm max on surface", float(out["vm_" + tag].max()), "u max", float(np.abs(U).max()))

(idm, Xm), bm = read_frd("/home/claude/frame/out/fem_v3_lid/modal.frd")
ixm = {n: i for i, n in enumerate(idm)}
dm = [b for b in bm if b[0] == "DISP"]
Um = np.zeros((len(Xm), 3)); Um[[ixm[n] for n in dm[6][1]]] = dm[6][2][:, :3]
_, nnm = cKDTree(Xm).query(V)
u = Um[nnm]; u /= np.abs(u).max()
out["u_mode"] = u.astype(np.float32)
fr = json.load(open("/home/claude/frame/out/fem_v3_lid/modal.json"))["freqs_hz"]
res = json.load(open("/home/claude/frame/out/fem_static/results.json"))
facts = dict(f_mode=fr[6], lc2_peak=res["LC2_landing_one_arm"]["max_vm"], lc3_peak=res["LC3_side_hit_motor"]["max_vm"],
             lc2_tip=float(np.linalg.norm(res["LC2_landing_one_arm"]["disp_FL"])),
             lc3_tip=float(np.linalg.norm(res["LC3_side_hit_motor"]["disp_FL"])))
np.savez_compressed("/home/claude/frame/speedrun/fem_anim.npz", **out)
json.dump(facts, open("/home/claude/frame/speedrun/fem_facts.json", "w"), indent=1)
print(facts)
