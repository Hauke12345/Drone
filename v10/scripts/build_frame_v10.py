# -*- coding: utf-8 -*-
"""Aero 3.5" FPV frame (camera-forward X) — parametric FreeCAD build script.

Run headless:   freecadcmd build_frame.py      (or paste into FreeCAD's macro editor)
Edit the PARAMS block and re-run to regenerate every part.

Axes: x forward, y left, z up. z = 0 is the underside of the pod floor.
Units: mm. Material assumption: PC (1.20 g/cm3).
"""
import os, sys, math, json
import FreeCAD as App
import Part, Mesh
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
OUT = os.environ.get("FRAME_OUT", os.path.join(HERE, "out"))
SNAP = os.path.join(OUT, "snaps")
os.makedirs(SNAP, exist_ok=True)

# ----------------------------------------------------------------------------
PARAMS = dict(
    wheelbase=168.0,        # motor-to-motor diagonal (v5: +13 mm, props clear the 18650 pack)
    prop_d=88.9,            # 3.5"
    motor_pattern=9.0 / math.sqrt(2),   # v9: EX1404 is Φ9 mm (holes on a 9 mm circle) = 6.36 mm square
    motor_hole=2.2,
    pad_d=19.0, pad_t=3.0,
    arm_top_z=22.0,         # top of arms = motor seat
    arm_root_h=18.0, arm_root_t=11.0,  # vertical airfoil section at pod wall
    arm_tip_h=11.0,  arm_tip_t=5.0,    # at motor
    arm_wall=0.85,
    arm_rake_deg=0.0,       # tilt of arm section toward oncoming cruise flow (CFD sweep param)
    pod_top_z=27.0,
    pod_wall=1.2, pod_floor=1.4,      # v6: lighter shell
    lid_t=1.6,
    cam_pivot=(95.0, 17.0), # x, z of camera pivot (from FOV study)
    cam_size=14.0, cam_depth=12.0,
    uptilt_range=(10.0, 40.0),
    stack_patterns=(25.5, 20.0), stack_boss_h=3.0,
    floor_box=5.0, skin=0.8,   # double-skin floor (closed cells) for torsion stiffness
    gps_seat=26.0,
    strap_slot=(14.0, 3.0), strap_xs=(-24.0, 16.0), strap_y=15.5,   # v9: slots further out, clear of the fairing fingers
    arm_t_taper_exp=1.6,    # >1: thickness concentrated at the root (stiff, little blockage under the prop)
    root_flare_len=12.0,    # v3: flared arm root acting as a fillet into the pod
    root_flare_dt=5.0,      #     extra thickness at the wall
    root_flare_dz=4.5,      #     arm top rises toward the pod rim at the wall
    root_flare_dh=3.0,      #     arm bottom drops at the wall
    hood=True, hood_h=37.5, hood_len=57.0, hood_wall=1.0,   # v3: battery nose fairing / GPS hood
    tail_hole_d=7.0,        # v3: smaller tail exit (power lead + antenna)
    density=1.20,
    # v4: motor plug passes through the arms (envelope of a 3-pin JST-PH housing, 8.0 x 4.5 mm, plus clearance)
    conn=True, conn_h=8.0, conn_w=4.5, conn_clear=1.0,
    conn_slot=(21.0, 10.8), # entry slot in the arm top, radial range measured inboard from the motor centre
    # v5: printable without any support (upright, flat bottom on the bed)
    nac_d=19.0, nac_wall=1.0, nac_rib=1.0,   # (v5 column, unused in v6)
    tip_t_mount=8.6,         # v6: arm thickness under the motor pad (side screw heads stay clear of the arm)
    tube_wall=0.8,           # v6: access tube for the inboard motor screw
    tip_blend=14.0,          # arm flares into the column over this length
    pattern_rot=0.0,         # v6: screws on the arm axis and at the sides
    floor_rib=0.9,           # open floor ribs replace the closed-cell double floor
    overhang_deg=60.0,       # end chamfers of the hull (from horizontal)
    bilge_deg=50.0,          # bottom-edge chamfer (hip line with the end cut stays >= 44 deg)
    roof_deg=60.0,           # arm channel roof (its edge in the pod wall stays > 50 deg)
)
if os.environ.get("FRAME_PARAMS"):
    PARAMS.update(json.loads(os.environ["FRAME_PARAMS"]))
P = PARAMS
Rm = P["wheelbase"] / 2.0
MOTOR_ANG = [45.0, 135.0, 225.0, 315.0]          # FL, RL, RR, FR (deg from +x)

# Pod stations: (x, half-width, bottom z, bottom corner radius). Top is flat at pod_top_z.
xp_cam = P["cam_pivot"][0]
STATIONS = [                       # v5: flat bottom (z = 0) everywhere; the ends are cut at 50 deg afterwards
    (-56.0,  7.0, 0.0, 3.0),
    (-45.0, 14.0, 0.0, 6.0),
    (-34.0, 20.0, 0.0, 7.0),
    (  0.0, 20.0, 0.0, 7.0),
    ( 34.0, 20.0, 0.0, 7.0),
    ( 52.0, 16.5, 0.0, 6.0),
    ( 72.0, 12.5, 0.0, 5.0),
    (xp_cam - 8.0, 10.5, 0.0, 5.0),
    (xp_cam + 1.0, 10.0, 0.0, 5.0),
    (xp_cam + 5.0,  7.5, 0.0, 3.5),
]
STACKS = ((-27.0, (20.0,)), (0.0, (25.5, 20.0)), (31.0, (20.0,)))   # v10: VTX rear, AIO in the centre (short motor wires), Turtle board front
STACK_X = tuple(x for x, _ in STACKS)
LID_SCREW_X = (-44.0, 0.0)          # v9: 4 screws behind the fairing; the front is held by 4 snap hooks
LID_HOOK_X = (42.0, 72.0)
GPS_X = 50.0

# ----------------------------------------------------------------------------
steps = []
def snap(name, shape):
    """Save a build-step snapshot (used for the time-lapse)."""
    i = len(steps)
    fn = os.path.join(SNAP, "%02d.stl" % i)
    m = Mesh.Mesh(shape.tessellate(0.25))
    m.write(fn)
    steps.append(dict(i=i, name=name, file=os.path.basename(fn)))
    print("  step %02d  %s" % (i, name))


