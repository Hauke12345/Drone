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
    wheelbase=155.0,        # motor-to-motor diagonal
    prop_d=88.9,            # 3.5"
    motor_pattern=9.0,      # square M2 pattern (EX1404: 9x9; 12 also possible)
    motor_hole=2.2,
    pad_d=19.0, pad_t=3.0,
    arm_top_z=22.0,         # top of arms = motor seat
    arm_root_h=18.0, arm_root_t=11.0,  # vertical airfoil section at pod wall
    arm_tip_h=11.0,  arm_tip_t=5.0,    # at motor
    arm_wall=0.85,
    arm_rake_deg=0.0,       # tilt of arm section toward oncoming cruise flow (CFD sweep param)
    pod_top_z=27.0,
    pod_wall=1.4, pod_floor=1.6,
    lid_t=1.6,
    cam_pivot=(95.0, 17.0), # x, z of camera pivot (from FOV study)
    cam_size=14.0, cam_depth=12.0,
    uptilt_range=(10.0, 40.0),
    stack_patterns=(25.5, 20.0), stack_boss_h=3.0,
    floor_box=5.0, skin=0.8,   # double-skin floor (closed cells) for torsion stiffness
    gps_seat=26.0,
    strap_slot=(16.0, 3.0), strap_x=26.0, strap_y=12.5,
    arm_t_taper_exp=1.6,    # >1: thickness concentrated at the root (stiff, little blockage under the prop)
    root_flare_len=12.0,    # v3: flared arm root acting as a fillet into the pod
    root_flare_dt=5.0,      #     extra thickness at the wall
    root_flare_dz=4.5,      #     arm top rises toward the pod rim at the wall
    root_flare_dh=3.0,      #     arm bottom drops at the wall
    hood=True, hood_h=37.5, hood_len=57.0, hood_wall=1.0,   # v3: battery nose fairing / GPS hood
    tail_hole_d=7.0,        # v3: smaller tail exit (power lead + antenna)
    density=1.20,
)
if os.environ.get("FRAME_PARAMS"):
    PARAMS.update(json.loads(os.environ["FRAME_PARAMS"]))
P = PARAMS
Rm = P["wheelbase"] / 2.0
MOTOR_ANG = [45.0, 135.0, 225.0, 315.0]          # FL, RL, RR, FR (deg from +x)

# Pod stations: (x, half-width, bottom z, bottom corner radius). Top is flat at pod_top_z.
xp_cam = P["cam_pivot"][0]
STATIONS = [
    (-56.0,  7.0, 11.0, 3.0),
    (-45.0, 14.0,  4.0, 6.0),
    (-34.0, 20.0,  0.0, 7.0),
    (  0.0, 20.0,  0.0, 7.0),
    ( 34.0, 20.0,  0.0, 7.0),
    ( 52.0, 16.5,  1.0, 6.0),
    ( 72.0, 12.5,  1.5, 5.0),
    (xp_cam - 8.0, 10.5, 2.0, 5.0),
    (xp_cam + 1.0, 10.0, 3.0, 5.0),
    (xp_cam + 5.0,  7.5, 7.0, 3.5),
]
STACK_X = (-19.0, 19.0)          # two short stacks: FC+VTX and Turtle DVR board
LID_SCREW_X = (-44.0, 0.0, 42.0, 76.0)
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

def u_section(x, w, zb, rb, ztop):
    p = lambda y, z: V(x, y, z)
    s = math.sqrt(0.5)
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

def airfoil_wire(r, ang_deg, h, t, z_le, rake_deg=0.0, n=28):
    """Vertical symmetric airfoil (leading edge up) in the plane normal to an arm.
    r: radial station, h: chord (height), t: max thickness, z_le: leading-edge z."""
    a = math.radians(ang_deg)
    ar = V(math.cos(a), math.sin(a), 0)
    at = V(-math.sin(a), math.cos(a), 0)
    # side of the arm facing the oncoming cruise flow (+x)
    nx = V(1, 0, 0) - ar * ar.x
    sgn = 1.0 if nx.dot(at) >= 0 else -1.0
    g = -sgn * math.radians(rake_deg)
    tr = t / h
    ss = [(1 - math.cos(math.pi * i / n)) / 2 * 0.97 for i in range(n + 1)]
    pts2 = [(naca_half(tr, s) * h, s) for s in ss]              # upper surface LE->TE
    loop = [(u, s) for u, s in pts2[1:]] + [(0.0, 0.99)] + \
           [(-u, s) for u, s in reversed(pts2[1:])] + [(0.0, 0.0)]
    pts = []
    for u, s in loop:
        v = h / 2 - s * h                                       # + up from mid-chord
        uu = u * math.cos(g) - v * math.sin(g)
        vv = u * math.sin(g) + v * math.cos(g)
        c = ar * r + V(0, 0, z_le - h / 2)
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
    return h + dz + dh, t + P["root_flare_dt"] * f, P["arm_top_z"] + dz

