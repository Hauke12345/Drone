"""AeroFrame v3 speedrun with FEM and CFD segments (Blender 5, Workbench).

Build steps (from out_rec) -> FEM after the arms (stress maps + deformation + vibration mode)
-> remaining steps -> fit check -> CFD cruise (tilt 20 deg, streamlines, beads) -> CFD hover
(actuator-disk rings, downwash) -> exploded view.  Writes frame_speedrun2.blend + timing2.json.
FEM/CFD frames need shading.color_type = 'VERTEX' (set per frame by render_frames2.py).
"""
import bpy, json, math, os
import numpy as np
from mathutils import Vector, Matrix

ROOT = "/home/claude/frame"; REC = f"{ROOT}/out_rec/steps"; REF = f"{ROOT}/out/parts"; OUT = f"{ROOT}/speedrun"
FPS = 24; W, H = 1280, 720
steps = json.load(open(f"{REC}/steps.json"))
VIS = np.load(f"{OUT}/vis.npz"); META = json.load(open(f"{OUT}/vis.json"))
FACT = json.load(open(f"{OUT}/fem_facts.json"))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"; sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.fps = FPS
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL"
sh.show_cavity = True; sh.cavity_type = "BOTH"; sh.cavity_ridge_factor = 1.0; sh.cavity_valley_factor = 1.0
sh.show_shadows = True; sh.shadow_intensity = 0.35; sh.show_specular_highlight = True
sh.show_object_outline = True; sh.object_outline_color = (0.15, 0.12, 0.10)
sc.display.light_direction = (0.35, -0.45, 0.82)
w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.36, 0.37, 0.39)
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0.9

COL = dict(chassis=(1.0, 0.50, 0.16, 1), lid=(1.0, 0.70, 0.42, 1), hood=(0.42, 0.66, 1.0, 1),
           add=(1.0, 0.86, 0.10, 1), rem=(0.95, 0.10, 0.16, 1), sketch=(0.05, 0.30, 0.85, 1),
           motor=(0.12, 0.12, 0.14, 1), prop=(0.30, 0.45, 0.75, 1), battery=(0.18, 0.40, 0.80, 1),
           cam=(0.05, 0.05, 0.05, 1), board=(0.10, 0.45, 0.20, 1), gps=(0.25, 0.25, 0.28, 1),
           floor=(1.0, 1.0, 1.0, 1), bead=(1.0, 1.0, 1.0, 1), floorv=(0.36, 0.37, 0.39, 1), fem=(1, 1, 1, 1))
MATS = {}
def mat(k):
    if k not in MATS:
        m = bpy.data.materials.new(k); m.diffuse_color = COL[k]; m.roughness = 0.45; MATS[k] = m
    return MATS[k]

def paint(o, rgb=None, per_vertex=None):
    """colour attribute for VERTEX shading (uniform or per vertex)."""
    me = o.data
    a = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    n = len(me.vertices)
    if per_vertex is not None:
        c = np.concatenate([per_vertex, np.ones((n, 1), np.float32)], 1)
    else:
        c = np.tile(np.array(list(rgb[:3]) + [1.0], np.float32), (n, 1))
    a.data.foreach_set("color", c.ravel())
    me.color_attributes.active_color = a

def imp(path, k, name):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path, global_scale=0.001)
    o = [x for x in bpy.data.objects if x not in before][0]
    o.name = name; o.data.materials.clear(); o.data.materials.append(mat(k))
    sx = o.scale[0]; o.data.transform(Matrix.Scale(sx, 4)); o.scale = (1, 1, 1)
    paint(o, COL[k])
    return o

def mesh_obj(name, V, F, colors, k="fem"):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V)); me.vertices.foreach_set("co", V.ravel())
    nf, ns = F.shape
    me.loops.add(nf * ns); me.loops.foreach_set("vertex_index", F.ravel())
    me.polygons.add(nf); me.polygons.foreach_set("loop_start", np.arange(0, nf * ns, ns)); me.polygons.foreach_set("loop_total", np.full(nf, ns))
    me.update(); me.validate(clean_customdata=False)
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); me.materials.append(mat(k))
    paint(o, per_vertex=colors)
    return o