# ---- speedrun recorder: per-step part meshes plus added / removed material
REC = os.environ.get("RECORD")
rec_prev, rec_steps = {}, []
def rec(title, detail, parts, sketch=None, add=None, rem=None):
    if not REC:
        return
    i = len(rec_steps); d = os.path.join(REC, "%02d" % i); os.makedirs(d, exist_ok=True)
    info = dict(i=i, title=title, detail=detail, parts={}, sketch=[])
    for name, shp in parts.items():
        Mesh.Mesh(shp.copy().tessellate(0.12)).write(os.path.join(d, name + ".stl"))
        e = dict(add=False, rem=False)
        prev = rec_prev.get(name)
        if prev is not None and ((add and name in add) or (rem and name in rem)):
            for key, src in (("add", add), ("rem", rem)):
                if src and name in src:
                    Mesh.Mesh(src[name].copy().tessellate(0.12)).write(os.path.join(d, name + "_%s.stl" % key)); e[key] = True
        elif prev is not None:
            try:
                a = shp.copy().cut(prev.copy())
                if a.Volume > 1.0:
                    Mesh.Mesh(a.tessellate(0.12)).write(os.path.join(d, name + "_add.stl")); e["add"] = True
                r = prev.copy().cut(shp.copy())
                if r.Volume > 1.0:
                    Mesh.Mesh(r.tessellate(0.12)).write(os.path.join(d, name + "_rem.stl")); e["rem"] = True
            except Exception as ex:
                print("rec diff failed", name, ex)
        else:
            e["add"] = True
            Mesh.Mesh(shp.copy().tessellate(0.12)).write(os.path.join(d, name + "_add.stl"))
        e["vol"] = shp.Volume; info["parts"][name] = e
        rec_prev[name] = shp
    for w in (sketch or []):
        info["sketch"].append([[p.x, p.y, p.z] for p in w.discretize(Deflection=0.2)])
    rec_steps.append(info)
    json.dump(rec_steps, open(os.path.join(REC, "steps.json"), "w"))
    print("  rec %02d %s" % (i, title))

def u_section(x, w, zb, rb, ztop, chamfer=False):
    p = lambda y, z: V(x, y, z)
    s = math.sqrt(0.5)
    if chamfer:                                                   # 45 deg bilge: self-supporting when printed upright
        k = math.tan(math.radians(P["bilge_deg"]))
        pts = [p(-w, ztop), p(w, ztop), p(w, zb + rb * k), p(w - rb, zb), p(-w + rb, zb), p(-w, zb + rb * k), p(-w, ztop)]
        return Part.makePolygon(pts)
    e = [Part.LineSegment(p(-w, ztop), p(w, ztop)),
         Part.LineSegment(p(w, ztop), p(w, zb + rb)),
         Part.Arc(p(w, zb + rb), p(w - rb + rb * s, zb + rb - rb * s), p(w - rb, zb)),
         Part.LineSegment(p(w - rb, zb), p(-w + rb, zb)),
         Part.Arc(p(-w + rb, zb), p(-w + rb - rb * s, zb + rb - rb * s), p(-w, zb + rb)),
         Part.LineSegment(p(-w, zb + rb), p(-w, ztop))]
    return Part.Wire([c.toShape() for c in e])

def naca_half(tr, s):
    return 5 * tr * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s**2
                     + 0.2843 * s**3 - 0.1036 * s**4)

def airfoil_wire(r, ang_deg, h, t, z_le, rake_deg=0.0, n=28, lmid=0.0):
    """Vertical symmetric airfoil (leading edge up) in the plane normal to an arm.
    r: radial station, h: chord (height), t: max thickness, z_le: leading-edge z."""
    a = math.radians(ang_deg)
    ar = V(math.cos(a), math.sin(a), 0)
    at = V(-math.sin(a), math.cos(a), 0)
    # side of the arm facing the oncoming cruise flow (+x)
    nx = V(1, 0, 0) - ar * ar.x
    sgn = 1.0 if nx.dot(at) >= 0 else -1.0
    g = -sgn * math.radians(rake_deg)
    c0 = h                                                       # NACA chord; lmid = straight insert at max thickness
    H = c0 + lmid
    tr = t / c0
    SM = 0.2985                                                  # NACA 00xx max-thickness station
    ss = [(1 - math.cos(math.pi * i / n)) / 2 * 0.97 for i in range(n + 1)]
    if lmid > 0:
        ss = sorted(set([x for x in ss if abs(x - SM) > 0.01] + [SM]))
    def zpos(sv, after):                                         # distance from LE along the chord incl. insert
        return sv * c0 + (lmid if after else 0.0)
    up = []
    for sv in ss[1:]:
        u = naca_half(tr, sv) * c0
        if lmid > 0 and abs(sv - SM) < 1e-9:
            up.append((u, zpos(sv, False))); up.append((u, zpos(sv, True)))
        else:
            up.append((u, zpos(sv, sv > SM)))
    loop = up + [(0.0, 0.99 * c0 + lmid)] + [(-u, d) for u, d in reversed(up)] + [(0.0, 0.0)]
    pts = []
    for u, d in loop:
        v = H / 2 - d                                            # + up from mid-chord
        uu = u * math.cos(g) - v * math.sin(g)
        vv = u * math.sin(g) + v * math.cos(g)
        c = ar * r + V(0, 0, z_le - H / 2)
        pts.append(c + at * uu + V(0, 0, vv))
    bs = Part.BSplineCurve()
    bs.interpolate(pts[:-1] if (pts[0] - pts[-1]).Length < 1e-6 else pts, PeriodicFlag=True)
    return Part.Wire(bs.toShape())

def arm_dims(r, r_wall):
    """Linear taper from pod wall to motor; constant inside the pod."""
    k = min(max((r - r_wall) / (Rm - r_wall), 0.0), 1.0)
    h = P["arm_root_h"] + k * (P["arm_tip_h"] - P["arm_root_h"])
    t = P["arm_tip_t"] + (1 - k) ** P["arm_t_taper_exp"] * (P["arm_root_t"] - P["arm_tip_t"])
    return h, t

def arm_shape(r, r_wall):
    """h, t and leading-edge z including the root flare (smooth, fillet-like)."""
    h, t = arm_dims(r, r_wall)
    kf = min(max((r - r_wall) / P["root_flare_len"], 0.0), 1.0)
    f = (1 - kf) ** 2
    dz, dh = P["root_flare_dz"] * f, P["root_flare_dh"] * f
    # v5: tip flare into the motor column (smoothstep), so the arm meets the column without a sharp corner
    r0 = Rm - P["nac_d"] / 2 - P["tip_blend"]
    kt = min(max((r - r0) / P["tip_blend"], 0.0), 1.0); kt = kt * kt * (3 - 2 * kt)
    t = t + kt * max(0.0, P["tip_t_mount"] - t)
    return h + dz + dh, t + P["root_flare_dt"] * f, P["arm_top_z"] + dz

