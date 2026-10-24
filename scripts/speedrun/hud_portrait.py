"""4:5 portrait speedrun overlay for the LinkedIn GIF (frames_p/ -> hud_p/)."""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, "/home/claude/frame/speedrun")
import hud2 as H
from hud2 import F, IF, MF, SEG, SUB, STOP, FPS, PB, GOLDS, ends, tfmt, CB, CBIMG, ORANGE, GREEN, RED, GOLD, BLUE, PANEL

W, HH = 720, 900
D = "/home/claude/frame/speedrun"
f_t, f_s = F(IF + "Inter-Bold.otf", 23), F(IF + "Inter-Regular.otf", 14)
f_split, f_d = F(IF + "Inter-SemiBold.otf", 18), F(MF + "DejaVuSansMono-Bold.ttf", 16)
f_tim, f_tims = F(MF + "DejaVuSansMono-Bold.ttf", 46), F(MF + "DejaVuSansMono-Bold.ttf", 28)
f_lab, f_cap, f_det, f_small = F(IF + "Inter-SemiBold.otf", 14), F(IF + "Inter-Bold.otf", 27), F(IF + "Inter-Regular.otf", 17), F(IF + "Inter-Regular.otf", 14)
f_big, f_mid = F(IF + "Inter-Bold.otf", 40), F(IF + "Inter-SemiBold.otf", 18)
os.makedirs(f"{D}/hud_p", exist_ok=True)
T0, T1 = SEG[0]["start"], SEG[-1]["end"]

def fit(d, txt, font, maxw):
    while d.textlength(txt, font=font) > maxw and len(txt) > 4:
        txt = txt[:-2].rstrip() + "…" if not txt.endswith("…") else txt[:-3].rstrip() + "…"
    return txt

