"""Generate OpenFOAM v2412 cases for the AeroFrame v2 study.

  python make_case.py cruise <pitch_deg>        body drag, 15 m/s, nose-down pitch, no props
  python make_case.py hover  <frame|frame_flatarms>   4 actuator disks at hover thrust, still air

simpleFoam, k-omega SST, wall functions, snappyHexMesh. Units SI (geometry in metres).
"""
import os, sys, shutil, math, textwrap

STL = os.environ.get("STL_DIR", "/home/claude/frame/out/cfd_stl")
PFX = os.environ.get("CASE_PREFIX", "")
HDR = """FoamFile {{ version 2.0; format ascii; class {cls}; object {obj}; }}
"""
mode = sys.argv[1]
if mode == "cruise":
    pitch = float(sys.argv[2]); case = f"{PFX}cruise_{int(pitch):02d}"
    surfaces = ["frame", "battery", "gps", "camera", "motors"]
else:
    variant = sys.argv[2]; case = f"{PFX}hover_{variant}"
    surfaces = [variant, "battery", "gps", "camera", "motors"]
if os.path.exists(os.path.join(STL, "hood.stl")):
    surfaces.append("hood")
C = os.path.join("/home/claude/cfd", case)
shutil.rmtree(C, ignore_errors=True)
for d in ("0", "constant/triSurface", "system"):
    os.makedirs(os.path.join(C, d), exist_ok=True)

def w(path, cls, obj, body):
    with open(os.path.join(C, path), "w") as f:
        f.write(HDR.format(cls=cls, obj=obj) + textwrap.dedent(body))

for s in surfaces:
    shutil.copy(os.path.join(STL, s + ".stl"), os.path.join(C, "constant/triSurface", s + ".stl"))

U0 = 15.0
if mode == "cruise":
    bb = dict(xmin=-0.9, xmax=0.5, ymin=-0.45, ymax=0.45, zmin=-0.45, zmax=0.5, d=0.04)
    boxes = [("wake2", (-0.40, -0.20, -0.16), (0.22, 0.20, 0.20), 2),
             ("near3", (-0.16, -0.14, -0.07), (0.16, 0.14, 0.13), 3)]
    loc = (0.31, 0.31, 0.31)
else:
    bb = dict(xmin=-0.45, xmax=0.45, ymin=-0.45, ymax=0.45, zmin=-0.70, zmax=0.35, d=0.04)
    boxes = [("wake2", (-0.25, -0.25, -0.40), (0.25, 0.25, 0.12), 2),
             ("near3", (-0.15, -0.15, -0.12), (0.15, 0.15, 0.08), 3)]
    loc = (0.31, 0.31, 0.21)
nx = round((bb["xmax"] - bb["xmin"]) / bb["d"]); ny = round((bb["ymax"] - bb["ymin"]) / bb["d"]); nz = round((bb["zmax"] - bb["zmin"]) / bb["d"])

# ---------------- mesh
x0, x1, y0, y1, z0, z1 = bb["xmin"], bb["xmax"], bb["ymin"], bb["ymax"], bb["zmin"], bb["zmax"]
if mode == "cruise":
    patches = f"""
    inlet  {{ type patch; faces ((1 2 6 5)); }}
    outlet {{ type patch; faces ((0 4 7 3)); }}
    sides  {{ type patch; faces ((0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7)); }}
"""
else:
    patches = f"""
    open   {{ type patch; faces ((1 2 6 5) (0 4 7 3) (0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7)); }}
"""
w("system/blockMeshDict", "dictionary", "blockMeshDict", f"""
convertToMeters 1;
vertices ( ({x0} {y0} {z0}) ({x1} {y0} {z0}) ({x1} {y1} {z0}) ({x0} {y1} {z0})
           ({x0} {y0} {z1}) ({x1} {y0} {z1}) ({x1} {y1} {z1}) ({x0} {y1} {z1}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
boundary ( {patches} );
""")

geom = "\n".join(f"    {s}.stl {{ type triSurfaceMesh; name {s}; }}" for s in surfaces)
geom += "\n" + "\n".join(f"    {n} {{ type box; min ({a[0]} {a[1]} {a[2]}); max ({b[0]} {b[1]} {b[2]}); }}" for n, a, b, _ in boxes)
RM = 0.155 / 2; MX = RM / math.sqrt(2); ZP = 0.036; RP = 0.0889 / 2
disks = [("dFL", MX, MX), ("dRL", -MX, MX), ("dRR", -MX, -MX), ("dFR", MX, -MX)]
if mode == "hover":
    geom += "\n" + "\n".join(f"    {n}r {{ type searchableCylinder; point1 ({x} {y} {ZP - 0.004}); point2 ({x} {y} {ZP + 0.004}); radius {RP + 0.004}; }}"
                             for n, x, y in disks)