_G = None
def conn_fit(r, r_wall_):
    """(t_eff, lmid) so the inner cavity holds the plug envelope at station r (0 insert if not needed)."""
    h, t, zl = arm_shape(r, r_wall_)
    if not P.get("conn"):
        return t, 0.0
    global _G
    if _G is None:
        import numpy as _np
        S = _np.linspace(0.0, 0.97, 3000); G = _np.array([2 * naca_half(1.0, x) for x in S]); _G = (S, G / G.max())
    S, G = _G
    w_ = P["arm_wall"]; Wc = P["conn_w"] + P["conn_clear"]; Hc = P["conn_h"] + P["conn_clear"]
    tm = Wc + 2 * w_ + 0.6                                       # minimum outer thickness
    te = 0.5 * (t + tm + math.sqrt((t - tm) ** 2 + 0.25))        # smooth max(t, tm)
    hb, _ = arm_dims(r, r_wall_)
    ci = h - 2.6 * w_ - 0.18 * hb; ti = te - 2 * w_
    ok = (G * ti >= Wc).nonzero()[0]
    span = (S[ok[-1]] - S[ok[0]]) * ci if len(ok) else 0.0
    roofk = 0.9 if r <= r_wall_ + 7.0 else 0.5                   # v7: 60 deg roof zone at the pod wall needs more height
    lm = max(0.0, Hc + roofk * Wc - span)                        # v6: + room for a pointed channel roof
    kf_ = min(max((r - (Rm - P["conn_slot"][1] - 1.5)) / 9.0, 0.0), 1.0)
    lm *= 1.0 - kf_ * kf_ * (3 - 2 * kf_)                        # v7: no plug channel past the entry slot -> slim arm tip
    if kf_ > 0: lm = max(lm, 0.3)                                # keep a small insert (a near-zero one makes degenerate sections)
    if _plug_only:
        return te, lm
    # v6: arms hang free (external support under them is allowed)
    return te, lm

_plug_only = False; _ZB = None
def arm_zbot():
    """Lowest underside the plug channel needs anywhere along the arm: the whole arm is made level at that height."""
    global _plug_only, _ZB
    if _ZB is None:
        _plug_only = True
        zs = []
        for i in range(41):
            r = 28.0 + (Rm - P["nac_d"] / 2 - 28.0) * i / 40
            h, t, zl = arm_shape(r, 28.0); te, lm = conn_fit(r, 28.0)
            zs.append(zl - 0.99 * h - lm)
        _plug_only = False
        _ZB = min(zs) - 0.3
        print("ARM underside level at z = %.2f" % _ZB)
    return _ZB

def rot_y(shape, deg, center):
    s = shape.copy(); s.rotate(center, V(0, 1, 0), deg); return s

# ----------------------------------------------------------------------------
def safe_rs(sh):
    """removeSplitter, but keep the unrefined shape if refining makes it invalid."""
    return sh.Solids[0] if len(sh.Solids) == 1 else sh          # v7: refining breaks later booleans on this geometry
print("Building aero 3.5\" frame ...")
ztop = P["pod_top_z"]

# 1. pod outer body: loft of U-sections
outer_w = [u_section(x, w, zb, rb, ztop, chamfer=True) for x, w, zb, rb in STATIONS]
pod_outer = Part.makeLoft(outer_w, True, True)                   # ruled: keeps the 45 deg bilge exact
def end_cut(x0, sign, ang):
    """Half-space below a plane through (x0, z=0) rising at `ang` deg toward sign*x (removes material there)."""
    b = Part.makeBox(200, 400, 200, V(0, -200, -200))
    b.rotate(V(0, 0, 0), V(0, 1, 0), -ang if sign > 0 else ang)   # tilt the top face
    if sign < 0:
        b.rotate(V(0, 0, 0), V(0, 0, 1), 180)
    b.translate(V(x0, 0, 0)); return b
HULL_CUTS = [end_cut(-44.0, -1, P["overhang_deg"]), end_cut(xp_cam - 2.0, 1, P["overhang_deg"])]
pod_outer = pod_outer.cut(Part.makeCompound(HULL_CUTS)).removeSplitter()
snap("Fuselage sections lofted into a streamlined pod", Part.makeCompound(outer_w + [pod_outer]))
rec("Loft the fuselage", "10 U-sections, flat deck at z 27", {"chassis": pod_outer}, sketch=outer_w)

# 2. arms: tapered hollow vertical airfoils
r_wall = 28.0
r_in = 10.0
z_le = P["arm_top_z"]
arms_outer, arms_inner = [], []
for ang in MOTOR_ANG:
    secs = []
    RS = sorted(set([r_in, r_wall - 3.0] + [r_wall + P["root_flare_len"] * f for f in (0, 0.25, 0.5, 0.75, 1.0)] +
                    [47.0, 56.0, 64.0, 70.0, 73.5, 77.0, 80.5, Rm + 2.0]))
    for r in RS:
        h, t, zl = arm_shape(r, r_wall)
        t, lm = conn_fit(r, r_wall)
        t += 0.7 * math.exp(-((r - (Rm - 16.0)) / 6.0) ** 2)      # v7: +0.35 mm wall each side around the plug slot
        secs.append(airfoil_wire(r, ang, h, t, zl, P["arm_rake_deg"], lmid=lm))
    arms_outer.append(Part.makeLoft(secs, True, True))
    w_ = P["arm_wall"]
    isecs = []
    RI = sorted(set([r_in, r_wall - 3.0] + [r_wall + P["root_flare_len"] * f for f in (0, 0.25, 0.5, 0.75, 1.0)] +
                    [47.0, 56.0, 64.0, 70.0, 73.5, 77.0, 80.5, Rm + 0.5]))
    for r in RI:
        h, t, zl = arm_shape(r, r_wall)
        t, lm = conn_fit(r, r_wall)
        hb, _ = arm_dims(r, r_wall)
        hi = h - 2.6 * w_ - 0.18 * hb                # shorter chord: keeps the thin TE solid
        isecs.append(airfoil_wire(r, ang, hi, t - 2 * w_, zl - 1.3 * w_, P["arm_rake_deg"], lmid=lm))
    inner = Part.makeLoft(isecs, True, True)
    # 45 deg roof over the channel (no round ceiling to bridge) and a floor 1.2 mm above the bed
    a_ = math.radians(ang); ar_ = V(math.cos(a_), math.sin(a_), 0); at_ = V(-math.sin(a_), math.cos(a_), 0)
    rsec = []
    for r in RI:
        zt = z_le - 1.3 * w_                                       # level ridge (a ridge rising toward the pod needs support inside the pod - tried in v7)
        q = lambda u, z: ar_ * r + at_ * u + V(0, 0, z)
        zf = -10.0                                                   # the roof only trims the ceiling
        kr = math.tan(math.radians(P["roof_deg"] if r < r_wall + 5.0 else 45.0))   # 60 deg where the channel crosses the pod wall
        rsec.append(Part.makePolygon([q(0, zt), q(8.5, zt - 8.5 * kr), q(8.5, zf), q(-8.5, zf), q(-8.5, zt - 8.5 * kr), q(0, zt)]))
    roof = Part.makeLoft(rsec, True, True)
    _mr = P["motor_pattern"] / 2 * math.sqrt(2)
    _tq = [ar_ * Rm + (ar_ * math.cos(math.radians(P["pattern_rot"] + 90 * kk)) + at_ * math.sin(math.radians(P["pattern_rot"] + 90 * kk))) * _mr for kk in range(4)]
    arms_inner.append(inner.common(roof).cut(Part.makeCompound([Part.makeCylinder(2.2 + P["tube_wall"], 80, V(q_.x, q_.y, -20)) for q_ in _tq])))   # v9: tube wall around every screw
