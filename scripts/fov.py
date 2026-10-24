"""Fisheye camera-view model for the Caddx Turtle V2 (1.8 mm lens).

Equidistant fisheye: image radius is proportional to the angle off the optical axis.
Two image formats are checked, and a point counts as visible if it lands inside either:
  - DVR recording 16:9, 170 deg diagonal  -> 148.2 x 83.3 deg (H x V)
  - analog FPV 4:3, 155 deg diagonal      -> 124.0 x 93.0 deg
Frame: x forward, y left, z up. Uptilt rotates the optical axis up about +y.
"""
import numpy as np

def _fmt(diag_deg, aw, ah):
    d = np.hypot(aw, ah)
    return diag_deg * aw / d / 2.0, diag_deg * ah / d / 2.0   # half-angles H, V

FORMATS = {"rec_16x9": _fmt(170.0, 16, 9), "fpv_4x3": _fmt(155.0, 4, 3)}

def camera_axes(uptilt_deg):
    a = np.radians(uptilt_deg)
    f = np.array([np.cos(a), 0.0, np.sin(a)])     # optical axis
    r = np.array([0.0, -1.0, 0.0])                # image right = -y
    u = np.cross(r, f)                            # image up
    return f, r, u

def project(points, lens, uptilt_deg):
    """Return (xs, ys) image coords in degrees (equidistant) and theta off-axis."""
    f, r, u = camera_axes(uptilt_deg)
    d = np.asarray(points, float) - np.asarray(lens, float)
    n = np.linalg.norm(d, axis=1)
    d = d / n[:, None]
    cf, cr, cu = d @ f, d @ r, d @ u
    theta = np.degrees(np.arccos(np.clip(cf, -1, 1)))
    psi = np.arctan2(cu, cr)
    return theta * np.cos(psi), theta * np.sin(psi), theta

def margin(points, lens, uptilt_deg):
    """Per point: max over formats of the 'inside-ness' m = max(|xs|/H, |ys|/V).
    m < 1 means the point is inside that frame. Returns the minimum m over formats."""
    xs, ys, th = project(points, lens, uptilt_deg)
    ms = []
    for H, Vh in FORMATS.values():
        m = np.maximum(np.abs(xs) / H, np.abs(ys) / Vh)
        m = np.where(th >= 89.9, np.inf, m)       # behind the lens hemisphere
        ms.append(m)
    return np.minimum(*ms)

def lens_position(pivot, uptilt_deg, pupil_offset):
    f, _, _ = camera_axes(uptilt_deg)
    return np.asarray(pivot, float) + pupil_offset * f

# ---- simple solids sampled as points (for props, motors, battery) ----
def disk_points(cx, cy, z, R, nr=8, nt=72):
    pts = []
    for rr in np.linspace(0, R, nr):
        for t in np.linspace(0, 2 * np.pi, nt, endpoint=False):
            pts.append((cx + rr * np.cos(t), cy + rr * np.sin(t), z))
    return np.array(pts)

def cylinder_points(cx, cy, z0, z1, R, nz=6, nt=48):
    pts = []
    for z in np.linspace(z0, z1, nz):
        for t in np.linspace(0, 2 * np.pi, nt, endpoint=False):
            pts.append((cx + R * np.cos(t), cy + R * np.sin(t), z))
    return np.array(pts)

def box_points(x0, x1, y0, y1, z0, z1, n=12):
    g = [np.linspace(a, b, n) for a, b in ((x0, x1), (y0, y1), (z0, z1))]
    X, Y, Z = np.meshgrid(*g, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    on = ((np.isclose(P[:, 0], x0) | np.isclose(P[:, 0], x1)) |
          (np.isclose(P[:, 1], y0) | np.isclose(P[:, 1], y1)) |
          (np.isclose(P[:, 2], z0) | np.isclose(P[:, 2], z1)))
    return P[on]