def rot_y(shape, deg, center):
    s = shape.copy(); s.rotate(center, V(0, 1, 0), deg); return s

# ----------------------------------------------------------------------------
print("Building aero 3.5\" frame ...")
ztop = P["pod_top_z"]

# 1. pod outer body: loft of U-sections
outer_w = [u_section(x, w, zb, rb, ztop) for x, w, zb, rb in STATIONS]
pod_outer = Part.makeLoft(outer_w, True, False)
snap("Fuselage sections lofted into a streamlined pod", Part.makeCompound(outer_w + [pod_outer]))

# 2. arms: tapered hollow vertical airfoils
r_wall = 28.0
r_in = 10.0
z_le = P["arm_top_z"]
arms_outer, arms_inner = [], []
for ang in MOTOR_ANG:
    secs = []
    RS = sorted(set([r_in, r_wall - 3.0] + [r_wall + P["root_flare_len"] * f for f in (0, 0.25, 0.5, 0.75, 1.0)] +
                    [r_wall + (Rm + 5.0 - r_wall) * i / 6 for i in range(2, 7)]))
    for r in RS:
        h, t, zl = arm_shape(r, r_wall)
        secs.append(airfoil_wire(r, ang, h, t, zl, P["arm_rake_deg"]))
    arms_outer.append(Part.makeLoft(secs, True, True))
    w_ = P["arm_wall"]
    isecs = []
    RI = sorted(set([r_in, r_wall - 3.0] + [r_wall + P["root_flare_len"] * f for f in (0, 0.25, 0.5, 0.75, 1.0)] +
                    [r_wall + (Rm - 2.5 - r_wall) * i / 6 for i in range(2, 7)]))
    for r in RI:
        h, t, zl = arm_shape(r, r_wall)
        hb, _ = arm_dims(r, r_wall)
        hi = h - 2.6 * w_ - 0.18 * hb                # shorter chord: keeps the thin TE solid
        isecs.append(airfoil_wire(r, ang, hi, t - 2 * w_, zl - 1.3 * w_, P["arm_rake_deg"]))
    arms_inner.append(Part.makeLoft(isecs, True, True))
snap("Four tapered airfoil arms with flared roots", pod_outer.fuse(arms_outer))

# 3. motor pads
pads = []
for ang in MOTOR_ANG:
    a = math.radians(ang)
    c = V(Rm * math.cos(a), Rm * math.sin(a), z_le - P["pad_t"])
    pads.append(Part.makeCylinder(P["pad_d"] / 2, P["pad_t"], c))
body = pod_outer.fuse(arms_outer + pads).removeSplitter()
snap("Motor pads for EX1404", body)

# 4. hollow out: pod cavity (open top) + arm wire channels
inner_st = []
def floor_at(x):
    return P["floor_box"] if -40.0 <= x <= 55.0 else P["pod_floor"]
for x, w, zb, rb in STATIONS[1:-1]:
    inner_st.append((x, w - P["pod_wall"], zb + floor_at(x), max(rb - P["pod_wall"], 1.0)))
x0, w0, zb0, rb0 = STATIONS[0]; x9, w9, zb9, rb9 = STATIONS[-1]
inner_st = [(x0 + 1.5, w0 - P["pod_wall"], zb0 + P["pod_floor"], 1.5)] + inner_st + \
           [(x9 - 1.2, w9 - P["pod_wall"], zb9 + P["pod_floor"], 2.0)]