snap("Four tapered airfoil arms with flared roots", pod_outer.fuse(arms_outer))
rec("Airfoil arms", "vertical NACA sections, flared roots", {"chassis": pod_outer.fuse(arms_outer)},
    sketch=[airfoil_wire(r, a, *arm_shape(r, 28.0)[:2], arm_shape(r, 28.0)[2]) for a in MOTOR_ANG for r in (28.0, 52.0, Rm)])

# 3. motor pads
pads, cups, tubes_o, tubes_i = [], [], [], []
mp_r = P["motor_pattern"] / 2 * math.sqrt(2)
for k, ang in enumerate(MOTOR_ANG):
    a = math.radians(ang); ar = V(math.cos(a), math.sin(a), 0)
    c = V(Rm * math.cos(a), Rm * math.sin(a), z_le - P["pad_t"])
    pads.append(Part.makeCylinder(P["pad_d"] / 2, P["pad_t"], c))
    at = V(-math.sin(a), math.cos(a), 0)
    for kk in range(4):                                                        # v9: every screw gets a driver tube from below
        th_ = math.radians(P["pattern_rot"] + 90 * kk)
        q = ar * Rm + (ar * math.cos(th_) + at * math.sin(th_)) * mp_r
        tubes_o.append(Part.makeCylinder(2.2 + P["tube_wall"], z_le - P["pad_t"] + 1.0, V(q.x, q.y, -1.0)).common(arms_outer[k]))
        tubes_i.append(Part.makeCylinder(2.2, z_le - P["pad_t"] + 1.0, V(q.x, q.y, -1.0)))   # M2 head + driver from below
body = pod_outer.fuse(arms_outer + pads).Solids[0]              # v7: refining this fuse gives an invalid shape, keep it unrefined
snap("Motor pads for EX1404", body)
rec("Motor pads", "\u00d8 19 mm seats for EX1404", {"chassis": body})

# 4. hollow out: pod cavity (open top) + arm wire channels
inner_st = []
def floor_at(x):
    return P["pod_floor"]                                         # v5: single floor + open ribs
def rb_in(rb, fl):
    # inner chamfer parallel to the outer 45 deg bilge: constant wall thickness
    a = math.radians(P["bilge_deg"]); wl = P["pod_wall"]
    return max(rb - wl - (fl - wl / math.cos(a)) / math.tan(a), 0.8)
for x, w, zb, rb in STATIONS[1:-1]:
    inner_st.append((x, w - P["pod_wall"], zb + floor_at(x), rb_in(rb, floor_at(x))))
x0, w0, zb0, rb0 = STATIONS[0]; x9, w9, zb9, rb9 = STATIONS[-1]
inner_st = [(x0 + 1.5, w0 - P["pod_wall"], zb0 + P["pod_floor"], rb_in(rb0, P["pod_floor"]))] + inner_st + \
           [(x9 - 1.2, w9 - P["pod_wall"], zb9 + P["pod_floor"], rb_in(rb9, P["pod_floor"]))]
pod_inner = Part.makeLoft([u_section(x, w, zb, rb, ztop + 5, chamfer=True) for x, w, zb, rb in inner_st], True, True)
_sh = P["pod_wall"] / math.cos(math.radians(P["overhang_deg"])) + 0.2        # same 50 deg end cuts, one wall further in
_ic = [c.copy() for c in HULL_CUTS]
for c in _ic: c.translate(V(0, 0, _sh))
pod_inner = pod_inner.cut(Part.makeCompound(_ic))
body = body.cut(pod_inner)
for _ai in arms_inner:
    body = body.cut(_ai)
print("shell valid", body.isValid(), len(body.Solids))
body = safe_rs(body.cut(Part.makeCompound(tubes_i)))
body = body.common(Part.makeBox(600, 600, 200, V(-300, -300, 0.0)))     # flat foot: everything sits on z = 0
snap("Shelled pod and hollow arms (motor wires run inside)", body)
rec("Shell it", "1.4 mm pod, 0.85 mm hollow arms", {"chassis": body})

# 5. internal structure: closed-cell double floor, two stacks, lid screw bosses
sk = P["skin"]
void_st = [st for st in STATIONS if -34.0 <= st[0] <= 52.0]
void = Part.makeLoft([u_section(x, w - P["pod_wall"] - 2.1, zb + sk, 3.0, zb + P["floor_box"] - sk)
                      for x, w, zb, rb in void_st], True, False)
webs = []
for y in (-12.0, -6.0, 0.0, 6.0, 12.0):
    webs.append(Part.makeBox(120, sk, 10, V(-50, y - sk / 2, -1)))
for x in (-17.0, 0.0, 17.0, 34.0):
    webs.append(Part.makeBox(sk, 60, 10, V(x - sk / 2, -30, -1)))
bosses, holes, plugs = [], [], []
for xs, pats in STACKS:
    for pat in pats:
        for sx in (1, -1):
            for sy in (1, -1):
                q = V(xs + sx * pat / 2, sy * pat / 2, 0)
                bosses.append(Part.makeCylinder(2.6, P["floor_box"] + P["stack_boss_h"] - P["pod_floor"] + 0.5, q + V(0, 0, P["pod_floor"] - 0.5)))
                holes.append(Part.makeCylinder(1.1, 30, q + V(0, 0, -1)))
                bosses.append(Part.makeCylinder(3.4, 2.8, q + V(0, 0, P["pod_floor"] - 0.5)))      # v9: thicker foot around the counterbore
                holes.append(Part.makeCylinder(2.05, 3.2, q + V(0, 0, -1.0)))                     # v9: M2 head sunk 2.2 mm into the bottom
                plugs.append(Part.makeCylinder(2.5, 10, q + V(0, 0, -1)))
cells = Part.makeCompound([])                                  # v5: no closed cells (their ceilings need support)
rib_zone = Part.makeLoft([u_section(x, w - P["pod_wall"] + 0.3, P["pod_floor"] - 0.2, 3.0, P["floor_box"])
                          for x, w, zb, rb in void_st], True, False)
ribs = Part.makeCompound([Part.makeBox(120, P["floor_rib"], 10, V(-50, y - P["floor_rib"] / 2, -1)) for y in (-12.0, -6.0, 0.0, 6.0, 12.0)] +
                         [Part.makeBox(P["floor_rib"], 60, 10, V(x - P["floor_rib"] / 2, -30, -1)) for x in (-17.0, 0.0, 17.0, 34.0)]).common(rib_zone)
