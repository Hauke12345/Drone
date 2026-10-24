"""Free-free modal analysis of the printed frame with CalculiX.

Chassis (and optionally lid) are meshed with gmsh as 2nd-order tets. With LID=1 the lid
is tied to the chassis rim (*TIE), i.e. the lid is assumed to act as a bonded shear panel
(upper bound for a screwed lid with a shear tongue). Component masses (motors+props,
battery, camera, GPS, boards) are lumped on the nodes where they attach.
Units: N, mm, tonne, s.   Usage: python fem_modal.py [tag]
"""
import os, re, sys, subprocess, json
import numpy as np

TAG = sys.argv[1] if len(sys.argv) > 1 else "v2"
OUT = os.path.join("out", "fem_" + TAG); os.makedirs(OUT, exist_ok=True)
BIN = "/opt/mamba/envs/fc/bin"
CLMAX = float(os.environ.get("CLMAX", "1.4"))
LID = bool(int(os.environ.get("LID", "1")))
EXTRA = bool(int(os.environ.get("EXTRA_MASSES", "1")))
E, NU, RHO = 2300.0, 0.37, 1.20e-9          # polycarbonate
RM = 155.0 / 2; ZTOP_ARM = 22.0; ZRIM = 27.0; LID_T = 1.6
ANG = [45, 135, 225, 315]

def mesh(step, name):
    inp = os.path.join(OUT, name + ".inp")
    subprocess.run([f"{BIN}/gmsh", step, "-3", "-order", "2", "-clmax", str(CLMAX), "-clmin", "0.5",
                    "-setnumber", "Mesh.SecondOrderLinear", "1", "-format", "inp", "-o", inp, "-nt", "2"],
                   check=True, stdout=subprocess.DEVNULL)
    nodes, elems, mode = {}, [], None
    for line in open(inp):
        if line.startswith("*"):
            l = line.upper()
            mode = "N" if l.startswith("*NODE") else ("E" if ("*ELEMENT" in l and "C3D10" in l) else None)
            continue
        if mode == "N":
            p = line.split(","); nodes[int(p[0])] = tuple(map(float, p[1:4]))
        elif mode == "E":
            elems.append([int(x) for x in line.replace(" ", "").split(",") if x.strip()])
    used = sorted({n for e in elems for n in e[1:]})
    return {n: nodes[n] for n in used}, elems

nodesC, elemsC = mesh("out/chassis_only.step", "chassis")
nodes, elems = dict(nodesC), [list(e) for e in elemsC]
offN, offE = max(nodes) + 1, max(e[0] for e in elems) + 1
lid_nodes = []
if LID:
    nodesL, elemsL = mesh("out/lid_only.step", "lid")
    for n, x in nodesL.items():
        nodes[n + offN] = x; lid_nodes.append(n + offN)
    for e in elemsL:
        elems.append([e[0] + offE] + [n + offN for n in e[1:]])
print("nodes", len(nodes), "C3D10", len(elems))
ids = np.array(list(nodes)); X = np.array([nodes[n] for n in ids])

# ---- lumped masses
mass_lines, eid = [], max(e[0] for e in elems) + 1
def add_mass(sel, m_g, label):
    global eid
    sel = list(sel); assert len(sel) > 0, label
    print(f"  mass {label:8s} {m_g:6.1f} g on {len(sel)} nodes")
    for n in sel:
        mass_lines.append((eid, int(n), m_g * 1e-6 / len(sel))); eid += 1
chassis_mask = np.isin(ids, list(nodesC))
for a in ANG:
    c = np.array([RM * np.cos(np.radians(a)), RM * np.sin(np.radians(a))])
    add_mass(ids[chassis_mask & (np.abs(X[:, 2] - ZTOP_ARM) < 0.05) & (np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) < 9.6)], 12.2, "motor")