def vis(o, f, on):
    o.hide_render = not on; o.hide_viewport = not on
    o.keyframe_insert("hide_render", frame=f); o.keyframe_insert("hide_viewport", frame=f)

def origin_to(o, pt):
    d = Vector(pt) - o.location; o.data.transform(Matrix.Translation(-d)); o.location = Vector(pt)

def bbox_center(o, mode="center"):
    vs = np.array([v.co[:] for v in o.data.vertices]) + np.array(o.location[:])
    lo, hi = vs.min(0), vs.max(0); c = (lo + hi) / 2
    if mode == "bottom":
        c[2] = lo[2]
    return Vector(c)

def scale_anim(o, f0, f1, s0, s1):
    o.scale = (s0,) * 3; o.keyframe_insert("scale", frame=f0); o.scale = (s1,) * 3; o.keyframe_insert("scale", frame=f1)

bpy.ops.mesh.primitive_plane_add(size=3, location=(0.02, 0, -0.012))
floor = bpy.context.active_object; floor.data.materials.append(mat("floor")); paint(floor, COL["floorv"])

SEG = []          # timeline segments for the HUD
SUB = []          # caption sub-phases
VTX = []          # frame ranges rendered with vertex colours
CAMK = []         # camera keys (frame, az, el, r, target)