bosses.append(ribs)
# v9: low bridges between the two stacks (boss height), joining the facing bosses of both patterns
_zb = P["pod_floor"] - 0.5; _hb = P["floor_box"] + P["stack_boss_h"] - _zb
for (xa, pa), (xb_, pb) in zip(STACKS, STACKS[1:]):         # v10: bridge each pair of neighbouring stacks
    x0_, x1_ = xa + max(pa) / 2 - 2.0, xb_ - max(pb) / 2 + 2.0
    for sy in (1, -1):
        bosses.append(Part.makeBox(x1_ - x0_, 1.6, _hb, V(x0_, sy * 11.4 - 0.8, _zb)))
lid_boss_xy = []
def inner_half_width(x):
    for (xa, wa, *_), (xb, wb, *_) in zip(STATIONS, STATIONS[1:]):
        if xa <= x <= xb:
            return wa + (wb - wa) * (x - xa) / (xb - xa) - P["pod_wall"]
for bx in LID_SCREW_X:
    wi = inner_half_width(bx)
    for sy in (1, -1):
        y = sy * (wi - 1.8)
        lid_boss_xy.append((bx, y))
        z0 = ztop - 7.0; yw = sy * (wi + 0.4)
        gus = Part.makeLoft([Part.Wire(Part.makeCircle(0.4, V(bx, yw, z0 - 6.5))), Part.Wire(Part.makeCircle(2.6, V(bx, y, z0)))], True, False)
        corbel = Part.makeCylinder(2.6, 7.0, V(bx, y, z0)).fuse(gus)
        bosses.append(corbel.common(pod_outer))
        holes.append(Part.makeCylinder(0.85, 9, V(bx, y, ztop - 8.5)))   # M2 self-tap pilot
inner_struct = bosses[0].fuse(bosses[1:]).common(pod_outer)
body = safe_rs(body.fuse(inner_struct))
snap("Closed-cell double floor, three mounts: AIO centre, VTX, Turtle, lid screw bosses", body)
rec("Floor, stacks, bosses", "closed-cell floor, 3 board mounts, 8 screw bosses", {"chassis": body},
    add={"chassis": inner_struct}, rem={"chassis": cells})

# 6. motor holes, shaft clearance, wire slots
cuts = []
mp = P["motor_pattern"] / 2
for ang in MOTOR_ANG:
    a = math.radians(ang)
    ar = V(math.cos(a), math.sin(a), 0); at = V(-math.sin(a), math.cos(a), 0)
    c = ar * Rm
    for k in range(4):
        th = math.radians(P["pattern_rot"] + 90.0 * k)
        q = c + (ar * math.cos(th) + at * math.sin(th)) * (mp * math.sqrt(2))
        cuts.append(Part.makeCylinder(P["motor_hole"] / 2, 8, V(q.x, q.y, z_le - 6)))
    cuts.append(Part.makeCylinder(2.4, 6.0, V(c.x, c.y, z_le - 5.0)))       # shaft clearance (v9: smaller for the Φ9 pattern)
    if P.get("conn"):                                            # plug entry: rounded slot in the arm top, inboard of the pad
        r0, r1 = Rm - P["conn_slot"][0], Rm - P["conn_slot"][1]
        wd = P["conn_w"] + P["conn_clear"] + 0.4
        cs = Part.makeBox(r1 - r0 - wd, wd, 9, V(r0 + wd / 2, -wd / 2, z_le - 7))
        for rr in (r0 + wd / 2, r1 - wd / 2):
            cs = cs.fuse(Part.makeCylinder(wd / 2, 9, V(rr, 0, z_le - 7)))
        cs.rotate(V(0, 0, 0), V(0, 0, 1), ang)
        cuts.append(cs.removeSplitter())
body = body.cut(Part.makeCompound(holes + cuts))
snap("Motor screw holes, shaft clearance and wire slots", body)
rec("Motor holes + wire slots", "\u03a69 M2, wires run inside the arms", {"chassis": body})

# 7. camera bay: lens window swept over the uptilt range, pivot holes, exits
cx, cz = P["cam_pivot"]
piv = V(cx, 0, cz)
cam_cut = []
u0, u1 = P["uptilt_range"]
k = 0
while u0 + k * 2.5 <= u1 + 1e-6:
    u = u0 + k * 2.5
    cyl = Part.makeCylinder(5.6, 30, V(cx + 3, 0, cz), V(1, 0, 0))
    cam_cut.append(rot_y(cyl, -u, piv))
    cs, cd = P["cam_size"] + 0.6, P["cam_depth"] + 0.6
    bx = Part.makeBox(cd, cs, cs, V(cx - cd / 2, -cs / 2, cz - cs / 2))
    cam_cut.append(rot_y(bx, -u, piv))
    k += 1
cam_sweep = cam_cut[0].fuse(cam_cut[1:])
body = body.cut(cam_sweep)
body = body.cut(Part.makeCylinder(1.1, 40, V(cx, -20, cz), V(0, 1, 0)))          # M2 pivot
tail_x = STATIONS[0][0]
_tr = P["tail_hole_d"] / 2
_td = Part.makeCylinder(_tr, 14, V(tail_x - 3, 0, 18.5), V(1, 0, 0)).fuse(
      Part.makeBox(14, _tr * math.sqrt(2), _tr * math.sqrt(2), V(tail_x - 3, 0, 18.5)).copy())
_bx = Part.makeBox(14, 2 * _tr, 2 * _tr, V(0, -_tr, -_tr))   # diamond tangent to the circle -> 45 deg pointed top
_bx.rotate(V(0, 0, 0), V(1, 0, 0), 45); _bx.translate(V(tail_x - 3, 0, 18.5))
# v9: tall tail exit that passes an XT30 plug turned on its side (plug 10.2 x 5.2 mm): 6.6 wide, 13 tall + 45 deg gable top
_w, _z0, _z1 = 6.6, 7.5, 20.5
_slot = Part.makeBox(14, _w, _z1 - _z0, V(tail_x - 3, -_w / 2, _z0))
_g = Part.makeBox(14, _w / math.sqrt(2), _w / math.sqrt(2), V(0, 0, 0)); _g.rotate(V(0, 0, 0), V(1, 0, 0), 45)
_g.translate(V(tail_x - 3, 0, _z1 - _w / 2))
body = body.cut(_slot.fuse(_g))
_ux = -8.0                                   # v10: AIO USB-C, clear of the x = 0 lid-screw corbel
_usb = Part.makePolygon([V(_ux - 5, 0, 9.5), V(_ux + 5, 0, 9.5), V(_ux + 5, 0, 13.0),
                         V(_ux, 0, 18.0), V(_ux - 5, 0, 13.0), V(_ux - 5, 0, 9.5)])