def overlay(f):
    im = Image.open(f"{D}/frames_p/f_{f:04d}.png").convert("RGBA")
    ov = Image.new("RGBA", (W, HH), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    t = min(f, STOP) / FPS
    cur = max([i for i, s in enumerate(SEG) if f >= s["start"]], default=-1)
    # ---------------- top bar
    d.rounded_rectangle((12, 12, W - 12, 152), 14, fill=PANEL)
    d.text((28, 22), "AEROFRAME 3.5 · v3", font=f_t, fill=(255, 255, 255))
    d.text((28, 52), "FreeCAD + FEM + CFD speedrun", font=f_s, fill=(150, 156, 168))
    ahead = cur < 0 or f >= STOP or t <= PB[cur]
    s_ = tfmt(t); main, ms = s_[:-3], s_[-3:]
    tw = d.textlength(main, font=f_tim) + d.textlength(ms, font=f_tims)
    x = W - 28 - tw
    d.text((x, 18), main, font=f_tim, fill=GREEN if ahead else RED)
    d.text((x + d.textlength(main, font=f_tim), 34), ms, font=f_tims, fill=GREEN if ahead else RED)
    if 0 <= cur < len(SEG):
        s = SEG[cur]; done = f >= ends[cur]
        name = f"{cur + 1}/{len(SEG)}  {s['title']}"
        d.text((28, 86), fit(d, name, f_split, 520), font=f_split, fill=(255, 255, 255))
        dl = (ends[cur] / FPS if done else t) - PB[cur]
        if done or dl > -1.0:
            col = GOLD if (done and cur in GOLDS) else (GREEN if dl < 0 else RED)
            txt = f"{dl:+.2f}"; d.text((W - 28 - d.textlength(txt, font=f_d), 88), txt, font=f_d, fill=col)
    # progress strip: one chip per split, width ~ duration
    x0, x1, y0 = 28, W - 28, 122
    for i, s in enumerate(SEG):
        a = x0 + (x1 - x0) * (s["start"] - T0) / (T1 - T0); b = x0 + (x1 - x0) * (s["end"] - T0) / (T1 - T0)
        if f >= ends[i]:
            dl = ends[i] / FPS - PB[i]; col = GOLD if i in GOLDS else (GREEN if dl < 0 else RED)
        elif i == cur:
            col = (90, 140, 230)
        else:
            col = (70, 76, 90) if s["kind"] not in ("fem", "cfd") else (60, 80, 120)
        d.rounded_rectangle((a + 1, y0, b - 1, y0 + 14), 4, fill=col)
        if i == cur and f < ends[i]:
            p = (f - s["start"]) / max(s["end"] - s["start"], 1)
            d.rounded_rectangle((a + 1, y0, a + 1 + (b - a - 2) * p, y0 + 14), 4, fill=(150, 190, 255))
    # ---------------- bottom bar
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
            lab, cap, det = "FIT CHECK", "Motors, boards, camera, GPS, pack", "props out of view up to 40° uptilt"
        elif s["kind"] == "explode":
            lab, cap, det = "EXPLODED VIEW", "Chassis · lid · nose fairing", "3 PC prints, 58 g"
    if cap and f < STOP + 4:
        y = HH - 12 - 150
        d.rounded_rectangle((12, y, W - 12, HH - 12), 14, fill=PANEL)
        d.text((28, y + 14), lab.upper(), font=f_lab, fill=BLUE if sub else ORANGE)
        d.text((28, y + 34), fit(d, cap, f_cap, W - 56), font=f_cap, fill=(255, 255, 255))
        d.text((28, y + 72), fit(d, det, f_det, W - 56), font=f_det, fill=(200, 205, 214))
        yb = y + 108
        if cbk:
            cm, title, lo, hi = CB[cbk]
            d.text((28, yb + 2), title, font=f_small, fill=(200, 205, 214))
            gx = 28 + int(d.textlength(title, font=f_small)) + 14
            g = CBIMG[cbk].resize((260, 12)); ov.paste(g.convert("RGBA"), (gx, yb + 6))
            d.text((gx - 12 + 0, yb + 2), "", font=f_small)
            d.text((gx + 268, yb + 2), f"{lo} – {hi}", font=f_small, fill=(200, 205, 214))
        elif SEG[cur]["kind"] == "build":
            d.rectangle((28, yb + 5, 42, yb + 19), fill=(255, 219, 26)); d.text((50, yb + 2), "material added", font=f_small, fill=(230, 232, 238))
            d.rectangle((200, yb + 5, 214, yb + 19), fill=(242, 26, 41)); d.text((222, yb + 2), "material removed", font=f_small, fill=(230, 232, 238))
    # ---------------- end card
    if f > STOP + 4:
        a = min(1.0, (f - STOP - 4) / 8)
        bx0, by0, bx1, by1 = 28, 200, W - 28, 800
        d.rounded_rectangle((bx0, by0, bx1, by1), 16, fill=(14, 17, 24, int(236 * a)))
        if a > 0.5:
            d.text((bx0 + 30, by0 + 28), "RUN COMPLETE", font=f_lab, fill=GREEN)
            d.text((bx0 + 30, by0 + 50), f"{tfmt(STOP / FPS)} · new PB", font=f_big, fill=(255, 255, 255))
            lines = [("Printed parts", ["chassis 42 g · lid 10 g · fairing 6 g", "= 58 g of PC"]),
                     ("FEM (CalculiX)", ["crash peaks 22–26 MPa (PC yield ≈ 60)", "first vibration mode 120 Hz"]),
                     ("CFD (OpenFOAM)", ["cruise drag 0.55 N at 20°, 15 m/s", "hover loss 4 % (flat arms 12 %)"]),
                     ("Camera", ["props and frame out of view, 10–40°"]),
                     ("Tools", ["FreeCAD Python · gmsh + CalculiX", "OpenFOAM · Blender"])]
            yy = by0 + 120
            for h, vs in lines:
                d.text((bx0 + 30, yy), h.upper(), font=f_lab, fill=ORANGE); yy += 20
                for v in vs:
                    d.text((bx0 + 30, yy), v, font=f_mid, fill=(235, 238, 244)); yy += 25
                yy += 14
    return Image.alpha_composite(im, ov).convert("RGB")

if __name__ == "__main__":
    frames = [int(x) for x in open(f"{D}/gif_frames.txt").read().split()]
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        for f in map(int, sys.argv[2:]):
            overlay(f).save(f"{D}/tp/hud_{f:04d}.png")
        raise SystemExit
    for k, f in enumerate(frames):
        overlay(f).save(f"{D}/hud_p/g_{k:04d}.png")
    print("HUD frames", len(frames))