def build_step(s, t, current):
    i = s["i"]; d = f"{REC}/{i:02d}"; f0 = t; fs = f0
    if s["sketch"]:
        for j, poly in enumerate(s["sketch"]):
            cu = bpy.data.curves.new(f"sk{i}_{j}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.00045; cu.bevel_resolution = 1
            sp = cu.splines.new("POLY"); sp.points.add(len(poly) - 1)
            for k, p in enumerate(poly):
                sp.points[k].co = (p[0] * 0.001, p[1] * 0.001, p[2] * 0.001, 1)
            ob = bpy.data.objects.new(f"sk{i}_{j}", cu); sc.collection.objects.link(ob); ob.data.materials.append(mat("sketch"))
            vis(ob, 0, False); vis(ob, f0, True); vis(ob, f0 + 30, False)
            cu.bevel_factor_end = 0.0; cu.keyframe_insert("bevel_factor_end", frame=f0 + min(j, 6))
            cu.bevel_factor_end = 1.0; cu.keyframe_insert("bevel_factor_end", frame=f0 + 9 + min(j, 6))
        fs = f0 + 12
    fa, fb = fs + 1, fs + 15
    for name, e in s["parts"].items():
        cur = imp(f"{d}/{name}.stl", name, f"{name}_{i}")
        vis(cur, 0, False); vis(cur, fb, True)
        prev = current.get(name)
        if prev is not None:
            vis(prev, fb, False)
        if e["add"] and os.path.exists(f"{d}/{name}_add.stl"):
            a = imp(f"{d}/{name}_add.stl", "add", f"{name}_add_{i}")
            origin_to(a, bbox_center(a, "bottom" if i > 0 else "center"))
            vis(a, 0, False); vis(a, fa, True); vis(a, fb + 6, False); scale_anim(a, fa, fb - 3, 0.02, 1.003)
        if e["rem"] and os.path.exists(f"{d}/{name}_rem.stl"):
            r = imp(f"{d}/{name}_rem.stl", "rem", f"{name}_rem_{i}")
            origin_to(r, bbox_center(r))
            vis(r, 0, False); vis(r, fb, True); vis(r, fb + 15, False); scale_anim(r, fb + 1, fb + 14, 1.0, 0.02)
        current[name] = cur
    end = fb + 18
    SEG.append(dict(kind="build", title=s["title"], detail=s["detail"], start=f0, end=end))
    return end

# ======================================================== timeline
t = 12; current = {}
CAMK.append((0, 35, 30, 0.27, (0.022, 0, 0.012)))
for s in steps:
    t = build_step(s, t, current)
    if s["i"] == 1:
        # ---------------------------------------------- FEM segment
        f0 = t; arm_obj = current["chassis"]
        vis(arm_obj, f0, False)
        V = VIS["fem_v"]; F = VIS["fem_f"]
        phases = [("lc2", 44, "Landing on one arm: 30 N", f"peak {FACT['lc2_peak']:.0f} MPa at the arm root · motor moves {FACT['lc2_tip']:.2f} mm", "stress"),
                  ("lc3", 44, "Side hit on a motor: 20 N", f"peak {FACT['lc3_peak']:.0f} MPa · motor moves {FACT['lc3_tip']:.2f} mm", "stress"),
                  ("mode", 44, f"First vibration mode: {FACT['f_mode']:.0f} Hz", "arms swing in-plane (free-free, with battery and electronics)", "mode")]
        fp = f0
        for tag, dur, cap, det, cb in phases:
            o = mesh_obj(f"fem_{tag}", V, F, VIS[f"fem_c_{tag}"])
            o.shape_key_add(name="Basis"); kk = o.shape_key_add(name="def")
            kk.data.foreach_set("co", VIS[f"fem_d_{tag}"].ravel()); kk.slider_min = -1.0
            vis(o, 0, False); vis(o, fp, True); vis(o, fp + dur, False)
            if tag == "mode":
                for j in range(dur + 1):
                    kk.value = 0.95 * math.sin(2 * math.pi * j / 14.0) * min(1, j / 6); kk.keyframe_insert("value", frame=fp + j)
            else:
                for fr_, v in ((fp, 0.0), (fp + 4, 0.0), (fp + 16, 1.0), (fp + 32, 1.0), (fp + 42, 0.0)):
                    kk.value = v; kk.keyframe_insert("value", frame=fr_)
            SUB.append(dict(start=fp, end=fp + dur, label="FEM · CalculiX · finished v3 frame", caption=cap, detail=det, colorbar=cb))
            fp += dur
        vis(arm_obj, fp, True)
        VTX.append((f0, fp - 1))
        SEG.append(dict(kind="fem", title="FEM: arm loads + modes", detail="", start=f0, end=fp))
        CAMK += [(f0 - 6, None, None, None, None), (f0 + 8, -12, 40, 0.25, (0.035, 0.025, 0.010)),
                 (fp - 8, 10, 36, 0.25, (0.035, 0.025, 0.010)), (fp + 10, None, None, None, None)]
        t = fp
build_end = t

# ---------------------------------------------- fit check
fit0 = t + 2
refs = [("ref_Motor%d" % i, "motor") for i in range(4)] + [("ref_Camera", "cam"), ("ref_Board0", "board"), ("ref_Board1", "board"),
        ("ref_Board2", "board"), ("ref_GPS", "gps"), ("ref_Battery_4S1P_18650", "battery")]
drop = []
for j, (n, k) in enumerate(refs):
    o = imp(f"{REF}/{n}.stl", k, n); vis(o, 0, False)
    f = fit0 + 3 * j; vis(o, f, True); z0 = o.location.z
    o.location.z = z0 + 0.09; o.keyframe_insert("location", frame=f); o.location.z = z0; o.keyframe_insert("location", frame=f + 10)
    drop.append(o)
t = fit0 + 46
SEG.append(dict(kind="fit", title="Fit check", detail="", start=fit0, end=t))

# ---------------------------------------------- pivot for the cruise tilt
piv = bpy.data.objects.new("pivot", None); sc.collection.objects.link(piv); piv.location = (0, 0, 0.03)
bpy.context.view_layer.update()
movers = list(current.values()) + drop
for o in movers:
    o.parent = piv; o.matrix_parent_inverse = piv.matrix_world.inverted()

# ---------------------------------------------- CFD cruise
c0 = t
vis(floor, c0, False)
piv.rotation_euler = (0, 0, 0); piv.keyframe_insert("rotation_euler", frame=c0)
piv.rotation_euler = (0, math.radians(20), 0); piv.keyframe_insert("rotation_euler", frame=c0 + 14)
g0 = c0 + 14
stream_objs = []
for k in range(META["cruise_nchunk"]):
    o = mesh_obj(f"cr_{k}", VIS[f"cruise_v{k}"], VIS[f"cruise_f{k}"], VIS[f"cruise_c{k}"])
    vis(o, 0, False); vis(o, g0 + 3 * k, True); stream_objs.append(o)
nb = META["cruise_bead_frames"]; b0 = g0 + 26
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.0016); bead_mesh = bpy.context.active_object.data
bpy.data.objects.remove(bpy.context.active_object); bead_mesh.materials.append(mat("bead"))
def beads(tag, start, nfr):
    tr = VIS[f"{tag}_beads"]; objs = []
    for bi in range(len(tr)):
        o = bpy.data.objects.new(f"{tag}_b{bi}", bead_mesh); sc.collection.objects.link(o)
        vis(o, 0, False); vis(o, start, True); vis(o, start + nfr, False)
        for j, p in enumerate(tr[bi]):
            o.location = p.tolist(); o.keyframe_insert("location", frame=start + 2 * j)
        objs.append(o)
    return objs
