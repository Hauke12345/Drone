"""Precompute colours, exaggerated shapes, streamline tubes and bead paths for the Blender animation.
(system python: numpy + matplotlib) -> speedrun/vis.npz + vis.json
"""
import json, numpy as np
from matplotlib import colormaps
D = "/home/claude/frame/speedrun"
turbo, viri = colormaps["turbo"], colormaps["viridis"]
out, meta = {}, {}

# ---------------- FEM on the arms-stage mesh (metres)
F = np.load(f"{D}/fem_anim.npz")
tris_all = F["tris"].reshape(-1, 3) * 0.001
_, first, inv = np.unique(np.round(tris_all, 7), axis=0, return_index=True, return_inverse=True)
inv = inv.ravel()
tris = tris_all[first]                                   # welded vertices
fsel = lambda a: a[first]
out["fem_v"] = tris.astype(np.float32); out["fem_f"] = inv.reshape(-1, 3).astype(np.int32)
print("fem welded", len(tris_all), "->", len(tris))
SMAX = 20.0
for tag, target in (("lc2", 0.0065), ("lc3", 0.0070)):
    out[f"fem_c_{tag}"] = turbo(np.clip(fsel(F["vm_" + tag]) / SMAX, 0, 1))[:, :3].astype(np.float32)
    u = fsel(F["u_" + tag]) * 0.001; s = target / np.abs(u).max()
    out[f"fem_d_{tag}"] = (tris + s * u).astype(np.float32); meta[f"scale_{tag}"] = float(s)
um = fsel(F["u_mode"]); amp = np.linalg.norm(um, axis=1)
out["fem_c_mode"] = viri(amp / amp.max())[:, :3].astype(np.float32)
out["fem_d_mode"] = (tris + 0.008 * um / np.abs(um).max()).astype(np.float32)
meta["fem_smax"] = SMAX

# ---------------- streamlines -> tubes in chunks + bead paths
SLOW = 37.0                         # video time / physical time
def tubes(name, keep, vmax, nchunk=8, r=0.00036, sides=5, spacing=0.0028, nbead=2, seed=0):
    d = np.load(f"{D}/{name}.npz"); P, S, off = d["pts"], d["spd"], d["off"]
    rng = np.random.default_rng(seed)
    chunks = [dict(v=[], f=[], c=[]) for _ in range(nchunk)]
    beads = []
    for a, b in zip(off[:-1], off[1:]):
        p, s = P[a:b], S[a:b]
        if name == "stream_cruise" and p[0, 1] < -0.001:
            continue                                   # only the far half: lines in front would hide the frame
        m = keep(p)
        if m.sum() < 4:
            continue
        idx = np.where(m)[0]; p, s = p[idx[0]:idx[-1] + 1], s[idx[0]:idx[-1] + 1]
        # resample by arc length
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1); sl = np.concatenate([[0], np.cumsum(seg)])
        if sl[-1] < 0.02:
            continue
        q = np.arange(0, sl[-1], spacing)
        pr = np.stack([np.interp(q, sl, p[:, k]) for k in range(3)], 1); sr = np.interp(q, sl, s)
        # physical time along the line
        tl = np.concatenate([[0], np.cumsum(np.diff(q) / np.maximum(0.5 * (sr[1:] + sr[:-1]), 0.8))])
        # tube rings
        tang = np.gradient(pr, axis=0); tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-12
        ref = np.where(np.abs(tang[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
        n1 = np.cross(tang, ref); n1 /= np.linalg.norm(n1, axis=1)[:, None]; n2 = np.cross(tang, n1)
        ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
        ring = pr[:, None, :] + r * (np.cos(ang)[None, :, None] * n1[:, None, :] + np.sin(ang)[None, :, None] * n2[:, None, :])
        col = turbo(np.clip(sr / vmax, 0, 1))[:, :3]
        n = len(pr); frac = q / q[-1]
        ck = np.minimum((frac * nchunk).astype(int), nchunk - 1)
        for k in range(nchunk):
            sel = np.where(ck == k)[0]
            if len(sel) == 0:
                continue
            i0, i1 = sel[0], min(sel[-1] + 1, n - 1)        # overlap one point so chunks join
            if i1 <= i0:
                continue
            C = chunks[k]; base = sum(len(x) for x in C["v"])
            vv = ring[i0:i1 + 1].reshape(-1, 3); C["v"].append(vv); C["c"].append(np.repeat(col[i0:i1 + 1], sides, axis=0))
            m_ = i1 - i0
            jj = np.arange(m_)[:, None] * sides; aa = np.arange(sides)[None, :]; bb = (aa + 1) % sides
            quads = np.stack([jj + aa, jj + bb, jj + sides + bb, jj + sides + aa], -1).reshape(-1, 4) + base
            C["f"].append(quads)
        for _ in range(nbead):
            beads.append(dict(p=pr, t=tl, phase=float(rng.uniform(0, 1))))
    res = []
    for k, C in enumerate(chunks):
        res.append((np.concatenate(C["v"]).astype(np.float32), np.concatenate(C["f"]).astype(np.int32),
                    np.concatenate(C["c"]).astype(np.float32)))
    return res, beads

def bead_track(b, nframes, fps=24, step=2):
    T = b["t"][-1]; dur = nframes / fps / SLOW
    t0 = b["phase"] * max(T - dur, 0.0)
    fr = np.arange(0, nframes + 1, step)
    tt = np.clip(t0 + fr / fps / SLOW, 0, T)
    return np.stack([np.interp(tt, b["t"], b["p"][:, k]) for k in range(3)], 1).astype(np.float32)

for name, keep, vmax, nb, tag in (
        ("stream_cruise", lambda p: (p[:, 0] > -0.42) & (p[:, 0] < 0.33), 20.0, 48, "cruise"),
        ("stream_hover", lambda p: p[:, 2] > -0.24, 20.0, 40, "hover")):
    ch, beads = tubes(name, keep, vmax)
    for k, (v, f, c) in enumerate(ch):
        out[f"{tag}_v{k}"], out[f"{tag}_f{k}"], out[f"{tag}_c{k}"] = v, f, c
    tr = np.stack([bead_track(b, nb) for b in beads])
    out[f"{tag}_beads"] = tr
    meta[f"{tag}_nchunk"] = len(ch); meta[f"{tag}_bead_frames"] = nb
    print(tag, "chunks", [len(x[0]) for x in ch], "beads", tr.shape)
np.savez_compressed(f"{D}/vis.npz", **out)
json.dump(meta, open(f"{D}/vis.json", "w"), indent=1)
print(meta)
