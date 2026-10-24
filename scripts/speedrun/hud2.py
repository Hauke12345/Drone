"""Speedrun overlay v2 (build + FEM + CFD) over frames2/ -> AeroFrame35_speedrun_fem_cfd.mp4.
The 'personal best' splits are invented for the speedrun look; all engineering numbers are real.
"""
import os, sys, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from matplotlib import colormaps

D = "/home/claude/frame/speedrun"
TM = json.load(open(f"{D}/timing2.json")); META = json.load(open(f"{D}/vis.json"))
SEG, SUB, STOP, LAST, FPS = TM["segments"], TM["subs"], TM["stop"], TM["last"], TM["fps"]
W, H = 1280, 720
IF = "/usr/share/fonts/opentype/inter/"; MF = "/usr/share/fonts/truetype/dejavu/"
F = lambda p, s: ImageFont.truetype(p, s)
f_hdr, f_sub, f_row, f_rowb = F(IF + "Inter-Bold.otf", 17), F(IF + "Inter-Regular.otf", 12), F(IF + "Inter-Regular.otf", 14), F(IF + "Inter-SemiBold.otf", 14)
f_num, f_numb = F(MF + "DejaVuSansMono.ttf", 14), F(MF + "DejaVuSansMono-Bold.ttf", 14)
f_timer, f_timer_ms = F(MF + "DejaVuSansMono-Bold.ttf", 54), F(MF + "DejaVuSansMono-Bold.ttf", 32)
f_lab, f_cap, f_det = F(IF + "Inter-SemiBold.otf", 13), F(IF + "Inter-Bold.otf", 28), F(IF + "Inter-Regular.otf", 18)
f_big, f_mid, f_cb = F(IF + "Inter-Bold.otf", 44), F(IF + "Inter-SemiBold.otf", 20), F(IF + "Inter-Regular.otf", 13)
ORANGE, GREEN, RED, GOLD, BLUE = (255, 140, 40), (64, 214, 120), (240, 82, 82), (255, 205, 60), (110, 170, 255)
PANEL = (14, 17, 24, 218)

ends = [s["end"] for s in SEG]
PB = [e / FPS + round(math.sin(i * 1.9 + 0.4) * 0.45 + 0.12, 2) for i, e in enumerate(ends)]
GOLDS = {1, 5}

def tfmt(sec):
    m, s = divmod(max(sec, 0.0), 60)
    return f"{int(m)}:{s:05.2f}"

def gradient(cmap, w, h):
    g = (np.array(colormaps[cmap](np.linspace(0, 1, w)))[:, :3] * 255).astype(np.uint8)
    return Image.fromarray(np.repeat(g[None], h, 0), "RGB")
CB = {"stress": ("turbo", "surface von Mises stress", "0", f"{META['fem_smax']:.0f} MPa"),
      "mode": ("viridis", "relative amplitude", "0", "max"),
      "speed": ("turbo", "air speed", "0", "20 m/s")}
CBIMG = {k: gradient(v[0], 220, 12) for k, v in CB.items()}