paint_done = False
cb = beads("cruise", b0, nb)
cruise_end = b0 + nb
for o in stream_objs:
    vis(o, cruise_end, False)
piv.keyframe_insert("rotation_euler", frame=cruise_end)
piv.rotation_euler = (0, 0, 0); piv.keyframe_insert("rotation_euler", frame=cruise_end + 10)
SUB.append(dict(start=c0, end=cruise_end + 4, label="CFD · OpenFOAM · k-ω SST",
                caption="Cruise 15 m/s, 20° nose-down", detail="airframe drag 0.55 N without props · v2: 0.57 N", colorbar="speed"))

# ---------------------------------------------- CFD hover
h0 = cruise_end + 10
props = []
for i in range(4):
    a = math.radians(45 + 90 * i); c = (0.0775 * math.cos(a), 0.0775 * math.sin(a), 0.0364)
    bpy.ops.mesh.primitive_torus_add(location=c, major_radius=0.04445, minor_radius=0.0007, major_segments=96, minor_segments=8)
    ring = bpy.context.active_object; ring.data.materials.append(mat("prop")); paint(ring, COL["prop"])
    vis(ring, 0, False); vis(ring, h0, True); scale_anim(ring, h0, h0 + 8, 0.05, 1.0); props.append(ring)
hs = []
for k in range(META["hover_nchunk"]):
    o = mesh_obj(f"hv_{k}", VIS[f"hover_v{k}"], VIS[f"hover_f{k}"], VIS[f"hover_c{k}"])
    vis(o, 0, False); vis(o, h0 + 8 + 2 * k, True); hs.append(o)
hb0 = h0 + 26; hn = META["hover_bead_frames"]
beads("hover", hb0, hn)
hover_end = hb0 + hn
for o in hs:
    vis(o, hover_end, False)
vis(floor, hover_end, True)
SUB.append(dict(start=h0, end=hover_end, label="CFD · OpenFOAM · actuator disks",
                caption="Hover: 4 × 0.8 N through the props", detail="4.0 % of thrust lost to the airframe · flat carbon arms: 12 %", colorbar="speed"))
VTX.append((c0, hover_end - 1))
SEG.append(dict(kind="cfd", title="CFD: cruise + hover", detail="", start=c0, end=hover_end))

