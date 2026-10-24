"""Blender (bpy) build animation for the AeroFrame speedrun.

Reads out_rec/steps/steps.json (+ per-step STLs written by build_frame.py with RECORD set) and the
reference parts, builds a timeline and renders frames with the Workbench engine.
New material grows in orange, removed material shrinks away in red, sketches draw first,
then the fit check (parts drop in) and an exploded view. Writes timing.json for the HUD.
usage: python build_anim.py [--render] [--start N --end M]
"""
import bpy, json, math, os, sys
from mathutils import Vector, Matrix

ROOT = "/home/claude/frame"
REC = f"{ROOT}/out_rec/steps"
REF = f"{ROOT}/out/parts"
OUT = f"{ROOT}/speedrun"
FR = f"{OUT}/frames"; os.makedirs(FR, exist_ok=True)
FPS = 24; W, H = 1280, 720
args = sys.argv
RENDER = "--render" in args
S0 = int(args[args.index("--start") + 1]) if "--start" in args else None
S1 = int(args[args.index("--end") + 1]) if "--end" in args else None

steps = json.load(open(f"{REC}/steps.json"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.fps = FPS
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL"
sh.show_cavity = True; sh.cavity_type = "BOTH"; sh.cavity_ridge_factor = 1.0; sh.cavity_valley_factor = 1.0
sh.show_shadows = True; sh.shadow_intensity = 0.35; sh.show_specular_highlight = True
sh.show_object_outline = True; sh.object_outline_color = (0.15, 0.12, 0.10)
sc.display.light_direction = (0.35, -0.45, 0.82)
sc.render.film_transparent = False
w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.96, 0.97, 0.98)
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = float(os.environ.get("EXPOSURE", "0.9"))

COL = dict(chassis=(1.0, 0.50, 0.16, 1), lid=(1.0, 0.70, 0.42, 1), hood=(0.42, 0.66, 1.0, 1),
           add=(1.0, 0.86, 0.10, 1), rem=(0.95, 0.10, 0.16, 1), sketch=(0.05, 0.30, 0.85, 1),
           motor=(0.12, 0.12, 0.14, 1), prop=(0.55, 0.72, 0.95, 1), battery=(0.18, 0.40, 0.80, 1),
           cam=(0.05, 0.05, 0.05, 1), board=(0.10, 0.45, 0.20, 1), gps=(0.25, 0.25, 0.28, 1), floor=(1.0, 1.0, 1.0, 1))
MATS = {}
def mat(k):
    if k not in MATS:
        m = bpy.data.materials.new(k); m.diffuse_color = COL[k]; m.roughness = 0.45; m.metallic = 0.0; MATS[k] = m
    return MATS[k]

def imp(path, k, name):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path, global_scale=0.001)
    o = [x for x in bpy.data.objects if x not in before][0]
    o.name = name; o.data.materials.clear(); o.data.materials.append(mat(k))
    # bake the importer's mm->m object scale into the mesh, so scale animations start from 1
    sx = o.scale[0]; o.data.transform(Matrix.Scale(sx, 4)); o.scale = (1, 1, 1)
    for p in o.data.polygons:
        p.use_smooth = False
    return o

def vis(o, f, on):
    o.hide_render = not on; o.hide_viewport = not on
    o.keyframe_insert("hide_render", frame=f); o.keyframe_insert("hide_viewport", frame=f)

def origin_to(o, pt):
    """move object origin to pt (world) without moving the mesh"""
    d = Vector(pt) - o.location
    o.data.transform(Matrix.Translation(-d)); o.location = Vector(pt)

def bbox_center(o, mode="center"):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = Vector([min(v[i] for v in vs) for i in range(3)]); hi = Vector([max(v[i] for v in vs) for i in range(3)])
    c = (lo + hi) / 2
    if mode == "bottom":
        c.z = lo.z
    return c

def scale_anim(o, f0, f1, s0, s1):
    o.scale = (s0,) * 3; o.keyframe_insert("scale", frame=f0)
    o.scale = (s1,) * 3; o.keyframe_insert("scale", frame=f1)

def hidden_from(o, f_end=None):
    vis(o, 0, False)

# floor
bpy.ops.mesh.primitive_plane_add(size=3, location=(0.02, 0, -0.012))
bpy.context.active_object.data.materials.append(mat("floor"))

# --------------------------------------------------------------- timeline
t = 18                    # short lead-in
T = dict(starts=[], titles=[s["title"] for s in steps], details=[s["detail"] for s in steps])
current = {}              # part name -> object currently shown
DUR = 64
for s in steps:
    i = s["i"]; f0 = t; T["starts"].append(f0)
    d = f"{REC}/{i:02d}"
    fs = f0                                   # sketch phase
    if s["sketch"]:
        for j, poly in enumerate(s["sketch"]):
            cu = bpy.data.curves.new(f"sk{i}_{j}", "CURVE"); cu.dimensions = "3D"
            cu.bevel_depth = 0.00045; cu.bevel_resolution = 1
            sp = cu.splines.new("POLY"); sp.points.add(len(poly) - 1)
            for k, p in enumerate(poly):
                sp.points[k].co = (p[0] * 0.001, p[1] * 0.001, p[2] * 0.001, 1)
            ob = bpy.data.objects.new(f"sk{i}_{j}", cu); sc.collection.objects.link(ob); ob.data.materials.append(mat("sketch"))
            vis(ob, 0, False); vis(ob, f0, True); vis(ob, f0 + 46, False)
            cu.bevel_factor_end = 0.0; cu.keyframe_insert("bevel_factor_end", frame=f0 + min(j, 8))
            cu.bevel_factor_end = 1.0; cu.keyframe_insert("bevel_factor_end", frame=f0 + 14 + min(j, 8))
        fs = f0 + 14
    fa, fb = fs + 2, fs + 26                   # add grows fa..fb ; swap at fb ; rem shrinks fb..fb+22
    for name, e in s["parts"].items():
        k = name
        cur = imp(f"{d}/{name}.stl", k, f"{name}_{i}")
        vis(cur, 0, False); vis(cur, fb, True)
        prev = current.get(name)
        if prev is not None:
            vis(prev, fb, False)
        if e["add"] and os.path.exists(f"{d}/{name}_add.stl"):
            a = imp(f"{d}/{name}_add.stl", "add", f"{name}_add_{i}")
            origin_to(a, bbox_center(a, "bottom" if i > 0 else "center"))
            vis(a, 0, False); vis(a, fa, True); vis(a, fb + 8, False)
            scale_anim(a, fa, fb - 4, 0.02, 1.003)
            if prev is None:
                pass
        if e["rem"] and os.path.exists(f"{d}/{name}_rem.stl"):
            r = imp(f"{d}/{name}_rem.stl", "rem", f"{name}_rem_{i}")
            origin_to(r, bbox_center(r))
            vis(r, 0, False); vis(r, fb, True); vis(r, fb + 24, False)
            scale_anim(r, fb + 2, fb + 22, 1.0, 0.02)
        current[name] = cur
    t = fb + 30