body = body.cut(Part.Face(_usb).extrude(V(0, 4.0, 0)).translated(V(0, STATIONS[3][1] - 2.5, 0)))   # FC USB slot, 45 deg gable top
# v7 cooling: prop wash enters through the plug slots and arm channels; exits = floor slots under both stacks
# (printed on the bed) and 45 deg diamonds in the side walls (work when the quad sits on the ground)
vents = []
for xa, xb in ((-27.5, -18.3), (-15.7, -9.0), (9.0, 15.7), (18.3, 27.5)):
    for yc in (3.0, -3.0):
        vents.append(Part.makeBox(xb - xa - 3.4, 3.4, 5, V(xa + 1.7, yc - 1.7, -1)).fuse(
                     [Part.makeCylinder(1.7, 5, V(xx, yc, -1)) for xx in (xa + 1.7, xb - 1.7)]))
for xv in (-37.0, 36.0, 48.0, 56.0):
    for sy in (1, -1):
        dmd = Part.makeBox(4.5, 16, 4.5, V(-2.25, -8, -2.25)); dmd.rotate(V(0, 0, 0), V(0, 1, 0), 45)
        dmd.translate(V(xv, sy * 18.0, 18.0)); vents.append(dmd)
body = body.cut(Part.makeCompound(vents))
body = safe_rs(body)
chassis = body
snap("Camera bay for 14 mm cam, 10-40 deg uptilt, exits", chassis)
rec("Camera bay + exits", "14 mm cam, 10\u201340\u00b0 uptilt sweep", {"chassis": chassis},
    rem={"chassis": cam_sweep.common(pod_outer)})

# 8. lid / battery deck: the pod's own top face, extruded, with a shear tongue
top_faces = [f for f in pod_outer.Faces if abs(f.normalAt(0, 0).z) > 0.99 and abs(f.CenterOfMass.z - ztop) < 0.01]
_ex = [f.extrude(V(0, 0, P["lid_t"])) for f in top_faces]
lid = _ex[0].fuse(_ex[1:]).removeSplitter() if len(_ex) > 1 else _ex[0]
def band(off, z0, z1):
    ws = []
    for x, w, zb, rb in inner_st:
        y = w - off
        pts = [V(x, -y, z0), V(x, y, z0), V(x, y, z1), V(x, -y, z1), V(x, -y, z0)]
        ws.append(Part.makePolygon(pts))
    return Part.makeLoft(ws, True, True)        # v10: ruled, so the lip follows the faceted wall (was a smooth spline loft)
tongue = band(0.2, ztop - 3.0, ztop + 0.01).cut(band(1.6, ztop - 3.5, ztop + 0.5))
tongue = tongue.cut(Part.makeCompound([Part.makeCylinder(3.2, 10, V(bx, by, ztop - 5)) for bx, by in lid_boss_xy]))
# v9 snap hooks: flexible fingers below the tongue with a barb that clicks into a window in the pod wall
def w_in(x):
    for (xa, wa, *_), (xb, wb, *_) in zip(inner_st, inner_st[1:]):
        if xa <= x <= xb: return wa + (wb - wa) * (x - xa) / (xb - xa)
HK_W, HK_T, HK_L, BARB = 6.0, 1.3, 7.5, 0.6     # ~2 % bending strain at full deflection (PETG ok)
hooks, hgaps, windows = [], [], []
for hx in LID_HOOK_X:
    wy = w_in(hx); slope = (w_in(hx + 1.0) - w_in(hx - 1.0)) / 2.0; ang = math.degrees(math.atan(slope))
    for sy in (1, -1):
        # local frame: x along the wall, y outward (sy), z up; built at the origin then placed
        fin = Part.makeBox(HK_W, HK_T, HK_L + 0.3, V(-HK_W / 2, -HK_T, -HK_L))                   # finger, outer face at y = 0
        barb = Part.makePolygon([V(0, 0, -HK_L), V(0, BARB, -HK_L + BARB * 1.6), V(0, BARB, -HK_L + BARB * 1.6 + 1.0),
                                 V(0, 0, -HK_L + BARB * 1.6 + 1.0 + BARB), V(0, 0, -HK_L)])
        barb = Part.Face(barb).extrude(V(HK_W, 0, 0)).translated(V(-HK_W / 2, 0, 0))     # 58 deg lead-in, 45 deg back face
        gap = Part.makeBox(HK_W + 1.0, 3.0, 4.0, V(-HK_W / 2 - 0.5, -2.5, -3.5))            # free the finger from the tongue
        win = Part.makeBox(HK_W + 0.6, 4.0, BARB * 1.6 + 1.0 + BARB + 0.6, V(-HK_W / 2 - 0.3, -1.0, -HK_L - 0.3))
        for sh, lst in ((fin.fuse(barb), hooks), (gap, hgaps), (win, windows)):
            sh = sh.copy()
            if sy < 0: sh = sh.mirror(V(0, 0, 0), V(0, 1, 0))
            sh.rotate(V(0, 0, 0), V(0, 0, 1), sy * ang)
            sh.translate(V(hx, sy * (wy - 0.25), ztop))
            lst.append(sh)
tongue = tongue.cut(Part.makeCompound(hgaps))
lid = lid.fuse(tongue).fuse(hooks)
chassis = chassis.cut(Part.makeCompound(windows))
lcuts = []
sl, sw = P["strap_slot"]
for sxx in P["strap_xs"]:
    for sy in (1, -1):
        lcuts.append(Part.makeBox(sl, sw, 10, V(sxx - sl / 2, sy * P["strap_y"] - sw / 2, ztop - 4)))
for (bx, by) in lid_boss_xy:
    lcuts.append(Part.makeCylinder(1.15, 10, V(bx, by, ztop - 4)))
    lcuts.append(Part.makeCone(1.15, 2.2, 1.1, V(bx, by, ztop + P["lid_t"] - 1.1)))   # countersink