def overlay(f):
    im = Image.open(f"{D}/frames2/f_{f:04d}.png").convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    t = min(f, STOP) / FPS
    cur = max([i for i, s in enumerate(SEG) if f >= s["start"]], default=-1)
    # ---- splits
    x0, y0, pw, rh = 16, 16, 330, 22
    ph = 58 + rh * len(SEG) + 10
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), 12, fill=PANEL)
    d.text((x0 + 14, y0 + 10), "AEROFRAME 3.5 · v3", font=f_hdr, fill=(255, 255, 255))
    d.text((x0 + 14, y0 + 32), "FreeCAD build + FEM + CFD · any%", font=f_sub, fill=(150, 156, 168))
    for i, s in enumerate(SEG):
        y = y0 + 56 + i * rh; done = f >= ends[i]
        if i == cur and not done:
            d.rectangle((x0 + 6, y - 2, x0 + pw - 6, y + rh - 4), fill=(48, 84, 160, 200))
        col = (255, 255, 255) if (done or i == cur) else (140, 146, 158)
        if s["kind"] in ("fem", "cfd") and not (done or i == cur):
            col = (120, 150, 200)
        d.text((x0 + 14, y), s["title"][:27], font=f_rowb if i == cur else f_row, fill=col)
        if done:
            st = ends[i] / FPS; dl = st - PB[i]
            d.text((x0 + pw - 140, y), f"{dl:+.2f}", font=f_num, fill=GOLD if i in GOLDS else (GREEN if dl < 0 else RED))
            d.text((x0 + pw - 66, y), tfmt(st), font=f_numb, fill=(255, 255, 255))
        elif i == cur:
            live = t - PB[i]
            if live > -1.0:
                d.text((x0 + pw - 140, y), f"{live:+.2f}", font=f_num, fill=GREEN if live < 0 else RED)
            d.text((x0 + pw - 66, y), tfmt(PB[i]), font=f_num, fill=(150, 156, 168))
        else:
            d.text((x0 + pw - 66, y), tfmt(PB[i]), font=f_num, fill=(110, 116, 128))
    # ---- timer
    ahead = cur < 0 or f >= STOP or t <= PB[cur]
    tc = GREEN if ahead else RED
    s_ = tfmt(t); main, ms = s_[:-3], s_[-3:]
    tw = d.textlength(main, font=f_timer) + d.textlength(ms, font=f_timer_ms); bx = W - 30 - tw
    d.rounded_rectangle((bx - 22, H - 104, W - 16, H - 22), 12, fill=PANEL)
    d.text((bx, H - 96), main, font=f_timer, fill=tc); d.text((bx + d.textlength(main, font=f_timer), H - 78), ms, font=f_timer_ms, fill=tc)
    # ---- caption (sub-phase captions win over the segment caption)
    sub = next((u for u in SUB if u["start"] <= f < u["end"]), None)
    lab = cap = det = None; cbk = None
    if sub:
        lab, cap, det, cbk = sub["label"], sub["caption"], sub["detail"], sub["colorbar"]
    elif 0 <= cur < len(SEG) and f < STOP:
        s = SEG[cur]
        if s["kind"] == "build":
            nb = [x for x in SEG if x["kind"] == "build"]; k = nb.index(s)
            lab, cap, det = f"STEP {k + 1}/{len(nb)}", s["title"], s["detail"]
        elif s["kind"] == "fit":
            lab, cap, det = "FIT CHECK", "Motors, boards, camera, GPS, 4S1P pack", "props out of view up to 40° uptilt"
        elif s["kind"] == "explode":
            lab, cap, det = "EXPLODED VIEW", "Chassis · lid · nose fairing", "3 PC prints, 58 g"
    if cap:
        cw = max(d.textlength(cap, font=f_cap), d.textlength(det, font=f_det), d.textlength(lab, font=f_lab)) + 48
        d.rounded_rectangle((16, H - 122, 16 + cw, H - 22), 12, fill=PANEL)
        d.text((38, H - 112), lab.upper(), font=f_lab, fill=BLUE if sub else ORANGE)
        d.text((38, H - 92), cap, font=f_cap, fill=(255, 255, 255)); d.text((38, H - 54), det, font=f_det, fill=(200, 205, 214))
    # ---- top-right: legend or colour bar
    if cbk:
        cm, title, lo, hi = CB[cbk]; lx = W - 270
        d.rounded_rectangle((lx, 16, W - 16, 88), 10, fill=PANEL)
        d.text((lx + 16, 24), title, font=f_rowb, fill=(255, 255, 255))
        ov.paste(CBIMG[cbk].convert("RGBA"), (lx + 16, 48))
        d.text((lx + 16, 64), lo, font=f_cb, fill=(200, 205, 214))
        d.text((lx + 236 - d.textlength(hi, font=f_cb), 64), hi, font=f_cb, fill=(200, 205, 214))
    elif 0 <= cur and SEG[cur]["kind"] == "build":
        lx = W - 230
        d.rounded_rectangle((lx, 16, W - 16, 74), 10, fill=(14, 17, 24, 190))
        d.rectangle((lx + 14, 28, lx + 28, 40), fill=(255, 219, 26)); d.text((lx + 36, 25), "material added", font=f_row, fill=(255, 255, 255))
        d.rectangle((lx + 14, 50, lx + 28, 62), fill=(242, 26, 41)); d.text((lx + 36, 47), "material removed", font=f_row, fill=(255, 255, 255))
    # ---- end card
    if f > STOP + 4:
        a = min(1.0, (f - STOP - 4) / 8)
        bx0, by0, bx1, by1 = 380, 130, W - 30, 520
        d.rounded_rectangle((bx0, by0, bx1, by1), 16, fill=(14, 17, 24, int(232 * a)))
        if a > 0.5:
            d.text((bx0 + 34, by0 + 26), "RUN COMPLETE", font=f_lab, fill=GREEN)
            d.text((bx0 + 34, by0 + 46), f"{tfmt(STOP / FPS)}  ·  new PB", font=f_big, fill=(255, 255, 255))
            lines = [("Printed parts", "chassis 42 g · lid 10 g · fairing 6 g = 58 g PC"),
                     ("FEM (CalculiX)", "crash peaks 22–26 MPa (PC yield ≈ 60) · first mode 120 Hz"),
                     ("CFD (OpenFOAM)", "cruise drag 0.55 N at 20° · hover loss 4 % (flat arms 12 %)"),
                     ("Camera", "props and frame out of view, 10–40° uptilt"),
                     ("Tools", "FreeCAD Python · gmsh + CalculiX · OpenFOAM · Blender")]
            for k, (h, v) in enumerate(lines):
                yy = by0 + 128 + k * 46
                d.text((bx0 + 34, yy), h.upper(), font=f_lab, fill=ORANGE); d.text((bx0 + 34, yy + 16), v, font=f_mid, fill=(235, 238, 244))
    return Image.alpha_composite(im, ov).convert("RGB")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        for f in map(int, sys.argv[2:]):
            overlay(f).save(f"{D}/test2/hud_{f:04d}.png")
        raise SystemExit
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
                          "-movflags", "+faststart", f"{D}/AeroFrame35_speedrun_fem_cfd.mp4"], stdin=subprocess.PIPE)
    for f in range(0, LAST + 1):
        p.stdin.write(overlay(f).tobytes())
    p.stdin.close(); p.wait(); print("VIDEO", (LAST + 1) / FPS, "s")