feat = "\n".join(f'        {{ file "{s}.eMesh"; level 5; }}' for s in surfaces)
lev = {s: "(4 5)" for s in surfaces}
lev["battery"] = "(3 4)"
rsurf = "\n".join(f"        {s} {{ level {lev[s]}; patchInfo {{ type wall; }} }}" for s in surfaces)
rreg = "\n".join(f"        {n} {{ mode inside; levels ((1e15 {l})); }}" for n, _, _, l in boxes)
if mode == "hover":
    rreg += "\n" + "\n".join(f"        {n}r {{ mode inside; levels ((1e15 4)); }}" for n, _, _ in disks)
w("system/snappyHexMeshDict", "dictionary", "snappyHexMeshDict", f"""
castellatedMesh true; snap true; addLayers false;
geometry
{{
{geom}
}}
castellatedMeshControls
{{
    maxLocalCells 1500000; maxGlobalCells 4000000; minRefinementCells 10; maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features
    (
{feat}
    );
    refinementSurfaces
    {{
{rsurf}
    }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
{rreg}
    }}
    locationInMesh ({loc[0]} {loc[1]} {loc[2]});
    allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 50; nRelaxIter 5; nFeatureSnapIter 10;
               implicitFeatureSnap false; explicitFeatureSnap true; multiRegionFeatureSnap false; }}
addLayersControls {{ relativeSizes true; layers {{ }} expansionRatio 1.2; finalLayerThickness 0.5; minThickness 0.1;
    nGrow 0; featureAngle 60; nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10;
    maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 50; }}
meshQualityControls {{ #includeEtc "caseDicts/meshQualityDict" nSmoothScale 4; errorReduction 0.75; minFaceWeight 0.02; }}
mergeTolerance 1e-6;
""")
w("system/surfaceFeatureExtractDict", "dictionary", "surfaceFeatureExtractDict", "\n".join(
    f"{s}.stl {{ extractionMethod extractFromSurface; includedAngle 150; subsetFeatures {{ nonManifoldEdges no; openEdges yes; }} writeObj no; }}"
    for s in surfaces))
w("system/decomposeParDict", "dictionary", "decomposeParDict", "numberOfSubdomains 2;\nmethod scotch;\n")
w("system/meshQualityDict", "dictionary", "meshQualityDict", '#includeEtc "caseDicts/meshQualityDict"\nminFaceWeight 0.02;\n')

# ---------------- physics
w("constant/transportProperties", "dictionary", "transportProperties", "transportModel Newtonian;\nnu 1.5e-05;\n")
w("constant/turbulenceProperties", "dictionary", "turbulenceProperties", "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n")
k0 = 1.5 * (U0 * 0.01) ** 2 if mode == "cruise" else 1e-4
om0 = math.sqrt(k0) / (0.09 ** 0.25 * 0.01) if mode == "cruise" else 10.0
walls = "|".join(surfaces)
def field(name, cls, dim, internal, bc):
    w(f"0/{name}", cls, name, f"dimensions {dim};\ninternalField uniform {internal};\nboundaryField\n{{\n{bc}\n}}\n")
if mode == "cruise":
    field("U", "volVectorField", "[0 1 -1 0 0 0 0]", f"(-{U0} 0 0)", f"""
    inlet {{ type fixedValue; value uniform (-{U0} 0 0); }}
    outlet {{ type inletOutlet; inletValue uniform (0 0 0); value uniform (-{U0} 0 0); }}
    sides {{ type slip; }}
    "({walls})" {{ type noSlip; }}""")
    field("p", "volScalarField", "[0 2 -2 0 0 0 0]", "0", f"""
    inlet {{ type zeroGradient; }}  outlet {{ type fixedValue; value uniform 0; }}
    sides {{ type slip; }}  "({walls})" {{ type zeroGradient; }}""")
    for nm, v, wf in (("k", k0, "kqRWallFunction"), ("omega", om0, "omegaWallFunction")):
        field(nm, "volScalarField", "[0 2 -2 0 0 0 0]" if nm == "k" else "[0 0 -1 0 0 0 0]", v, f"""
    inlet {{ type fixedValue; value uniform {v}; }}
    outlet {{ type inletOutlet; inletValue uniform {v}; value uniform {v}; }}
    sides {{ type slip; }}  "({walls})" {{ type {wf}; value uniform {v}; }}""")
    field("nut", "volScalarField", "[0 2 -1 0 0 0 0]", "0", f"""
    inlet {{ type calculated; value uniform 0; }} outlet {{ type calculated; value uniform 0; }}
    sides {{ type slip; }} "({walls})" {{ type nutkWallFunction; value uniform 0; }}""")