if EXTRA:
    add_mass(ids[chassis_mask & (np.hypot(X[:, 0] - 95, X[:, 2] - 17) < 2.2) & (np.abs(X[:, 1]) > 6)], 4.0, "camera")
    sel = []
    for xs in (-19, 19):
        for sx in (1, -1):
            for sy in (1, -1):
                q = (xs + sx * 12.75, sy * 12.75)
                sel += list(ids[chassis_mask & (np.abs(X[:, 2] - 8.0) < 0.05) & (np.hypot(X[:, 0] - q[0], X[:, 1] - q[1]) < 2.7)])
    add_mass(sel, 13.0, "boards")
    if LID:
        lm = np.isin(ids, lid_nodes); zt = ZRIM + LID_T
        add_mass(ids[lm & (np.abs(X[:, 2] - zt) < 0.05) & (X[:, 0] > -35) & (X[:, 0] < 31) & (np.abs(X[:, 1]) < 18.5)], 200.0, "battery")
        add_mass(ids[lm & (np.abs(X[:, 2] - (zt - 0.5)) < 0.05) & (np.abs(X[:, 0] - 54) < 13) & (np.abs(X[:, 1]) < 13)], 8.0, "gps")

# ---- tie: lid underside nodes (slave) to chassis rim faces (master)
tie = ""
if LID:
    faces_def = {1: (0, 1, 2), 2: (0, 3, 1), 3: (1, 3, 2), 4: (2, 3, 0)}
    rim = []
    for e in elemsC:
        cn = e[1:5]
        for fid, (i, j, k) in faces_def.items():
            if all(abs(nodesC[cn[q]][2] - ZRIM) < 1e-3 for q in (i, j, k)):
                rim.append((e[0], fid))
    lm = np.isin(ids, lid_nodes)
    slave = ids[lm & (np.abs(X[:, 2] - ZRIM) < 1e-3)]
    print("  tie: master faces", len(rim), "slave nodes", len(slave))
    tie = "*SURFACE, NAME=SLAVE, TYPE=NODE\n" + "\n".join(str(n) for n in slave) + "\n"
    tie += "*SURFACE, NAME=RIM, TYPE=ELEMENT\n" + "\n".join(f"{e},S{f}" for e, f in rim) + "\n"
    tie += "*TIE, NAME=LIDTIE, POSITION TOLERANCE=0.05, ADJUST=NO\nSLAVE,RIM\n"

with open(os.path.join(OUT, "modal.inp"), "w") as f:
    f.write("*NODE, NSET=NALL\n")
    for n in ids:
        x, y, z = nodes[n]; f.write(f"{n},{x:.6f},{y:.6f},{z:.6f}\n")
    f.write("*ELEMENT, TYPE=C3D10, ELSET=EALL\n")
    for e in elems:
        f.write(",".join(map(str, e)) + "\n")
    for k, (e_, n, m) in enumerate(mass_lines):
        f.write(f"*ELEMENT, TYPE=MASS, ELSET=M{k}\n{e_},{n}\n*MASS, ELSET=M{k}\n{m:.6e}\n")
    f.write(tie)
    f.write(f"*MATERIAL, NAME=PC\n*ELASTIC\n{E},{NU}\n*DENSITY\n{RHO}\n")
    f.write("*SOLID SECTION, ELSET=EALL, MATERIAL=PC\n")
    f.write("*STEP\n*FREQUENCY, SOLVER=SPOOLES\n14\n*NODE FILE\nU\n*END STEP\n")

subprocess.run([f"{BIN}/ccx", "-i", "modal"], cwd=OUT, check=True, stdout=open(os.path.join(OUT, "ccx.log"), "w"))
dat = open(os.path.join(OUT, "modal.dat")).read()
blk = dat.split("E I G E N V A L U E   O U T P U T")[1].split("P A R T I C I P")[0]
freqs = [float(l.split()[3]) for l in blk.splitlines() if re.match(r"\s+\d+\s+[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+", l)]
print("frequencies (Hz):", [round(x, 1) for x in freqs])
json.dump(dict(freqs_hz=freqs, nodes=len(nodes), elements=len(elems), clmax=CLMAX, lid=LID, masses=EXTRA),
          open(os.path.join(OUT, "modal.json"), "w"), indent=1)
