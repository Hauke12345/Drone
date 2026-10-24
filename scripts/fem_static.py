"""Static load cases for the v2 frame (chassis + lid tied), CalculiX, linear elastic PC.

Support: the battery footprint on the lid is held fixed (the 200 g pack's inertia reacts the loads).
Loads are spread over the motor pad top nodes, never applied at single nodes.
  LC1  full throttle punch: 3.0 N up at each motor (EX1404 + 3.5" tri, 4S, roughly max static thrust)
  LC2  landing on one arm: 30 N up at the front-left motor pad
  LC3  side hit on a motor: 20 N tangential (in-plane) at the front-left motor pad
Units: N, mm, tonne, s -> stress in MPa.
"""
import os, re, sys, subprocess, json
import numpy as np

import os as _os
BASE = _os.environ.get("BASE", "out")
OUT = BASE + "/fem_static"; os.makedirs(OUT, exist_ok=True)
BIN = "/opt/mamba/envs/fc/bin"
CLMAX = float(os.environ.get("CLMAX", "2.0"))
E, NU = 2300.0, 0.37
RM = 155.0 / 2; ZARM = 22.0; ZRIM = 27.0; LID_T = 1.6
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

nodesC, elemsC = mesh(BASE + "/chassis_only.step", "chassis")
nodesL, elemsL = mesh(BASE + "/lid_only.step", "lid")
offN, offE = max(nodesC) + 1, max(e[0] for e in elemsC) + 1
nodes = dict(nodesC); elems = [list(e) for e in elemsC]
lid_nodes = []
for n, x in nodesL.items():
    nodes[n + offN] = x; lid_nodes.append(n + offN)
for e in elemsL:
    elems.append([e[0] + offE] + [n + offN for n in e[1:]])
ids = np.array(list(nodes)); X = np.array([nodes[n] for n in ids])
cm = np.isin(ids, list(nodesC)); lm = ~cm
print("nodes", len(ids), "elements", len(elems))

def pad_nodes(a):
    c = np.array([RM * np.cos(np.radians(a)), RM * np.sin(np.radians(a))])
    return ids[cm & (np.abs(X[:, 2] - ZARM) < 0.05) & (np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) < 9.6)]
zt = ZRIM + LID_T
fixed = ids[lm & (np.abs(X[:, 2] - zt) < 0.05) & (X[:, 0] > -35) & (X[:, 0] < 31) & (np.abs(X[:, 1]) < 18.5)]
print("fixed nodes", len(fixed))

# tie lid to rim
faces_def = {1: (0, 1, 2), 2: (0, 3, 1), 3: (1, 3, 2), 4: (2, 3, 0)}
rim = [(e[0], f) for e in elemsC for f, (i, j, k) in faces_def.items()
       if all(abs(nodesC[e[1:5][q]][2] - ZRIM) < 1e-3 for q in (i, j, k))]
slave = ids[lm & (np.abs(X[:, 2] - ZRIM) < 1e-3)]

def cload(sel, F):
    s = ""
    for n in sel:
        for d in range(3):
            if abs(F[d]) > 0:
                s += f"{n},{d + 1},{F[d] / len(sel):.6e}\n"
    return "*CLOAD, OP=NEW\n" + s

a0 = np.radians(45); tan0 = np.array([-np.sin(a0), np.cos(a0), 0.0])
cases = {
    "LC1_full_throttle": "".join(cload(pad_nodes(a), (0, 0, 3.0)) for a in ANG),
    "LC2_landing_one_arm": cload(pad_nodes(45), (0, 0, 30.0)),
    "LC3_side_hit_motor": cload(pad_nodes(45), tuple(20.0 * tan0)),
}
with open(os.path.join(OUT, "static.inp"), "w") as f:
    f.write("*NODE, NSET=NALL\n")
    for n in ids:
        x, y, z = nodes[n]; f.write(f"{n},{x:.6f},{y:.6f},{z:.6f}\n")
    f.write("*ELEMENT, TYPE=C3D10, ELSET=EALL\n")
    for e in elems:
        f.write(",".join(map(str, e)) + "\n")
    f.write("*NSET, NSET=FIX\n" + "\n".join(map(str, fixed)) + "\n")
    f.write("*SURFACE, NAME=SLAVE, TYPE=NODE\n" + "\n".join(map(str, slave)) + "\n")
    f.write("*SURFACE, NAME=RIM, TYPE=ELEMENT\n" + "\n".join(f"{e},S{k}" for e, k in rim) + "\n")
    f.write("*TIE, NAME=LIDTIE, POSITION TOLERANCE=0.05, ADJUST=NO\nSLAVE,RIM\n")
    f.write(f"*MATERIAL, NAME=PC\n*ELASTIC\n{E},{NU}\n*SOLID SECTION, ELSET=EALL, MATERIAL=PC\n")
    f.write("*BOUNDARY\nFIX,1,3\n")
    for name, ld in cases.items():
        f.write(f"*STEP\n*STATIC\n{ld}*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n")
subprocess.run([f"{BIN}/ccx", "-i", "static"], cwd=OUT, check=True, stdout=open(os.path.join(OUT, "ccx.log"), "w"))
json.dump(dict(cases=list(cases), nodes=len(ids)), open(os.path.join(OUT, "cases.json"), "w"))
print("solved")