else:
    field("U", "volVectorField", "[0 1 -1 0 0 0 0]", "(0 0 0)", f"""
    open {{ type pressureInletOutletVelocity; value uniform (0 0 0); }}
    "({walls})" {{ type noSlip; }}""")
    field("p", "volScalarField", "[0 2 -2 0 0 0 0]", "0", f"""
    open {{ type totalPressure; p0 uniform 0; value uniform 0; }}
    "({walls})" {{ type zeroGradient; }}""")
    for nm, v, wf in (("k", k0, "kqRWallFunction"), ("omega", om0, "omegaWallFunction")):
        field(nm, "volScalarField", "[0 2 -2 0 0 0 0]" if nm == "k" else "[0 0 -1 0 0 0 0]", v, f"""
    open {{ type inletOutlet; inletValue uniform {v}; value uniform {v}; }}
    "({walls})" {{ type {wf}; value uniform {v}; }}""")
    field("nut", "volScalarField", "[0 2 -1 0 0 0 0]", "0", f"""
    open {{ type calculated; value uniform 0; }}
    "({walls})" {{ type nutkWallFunction; value uniform 0; }}""")
    # actuator disks: annulus cellZones + momentum sources (uniform loading, no swirl)
    T = float(os.environ.get("HOVER_THRUST_N", "0.80"))
    ts = "\n".join(f"""    {{ name {n}; type cellSet; action new; source cylinderAnnulusToCell;
      p1 ({x} {y} {ZP - 0.0025}); p2 ({x} {y} {ZP + 0.0025}); outerRadius {RP}; innerRadius 0.008; }}
    {{ name {n}; type cellZoneSet; action new; source setToCellZone; set {n}; }}""" for n, x, y in disks)
    w("system/topoSetDict", "dictionary", "topoSetDict", f"actions\n(\n{ts}\n);\n")
    src = "\n".join(f"""{n} {{ type vectorSemiImplicitSource; selectionMode cellZone; cellZone {n}; volumeMode absolute;
       injectionRateSuSp {{ U ((0 0 {-T / 1.2:.6f}) 0); }} }}""" for n, _, _ in disks)
    w("constant/fvOptions", "dictionary", "fvOptions", src + "\n")

# ---------------- numerics
w("system/fvSchemes", "dictionary", "fvSchemes", """
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; grad(U) cellLimited Gauss linear 1; grad(k) cellLimited Gauss linear 1; grad(omega) cellLimited Gauss linear 1; }
divSchemes { default none; div(phi,U) bounded Gauss linearUpwindV grad(U); div(phi,k) bounded Gauss upwind;
             div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; div(div(phi,U)) Gauss linear; }
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.5; }
wallDist { method meshWave; }
""")
w("system/fvSolution", "dictionary", "fvSolution", """
solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
    Phi { $p; }
    "(U|k|omega)" { solver smoothSolver; smoother GaussSeidel; tolerance 1e-8; relTol 0.1; nSweeps 1; }
}
SIMPLE { nNonOrthogonalCorrectors 1; consistent yes; residualControl { p 1e-5; U 1e-6; } }
potentialFlow { nNonOrthogonalCorrectors 10; }
relaxationFactors { equations { U 0.7; k 0.5; omega 0.5; } fields { p 1.0; } }
""")
NIT = int(os.environ.get("NITER", "800" if mode == "cruise" else "1000"))
forces = "\n".join(f"""    f_{s} {{ type forces; libs (forces); writeControl timeStep; writeInterval 1; patches ({s}); rho rhoInf; rhoInf 1.2; CofR (0 0 0.03); log false; }}"""
                   for s in surfaces)
w("system/controlDict", "dictionary", "controlDict", f"""
application simpleFoam; startFrom latestTime; startTime 0; stopAt endTime; endTime {NIT}; deltaT 1;
writeControl timeStep; writeInterval {NIT}; purgeWrite 1; writeFormat binary; writePrecision 8;
writeCompression off; timeFormat general; timePrecision 6; runTimeModifiable true;
functions
{{
{forces}
}}
""")
open(os.path.join(C, "Allrun"), "w").write(f"""#!/bin/bash
set -e
cd {C}
source /home/claude/cfd/ofenv.sh
surfaceFeatureExtract > log.feat 2>&1
blockMesh > log.blockMesh 2>&1
decomposePar -force > log.decompose0 2>&1
mpirun -np 2 snappyHexMesh -parallel -overwrite > log.snappy 2>&1
reconstructParMesh -constant > log.reconMesh 2>&1
rm -rf processor*
{"topoSet > log.topoSet 2>&1" if mode == "hover" else ""}
checkMesh -constant > log.checkMesh 2>&1 || true
decomposePar -force > log.decompose 2>&1
mpirun -np 2 potentialFoam -parallel -writep > log.potential 2>&1 || true
mpirun -np 2 simpleFoam -parallel > log.simpleFoam 2>&1
reconstructPar -latestTime > log.reconstruct 2>&1
echo DONE
""")
os.chmod(os.path.join(C, "Allrun"), 0o755)
if mode == "cruise" and pitch != 0:
    # rotate the surfaces: nose-down pitch about y through (0,0,0.03)
    with open(os.path.join(C, "rotate.sh"), "w") as f:
        f.write("source /home/claude/cfd/ofenv.sh\ncd %s/constant/triSurface\n" % C)
        for s in surfaces:
            f.write(f"surfaceTransformPoints -centre '(0 0 0.03)' -rotate-y {pitch} {s}.stl {s}.stl > /dev/null\n")
    os.system(f"bash {C}/rotate.sh")
print(case, "cells(background)=", nx * ny * nz)