g = P["gps_seat"]
# v5: no GPS locating recess (it would be a 25 mm bridge on the first layers when the lid prints top-down)
lcuts.append(Part.makeBox(2.6, 12.0, 10, V(GPS_X + g / 2 + 0.1, -6.0, ztop - 4)))           # front GPS strap slot
# v9: XT30 pass-through under the fairing, just ahead of the battery; doubles as the rear GPS strap slot
lcuts.append(Part.makeBox(6.0, 11.8, 10, V(GPS_X - g / 2 - 6.0 + 0.1, -5.9, ztop - 4)))
lid = lid.cut(Part.makeCompound(lcuts)).removeSplitter()
pocket = band(4.0, ztop - 0.01, ztop + 0.4).common(Part.makeBox(128, 60, 5, V(-48, -30, ztop - 1)))
keep = [Part.makeCylinder(4.2, 5, V(bx, by, ztop - 1)) for bx, by in lid_boss_xy]
keep += [Part.makeBox(sl + 5, sw + 5, 5, V(sxx - sl / 2 - 2.5, sy * P["strap_y"] - sw / 2 - 2.5, ztop - 1)) for sxx in P["strap_xs"] for sy in (1, -1)]
keep += [Part.makeBox(7.6, 17.0, 5, V(GPS_X + g / 2 + 0.1 - 2.5, -8.5, ztop - 1)), Part.makeBox(10.0, 16.0, 5, V(GPS_X - g / 2 - 8.0, -8.0, ztop - 1))]
keep += [Part.makeCylinder(3.6, 5, V(31.0 + 47.0, 0, ztop - 1))]
keep += [Part.makeBox(1.6, 60, 5, V(xr - 0.8, -30, ztop - 1)) for xr in (-38, -19, 0, 19, 38, 57)]
lid = lid.cut(pocket.cut(Part.makeCompound(keep))).removeSplitter()       # v7: 1.2 mm skin between 1.6 mm ribs
# lid nose must stay behind the camera sweep; chamfer the nose top out of the 40 deg view
lid = lid.cut(cam_sweep)
nose_x, nose_z = xp_cam + 5.5, 24.0
wedge = Part.makeBox(60, 60, 40, V(nose_x - 30, -30, nose_z))
wedge.rotate(V(nose_x, 0, nose_z), V(0, 1, 0), 26.0)
lid = lid.cut(wedge).removeSplitter()
chassis = safe_rs(chassis.cut(wedge))
snap("Structural lid: shear tongue, 8 screws, strap slots, GPS seat", Part.makeCompound([chassis, lid]))
rec("Structural lid", "shear tongue, 8 screws, strap slots", {"chassis": chassis, "lid": lid})

# 9. v3: battery nose fairing that also hoods the GPS (separate print, clamped by the battery + one screw)
def lid_half_width(x):
    for (xa, wa, *_), (xb, wb, *_) in zip(STATIONS, STATIONS[1:]):
        if xa <= x <= xb:
            return wa + (wb - wa) * (x - xa) / (xb - xa)
    return STATIONS[-1][1]
z0 = ztop + P["lid_t"]                 # lid top
xb0 = 31.0                             # battery front face (4S1P 2x2 pack position)
HL, HH, HW = P["hood_len"], P["hood_h"], P["hood_wall"]
def hood_bc(x):
    u = min(max((x - xb0) / HL, 0.0), 1.0)
    c = max(HH * math.sqrt(max(1 - u * u, 0.0)), 2.5)
    bw = min(lid_half_width(x) - 0.3, 17.0)          # v5: narrower in the prop band
    if x >= 45.0:
        b = bw
    else:
        b45 = min(lid_half_width(45.0) - 0.3, 19.5)
        b = 19.5 + (b45 - 19.5) * max(0.0, (x - xb0) / (45.0 - xb0))
    # v5: stay outside the front prop discs (1 mm margin) but keep room for the 25 mm GPS
    Rp = P["prop_d"] / 2 + 1.0; cxp = Rm * math.cos(math.radians(45.0))
    if abs(x - cxp) < Rp:
        b = min(b, max((cxp - math.sqrt(Rp ** 2 - (x - cxp) ** 2)) / 0.99, 12.5 + HW + 0.15))
    return b, c
def hood_section(x, b, c, zb, ext=0.0, n=40):
    # v7: pointed arch. Ellipse (b, c') up to the 45 deg point, then straight 45 deg flanks to an apex at height c
    b = min(b, 0.8 * c)                                          # a 45 deg roof over half-width b needs height >= b (0.8: well-shaped sections)
    cp = math.sqrt(max(c * c - b * b, 1e-4))
    th45 = math.atan2(cp, b)
    pts = [V(x, b, zb - ext)]
    for i in range(n + 1):
        th = th45 * i / n
        pts.append(V(x, b * math.cos(th), zb + cp * math.sin(th)))
    pts.append(V(x, 0, zb + c))
    for i in range(n, -1, -1):
        th = th45 * i / n
        pts.append(V(x, -b * math.cos(th), zb + cp * math.sin(th)))
    pts.append(V(x, -b, zb - ext))
    pts.append(V(x, b, zb - ext))
    return Part.makePolygon(pts)
hood = None
if P["hood"]:
    xs_o = [xb0 + d for d in (0, 4, 9, 15, 21, 27, 33, 39, 45, 50, 54, HL - 0.5)]
    outer = Part.makeLoft([hood_section(x, *hood_bc(x), z0) for x in xs_o], True, False)
    xs_i = [xb0 - 1.0] + [x for x in xs_o[1:-2]] + [xb0 + 53.0]
    secs_i = []
    for x in xs_i:
        b, c = hood_bc(max(x, xb0))
        secs_i.append(hood_section(x, max(b - HW, 1.0), max(c - 1.42 * HW, 1.0), z0, ext=1.0))
    inner = Part.makeLoft(secs_i, True, False)
    hood = outer.cut(inner)
    # front screw boss (M2 self-tap from below through the lid) and rear tongue clamped under the battery
    web = Part.makeBox(1.6, 60, 60, V(xb0 + 46.2, -30, z0)).fuse(Part.makeCylinder(3.0, 5.0, V(xb0 + 47.0, 0, z0))).common(outer)  # thin bulkhead + screw boss
    hood = hood.fuse(web).cut(Part.makeCylinder(0.85, 8, V(xb0 + 47.0, 0, z0 - 1)))
    fingers = [Part.makeBox(9.5, 3.9, 0.8, V(xb0 - 7.0, sy * 17.35 - 1.95, z0)) for sy in (1, -1)]   # clamped under the pack
    tongue_h = fingers[0].fuse(fingers[1])
    hood = hood.fuse(tongue_h).cut(Part.makeBox(300, 100, 6, V(-50, -50, z0 - 6))).removeSplitter()   # v7: flat base (loft overshoot at the nose trimmed)
    lid = lid.cut(Part.makeCylinder(1.15, 6, V(xb0 + 47.0, 0, ztop - 3))).removeSplitter()
    print("HOOD solids", len(hood.Solids), "g", round(hood.Volume * P["density"] / 1000, 2))   # screw clearance in the lid
    snap("Battery nose fairing + GPS hood", Part.makeCompound([chassis, lid, hood]))
    rec("Battery nose fairing", "GPS hood, 6 g, clamped by the pack", {"chassis": chassis, "lid": lid, "hood": hood})

# ----------------------------------------------------------------------------
# Reference parts (not printed): motors, props, camera, batteries
def motor_ref(ang):
    a = math.radians(ang); c = V(Rm * math.cos(a), Rm * math.sin(a), z_le)
    m = Part.makeCylinder(8.9, 13.5, c)
    p = Part.makeCylinder(P["prop_d"] / 2, 0.8, c + V(0, 0, 14.0))
    return m, p