T["build_end"] = t

# --------------------------------------------------------------- fit check: parts drop in
fit0 = t + 4
refs = [("ref_Motor%d" % i, "motor") for i in range(4)] + [("ref_Camera", "cam"), ("ref_Board0", "board"), ("ref_Board1", "board"),
        ("ref_Board2", "board"), ("ref_GPS", "gps"), ("ref_Battery_4S1P_18650", "battery")]
drop = []
for j, (n, k) in enumerate(refs):
    o = imp(f"{REF}/{n}.stl", k, n); vis(o, 0, False)
    f = fit0 + 3 * j; vis(o, f, True)
    z0 = o.location.z
    o.location.z = z0 + 0.09; o.keyframe_insert("location", frame=f)
    o.location.z = z0; o.keyframe_insert("location", frame=f + 12)
    drop.append(o)
# props as rings (keeps the frame visible)
props = []
for i in range(4):
    a = math.radians(45 + 90 * i); c = (0.0775 * math.cos(a), 0.0775 * math.sin(a), 0.0364)
    bpy.ops.mesh.primitive_torus_add(location=c, major_radius=0.04445, minor_radius=0.0006, major_segments=96, minor_segments=8)
    ring = bpy.context.active_object; ring.data.materials.append(mat("prop")); vis(ring, 0, False); vis(ring, fit0 + 36, True)
    scale_anim(ring, fit0 + 36, fit0 + 48, 0.05, 1.0)
    props.append(ring)
T["fit"] = fit0
t = fit0 + 70

# --------------------------------------------------------------- exploded view
ex0 = t
EX = {"chassis": -0.012, "lid": 0.030, "hood": 0.055, "ref_Battery_4S1P_18650": 0.10, "ref_GPS": 0.018,
      "ref_Board0": 0.0, "ref_Board1": 0.008, "ref_Board2": 0.0, "ref_Camera": 0.0}
final = {n: o for n, o in current.items()}
movers = list(final.items()) + [(o.name, o) for o in drop]
for n, o in movers:
    dz = EX.get(n, EX.get(n.split("_")[0], 0.012 if n.startswith("ref_Motor") else 0.0))
    o.keyframe_insert("location", frame=ex0)
    o.location.z += dz; o.keyframe_insert("location", frame=ex0 + 30)
    o.keyframe_insert("location", frame=ex0 + 70)
    o.location.z -= dz; o.keyframe_insert("location", frame=ex0 + 96)
for r in props:
    r.keyframe_insert("location", frame=ex0); r.location.z += 0.03; r.keyframe_insert("location", frame=ex0 + 30)
    r.keyframe_insert("location", frame=ex0 + 70); r.location.z -= 0.03; r.keyframe_insert("location", frame=ex0 + 96)
T["explode"] = ex0
T["end"] = ex0 + 96
T["last"] = ex0 + 96 + 60

# --------------------------------------------------------------- camera: slow orbit, closer at the start
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 40; cam.data.clip_start = 0.005
tgt = bpy.data.objects.new("tgt", None); sc.collection.objects.link(tgt); tgt.location = (0.022, 0, 0.012)
con = cam.constraints.new("TRACK_TO"); con.target = tgt; con.track_axis = "TRACK_NEGATIVE_Z"; con.up_axis = "UP_Y"
N = T["last"]
for f in range(0, N + 1, 6):
    u = f / N
    az = math.radians(35 + 330 * u)
    el = math.radians(30 - 6 * math.sin(math.pi * u))
    r = 0.27 + 0.07 * min(1, f / max(T["build_end"], 1)) if f < T["explode"] else 0.34 + 0.05 * min(1, (f - T["explode"]) / 40)
    cam.location = (0.022 + r * math.cos(el) * math.cos(az), r * math.cos(el) * math.sin(az), 0.012 + r * math.sin(el))
    cam.keyframe_insert("location", frame=f)
sc.frame_start, sc.frame_end = 0, N
json.dump(T, open(f"{OUT}/timing.json", "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/frame_speedrun.blend")
print("TIMELINE", N, "frames", T["starts"], "fit", T["fit"], "explode", T["explode"])
if RENDER:
    a = S0 if S0 is not None else 0; b = S1 if S1 is not None else N
    for f in range(a, b + 1):
        sc.frame_set(f)
        sc.render.filepath = f"{FR}/f_{f:04d}.png"
        bpy.ops.render.render(write_still=True)
    print("RENDERED", a, b)