# ---------------------------------------------- exploded view
ex0 = hover_end + 2
EX = {"chassis": -0.012, "lid": 0.030, "hood": 0.055, "ref_Battery_4S1P_18650": 0.10, "ref_GPS": 0.018, "ref_Board1": 0.008}
for o in movers:
    key = o.name.split("_")[0] if o.name.split("_")[0] in ("chassis", "lid", "hood") else o.name
    dz = EX.get(key, 0.012 if o.name.startswith("ref_Motor") else 0.0)
    o.keyframe_insert("location", frame=ex0); o.location.z += dz; o.keyframe_insert("location", frame=ex0 + 20)
    o.keyframe_insert("location", frame=ex0 + 38); o.location.z -= dz; o.keyframe_insert("location", frame=ex0 + 58)
for r in props:
    r.keyframe_insert("location", frame=ex0); r.location.z += 0.03; r.keyframe_insert("location", frame=ex0 + 20)
    r.keyframe_insert("location", frame=ex0 + 38); r.location.z -= 0.03; r.keyframe_insert("location", frame=ex0 + 58)
STOP = ex0 + 58
SEG.append(dict(kind="explode", title="Exploded view", detail="", start=ex0, end=STOP))
LAST = STOP + 40

# ---------------------------------------------- camera
CAMK += [(build_end - 4, 215, 30, 0.33, (0.022, 0, 0.012)),
         (c0 + 6, 266, 10, 0.52, (-0.06, 0, 0.02)), (cruise_end, 274, 13, 0.52, (-0.06, 0, 0.02)),
         (h0 + 4, 300, 12, 0.60, (0.0, 0, -0.07)), (hover_end, 318, 14, 0.60, (0.0, 0, -0.07)),
         (ex0 + 10, 380, 28, 0.36, (0.022, 0, 0.012)), (LAST, 400, 26, 0.37, (0.022, 0, 0.012))]
# fill None keys (resume orbit) by linear interpolation of neighbours
CAMK.sort(key=lambda k: k[0])
def interp_keys(keys, f):
    known = [k for k in keys if k[1] is not None]
    for a, b in zip(known, known[1:]):
        if a[0] <= f <= b[0]:
            u = (f - a[0]) / max(b[0] - a[0], 1); u = u * u * (3 - 2 * u)
            lerp = lambda x, y: x + (y - x) * u
            return (lerp(a[1], b[1]), lerp(a[2], b[2]), lerp(a[3], b[3]), tuple(lerp(a[4][i], b[4][i]) for i in range(3)))
    k = known[-1] if f > known[-1][0] else known[0]
    return k[1:]
# resolve the 'None' resume keys: use the orbit through the build (35 -> 215 deg)
res = []
for k in CAMK:
    if k[1] is None:
        u = (k[0] - 0) / max(build_end, 1); res.append((k[0], 35 + 180 * u, 30, 0.27 + 0.06 * u, (0.022, 0, 0.012)))
    else:
        res.append(k)
CAMK = sorted(res, key=lambda k: k[0])
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 40; cam.data.clip_start = 0.005
tgt = bpy.data.objects.new("tgt", None); sc.collection.objects.link(tgt)
con = cam.constraints.new("TRACK_TO"); con.target = tgt; con.track_axis = "TRACK_NEGATIVE_Z"; con.up_axis = "UP_Y"
for f in range(0, LAST + 1, 2):
    az, el, r, tg = interp_keys(CAMK, f)
    az, el = math.radians(az), math.radians(el)
    tgt.location = tg; tgt.keyframe_insert("location", frame=f)
    cam.location = (tg[0] + r * math.cos(el) * math.cos(az), tg[1] + r * math.cos(el) * math.sin(az), tg[2] + r * math.sin(el))
    cam.keyframe_insert("location", frame=f)
for o in list(bpy.data.objects):
    if o.animation_data and o.animation_data.action:
        pass
sc.frame_start, sc.frame_end = 0, LAST
TM = dict(segments=SEG, subs=SUB, vertex=VTX, stop=STOP, last=LAST, fps=FPS)
json.dump(TM, open(f"{OUT}/timing2.json", "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/frame_speedrun2.blend")
print("TIMELINE2", LAST, [(s["title"], s["start"], s["end"]) for s in SEG])