motors, props = zip(*[motor_ref(a) for a in MOTOR_ANG])
cam_up = 20.0
cam = Part.makeBox(P["cam_depth"], P["cam_size"], P["cam_size"],
                   V(cx - P["cam_depth"] / 2, -P["cam_size"] / 2, cz - P["cam_size"] / 2))
cam = cam.fuse(Part.makeCylinder(4.0, 5.0, V(cx + P["cam_depth"] / 2, 0, cz), V(1, 0, 0)))
cam = rot_y(cam, -cam_up, piv)
liion = Part.makeBox(66, 37, 37, V(-35, -18.5, ztop + P["lid_t"]))        # 4S1P 18650, 2x2
lipo = Part.makeBox(57, 30, 28, V(-30, -15, ztop + P["lid_t"]))            # 4S 650-850 tabless
gps = Part.makeBox(25, 25, 8, V(GPS_X - 12.5, -12.5, ztop + P["lid_t"] - 0.5))
boards = []
for xs, zz, sz in ((STACK_X[1], P["floor_box"] + P["stack_boss_h"], 32.0),
                   (STACK_X[0], P["floor_box"] + P["stack_boss_h"], 27.0),
                   (STACK_X[2], P["floor_box"] + P["stack_boss_h"], 27.0)):
    boards.append(Part.makeBox(sz, sz, 1.6, V(xs - sz / 2, -sz / 2, zz)))
snap("Fit check: motors, props, boards, Turtle V2, GPS, 4S1P 18650 pack",
     Part.makeCompound([chassis, lid] + list(motors) + list(props) + [cam, liion, gps] + boards))

# ----------------------------------------------------------------------------
# Exports
doc = App.newDocument("AeroFrame35")
def add(name, shp):
    o = doc.addObject("Part::Feature", name); o.Shape = shp; return o
add("Chassis", chassis); add("Lid", lid)
if hood is not None: add("Hood", hood)
for i, (m, p) in enumerate(zip(motors, props)):
    add("ref_Motor%d" % i, m); add("ref_Prop%d" % i, p)
add("ref_GPS", gps)
for i, bd in enumerate(boards): add("ref_Board%d" % i, bd)
add("ref_Camera", cam); add("ref_Battery_4S1P_18650", liion); add("ref_Battery_LiPo_tabless", lipo)
sh = doc.addObject("Spreadsheet::Sheet", "Params")
for i, (kk, vv) in enumerate(PARAMS.items()):
    sh.set("A%d" % (i + 1), kk); sh.set("B%d" % (i + 1), str(vv))
doc.recompute()
doc.saveAs(os.path.join(OUT, "AeroFrame35.FCStd"))
Part.makeCompound([chassis, lid] + ([hood] if hood is not None else [])).exportStep(os.path.join(OUT, "AeroFrame35.step"))
for name, shp in (("chassis", chassis), ("lid", lid)) + ((("hood", hood),) if hood is not None else ()):
    Mesh.Mesh(shp.tessellate(0.02)).write(os.path.join(OUT, "AeroFrame35_%s.stl" % name))
Part.makeCompound(list(motors) + list(props) + [cam, liion, gps] + boards).exportStep(os.path.join(OUT, "reference_parts.step"))

# ----------------------------------------------------------------------------
# Report: mass, validity, arm section properties
rep = dict(params=PARAMS, steps=steps)
rho = P["density"] / 1000.0   # g/mm3
rep["chassis_valid"] = chassis.isValid(); rep["lid_valid"] = lid.isValid()
rep["chassis_g"] = chassis.Volume * rho; rep["lid_g"] = lid.Volume * rho
rep["hood_g"] = hood.Volume * rho if hood is not None else 0.0
rep["lid_screw_xy"] = lid_boss_xy
rep["chassis_solids"] = len(chassis.Solids); rep["lid_solids"] = len(lid.Solids)

def section_props(r, ang=45.0):
    h, t, zl = arm_shape(r, r_wall)
    hb, _ = arm_dims(r, r_wall)
    t, lm = conn_fit(r, r_wall)
    w_ = P["arm_wall"]
    hi = h - 2.6 * w_ - 0.18 * hb
    fo = Part.Face(airfoil_wire(r, ang, h, t, zl, P["arm_rake_deg"], lmid=lm))
    fi = Part.Face(airfoil_wire(r, ang, hi, t - 2 * w_, zl - 1.3 * w_, P["arm_rake_deg"], lmid=lm))
    f = fo.cut(fi)
    wall_min = fo.Wires[0].distToShape(fi.Wires[0])[0]
    # rotate section into the (t, z) plane: face lies in plane normal to radial dir
    M = f.MatrixOfInertia      # about centre of mass, global axes
    a = math.radians(ang)
    at = V(-math.sin(a), math.cos(a), 0)
    # I_vert (bending under thrust, about the in-plane tangential axis) = integral of dz^2
    Izz_axis = M.A33
    I_t = f.Area  # placeholder
    # second moments: about tangential axis -> sum dz^2 ; about z axis -> sum dt^2
    # MatrixOfInertia gives I_ij = integral(r^2 delta_ij - x_i x_j); use components.
    Ixx, Iyy, Izz = M.A11, M.A22, M.A33
    Ixy = M.A12
    # integral z^2 = (Ixx + Iyy - Izz)/2 ; integral of (t-coordinate)^2 = Izz - integral(radial^2)=Izz (radial thickness 0)
    Iz2 = (Ixx + Iyy - Izz) / 2.0
    It2 = Izz
    return dict(r=r, h=h + lm, t=t, lmid=lm, area=f.Area, I_vert=Iz2, I_lat=It2, wall_min=wall_min)
rep["arm_sections"] = [section_props(r) for r in [r_wall + (Rm - 3 - r_wall) * i / 8 for i in range(9)]]
json.dump(rep, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
print(json.dumps({k: rep[k] for k in ("chassis_valid", "lid_valid", "chassis_g", "lid_g",
                                      "chassis_solids", "lid_solids")}, indent=1))
for s in rep["arm_sections"]:
    print("arm r=%.1f h=%.1f t=%.1f A=%.1f Iv=%.0f Il=%.0f wall_min=%.2f" %
          (s["r"], s["h"], s["t"], s["area"], s["I_vert"], s["I_lat"], s["wall_min"]))

# Round-trip check: re-read the exported parts and make sure they are closed solids
for name, shp in (("chassis", chassis), ("lid", lid)) + ((("hood", hood),) if hood is not None else ()):
    fn = os.path.join(OUT, "_rt_%s.step" % name)
    shp.exportStep(fn)
    r = Part.read(fn)
    print("ROUNDTRIP %s solids=%d valid=%s" % (name, len(r.Solids), r.isValid()))
    os.remove(fn)