pod_inner = Part.makeLoft([u_section(x, w, zb, rb, ztop + 5) for x, w, zb, rb in inner_st], True, False)
body = body.cut(pod_inner).cut(arms_inner)
snap("Shelled pod and hollow arms (motor wires run inside)", body)

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
for xs in STACK_X:
    for pat in P["stack_patterns"]:
        for sx in (1, -1):
            for sy in (1, -1):
                q = V(xs + sx * pat / 2, sy * pat / 2, 0)
                bosses.append(Part.makeCylinder(2.6, P["stack_boss_h"] + 0.5, q + V(0, 0, P["floor_box"] - 0.5)))
                holes.append(Part.makeCylinder(1.1, 30, q + V(0, 0, -1)))
                plugs.append(Part.makeCylinder(2.5, 10, q + V(0, 0, -1)))
cells = void.cut(Part.makeCompound(webs + plugs))
body = body.cut(cells)
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
        corbel = Part.makeCylinder(2.6, 7.0, V(bx, y, ztop - 7.0)).fuse(
                 Part.makeCone(0.6, 2.6, 5.0, V(bx, y, ztop - 12.0)))
        bosses.append(corbel.common(pod_outer))
        holes.append(Part.makeCylinder(0.85, 9, V(bx, y, ztop - 8.5)))   # M2 self-tap pilot
inner_struct = bosses[0].fuse(bosses[1:]).common(pod_outer)
body = body.fuse(inner_struct).removeSplitter()
snap("Closed-cell double floor, two stacks (25.5 + 20 mm), lid screw bosses", body)

# 6. motor holes, shaft clearance, wire slots
cuts = []
mp = P["motor_pattern"] / 2
for ang in MOTOR_ANG:
    a = math.radians(ang)
    ar = V(math.cos(a), math.sin(a), 0); at = V(-math.sin(a), math.cos(a), 0)
    c = ar * Rm
    for i in (1, -1):
        for j in (1, -1):
            q = c + ar * (i * mp) + at * (j * mp)
            cuts.append(Part.makeCylinder(P["motor_hole"] / 2, 8, V(q.x, q.y, z_le - 6)))
    cuts.append(Part.makeCylinder(2.75, 5, V(c.x, c.y, z_le - P["pad_t"] - 0.5)))
    slot = Part.makeBox(4.0, 2.6, 6, V(-2.0, -1.3, z_le - 5.5))
    slot.rotate(V(0, 0, 0), V(0, 0, 1), ang)
    slot.translate(ar * (Rm - 4.5))
    cuts.append(slot)
body = body.cut(Part.makeCompound(holes + cuts))
snap("Motor screw holes, shaft clearance and wire slots", body)

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
body = body.cut(Part.makeCylinder(P["tail_hole_d"] / 2, 12, V(tail_x - 2, 0, 18.5), V(1, 0, 0)))  # power lead + antenna
body = body.cut(Part.makeBox(10, 3, 5.5, V(STACK_X[0] - 5, STATIONS[3][1] - 2, 9.5)))  # FC USB slot (left)
body = body.removeSplitter()
chassis = body
snap("Camera bay for 14 mm cam, 10-40 deg uptilt, exits", chassis)

# 8. lid / battery deck: the pod's own top face, extruded, with a shear tongue
top_face = None
for f in pod_outer.Faces:
    if abs(f.normalAt(0, 0).z) > 0.99 and abs(f.CenterOfMass.z - ztop) < 0.01:
        top_face = f
lid = top_face.extrude(V(0, 0, P["lid_t"]))
def band(off, z0, z1):
    ws = []
    for x, w, zb, rb in inner_st:
        y = w - off
        pts = [V(x, -y, z0), V(x, y, z0), V(x, y, z1), V(x, -y, z1), V(x, -y, z0)]
        ws.append(Part.makePolygon(pts))
    return Part.makeLoft(ws, True, False)
tongue = band(0.2, ztop - 3.0, ztop + 0.01).cut(band(1.6, ztop - 3.5, ztop + 0.5))
tongue = tongue.cut(Part.makeCompound([Part.makeCylinder(3.2, 10, V(bx, by, ztop - 5)) for bx, by in lid_boss_xy]))
lid = lid.fuse(tongue)
lcuts = []
sl, sw = P["strap_slot"]
for sx in (1, -1):
    for sy in (1, -1):
        lcuts.append(Part.makeBox(sl, sw, 10, V(sx * P["strap_x"] - sl / 2, sy * P["strap_y"] - sw / 2, ztop - 4)))
