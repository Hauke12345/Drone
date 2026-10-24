"""CFD post-processing: force averages per patch, slice plots.  python post.py <case>..."""
import os, sys, glob, json, subprocess, numpy as np

RHO = 1.2; U0 = 15.0
def forces(case, patch, nlast=200):
    fs = sorted(glob.glob(f"{case}/postProcessing/f_{patch}/*/force.dat"))
    rows = []
    for fn in fs:
        for l in open(fn):
            if l.startswith("#") or not l.strip():
                continue
            v = [float(x) for x in l.replace("(", " ").replace(")", " ").split()]
            rows.append(v)
    A = np.array(rows)
    return A[-nlast:, 1:4].mean(0), A[-nlast:, 1:4].std(0), A

def write_sample_dict(case, normal, point, name):
    d = f"""FoamFile {{ version 2.0; format ascii; class dictionary; object {name}; }}
functions {{ {name} {{ type surfaces; libs (sampling); writeControl writeTime; surfaceFormat raw; fields (U p k);
surfaces {{ {name} {{ type cuttingPlane; point ({point[0]} {point[1]} {point[2]}); normal ({normal[0]} {normal[1]} {normal[2]}); interpolate false; }} }} }} }}
"""
    open(f"{case}/system/{name}", "w").write(d)

def sample(case, normal, point, name):
    write_sample_dict(case, normal, point, name)
    subprocess.run(f"bash -c 'source /home/claude/cfd/ofenv.sh && cd {case} && postProcess -latestTime -fields \"(U p k)\" -dict system/{name} > log.{name} 2>&1'", shell=True)
    fs = glob.glob(f"{case}/postProcessing/{name}/*/U_{name}.raw") or glob.glob(f"{case}/postProcessing/{name}/*/{name}_U.raw") \
        or glob.glob(f"{case}/postProcessing/{name}/*/*U*.raw")
    if not fs:
        return None
    D = np.loadtxt(fs[0], comments="#")
    return D

if __name__ == "__main__":
    out = {}
    for case in sys.argv[1:]:
        pats = [os.path.basename(p)[2:] for p in glob.glob(f"{case}/postProcessing/f_*")]
        res = {}
        tot = np.zeros(3)
        for p in pats:
            m, s, A = forces(case, p)
            res[p] = dict(F=m.tolist(), std=s.tolist(), n=len(A)); tot += m
        res["total"] = dict(F=tot.tolist())
        out[case] = res
        print(case, {k: np.round(v["F"], 4).tolist() for k, v in res.items()})
    json.dump(out, open("/home/claude/cfd/forces.json", "w"), indent=1)
