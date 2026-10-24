"""Minimal CalculiX .frd (ascii) reader: node coords and nodal result blocks."""
import numpy as np

def read_frd(fn):
    coords = {}; blocks = []
    with open(fn) as f:
        lines = f.readlines()
    i = 0; n = len(lines)
    while i < n:
        l = lines[i]
        if l.startswith("    2C"):
            i += 1
            ids, xyz = [], []
            while not lines[i].startswith(" -3"):
                s = lines[i]; ids.append(int(s[3:13])); xyz.append((float(s[13:25]), float(s[25:37]), float(s[37:49]))); i += 1
            coords = (np.array(ids), np.array(xyz))
        elif l.startswith(" -4  "):
            name = l.split()[1]; ncomp = int(l.split()[2])
            i += 1
            while lines[i].startswith(" -5"):
                i += 1
            ids, vals = [], []
            while not lines[i].startswith(" -3"):
                s = lines[i]
                ids.append(int(s[3:13]))
                m = (len(s.rstrip('\n')) - 13) // 12
                vals.append([float(s[13 + 12 * k:25 + 12 * k]) for k in range(min(m, 6))])
                i += 1
            blocks.append((name, np.array(ids), np.array(vals)))
        i += 1
    return coords, blocks

def von_mises(S):
    sxx, syy, szz, sxy, syz, szx = S.T
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * (sxy ** 2 + syz ** 2 + szx ** 2))