for (bx, by) in lid_boss_xy:
    lcuts.append(Part.makeCylinder(1.15, 10, V(bx, by, ztop - 4)))
    lcuts.append(Part.makeCone(1.15, 2.2, 1.1, V(bx, by, ztop + P["lid_t"] - 1.1)))   # countersink
g = P["gps_seat"]
lcuts.append(Part.makeBox(g, g, 1, V(GPS_X - g / 2, -g / 2, ztop + P["lid_t"] - 0.5)))   # GPS seat
for dx in (-g / 2 - 2.5, g / 2 + 0.1):
    lcuts.append(Part.makeBox(2.6, 12.0, 10, V(GPS_X + dx, -6.0, ztop - 4)))              # GPS strap slots
lid = lid.cut(Part.makeCompound(lcuts)).removeSplitter()
# lid nose must stay behind the camera sweep; chamfer the nose top out of the 40 deg view
lid = lid.cut(cam_sweep)
nose_x, nose_z = xp_cam + 5.5, 24.0
wedge = Part.makeBox(60, 60, 40, V(nose_x - 30, -30, nose_z))
wedge.rotate(V(nose_x, 0, nose_z), V(0, 1, 0), 26.0)
lid = lid.cut(wedge).removeSplitter()
chassis = chassis.cut(wedge).removeSplitter()
snap("Structural lid: shear tongue, 8 screws, strap slots, GPS seat", Part.makeCompound([chassis, lid]))

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
    bw = min(lid_half_width(x) - 0.3, 19.5)
    if x >= 45.0:
        b = bw
    else:
        b45 = min(lid_half_width(45.0) - 0.3, 19.5)
        b = 19.5 + (b45 - 19.5) * max(0.0, (x - xb0) / (45.0 - xb0))
    return b, c
def hood_section(x, b, c, zb, ext=0.0, n=40):
    pts = [V(x, b, zb - ext)]
    for i in range(n + 1):
        th = math.pi * i / n
        pts.append(V(x, b * math.cos(th), zb + c * math.sin(th)))
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
        secs_i.append(hood_section(x, max(b - HW, 1.0), max(c - HW, 1.0), z0, ext=1.0))
    inner = Part.makeLoft(secs_i, True, False)
    hood = outer.cut(inner)
    # front screw boss (M2 self-tap from below through the lid) and rear tongue clamped under the battery
    web = Part.makeBox(1.6, 60, 60, V(xb0 + 46.2, -30, z0)).fuse(Part.makeCylinder(3.0, 5.0, V(xb0 + 47.0, 0, z0))).common(outer)  # thin bulkhead + screw boss
    hood = hood.fuse(web).cut(Part.makeCylinder(0.85, 8, V(xb0 + 47.0, 0, z0 - 1)))
    fingers = [Part.makeBox(9.5, 3.9, 0.8, V(xb0 - 7.0, sy * 17.35 - 1.95, z0)) for sy in (1, -1)]   # clamped under the pack
    tongue_h = fingers[0].fuse(fingers[1])
    hood = hood.fuse(tongue_h).removeSplitter()
    lid = lid.cut(Part.makeCylinder(1.15, 6, V(xb0 + 47.0, 0, ztop - 3))).removeSplitter()
    print("HOOD solids", len(hood.Solids), "g", round(hood.Volume * P["density"] / 1000, 2))   # screw clearance in the lid
    snap("Battery nose fairing + GPS hood", Part.makeCompound([chassis, lid, hood]))

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
for xs, zz, sz in ((STACK_X[0], P["floor_box"] + P["stack_boss_h"], 32.0),
                   (STACK_X[0], P["floor_box"] + P["stack_boss_h"] + 7.0, 27.0),
                   (STACK_X[1], P["floor_box"] + P["stack_boss_h"], 27.0)):
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
    h, t = arm_dims(r, r_wall)
    w_ = P["arm_wall"]
    hi = h - 2.6 * w_ - 0.18 * h
    fo = Part.Face(airfoil_wire(r, ang, h, t, z_le, P["arm_rake_deg"]))
    fi = Part.Face(airfoil_wire(r, ang, hi, t - 2 * w_, z_le - 1.3 * w_, P["arm_rake_deg"]))
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
    return dict(r=r, h=h, t=t, area=f.Area, I_vert=Iz2, I_lat=It2, wall_min=wall_min)
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
