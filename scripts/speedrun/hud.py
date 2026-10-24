"""LiveSplit-style speedrun overlay for the AeroFrame build frames -> MP4.

reads frames/f_####.png + timing.json, pipes composited frames to ffmpeg.
The 'personal best' it races against is invented, for the speedrun look only.
"""
import os, json, math, subprocess
from PIL import Image, ImageDraw, ImageFont

D = "/home/claude/frame/speedrun"
T = json.load(open(f"{D}/timing.json"))
W, H, FPS = 1280, 720, 24
IF = "/usr/share/fonts/opentype/inter/"; MF = "/usr/share/fonts/truetype/dejavu/"
F = lambda p, s: ImageFont.truetype(p, s)
f_hdr, f_sub, f_row, f_rowb = F(IF + "Inter-Bold.otf", 17), F(IF + "Inter-Regular.otf", 12), F(IF + "Inter-Regular.otf", 14), F(IF + "Inter-SemiBold.otf", 14)
f_num = F(MF + "DejaVuSansMono.ttf", 14); f_numb = F(MF + "DejaVuSansMono-Bold.ttf", 14)
f_timer, f_timer_ms = F(MF + "DejaVuSansMono-Bold.ttf", 54), F(MF + "DejaVuSansMono-Bold.ttf", 32)
f_lab, f_cap, f_det = F(IF + "Inter-SemiBold.otf", 13), F(IF + "Inter-Bold.otf", 28), F(IF + "Inter-Regular.otf", 18)
f_big, f_mid, f_small = F(IF + "Inter-Bold.otf", 44), F(IF + "Inter-SemiBold.otf", 20), F(IF + "Inter-Regular.otf", 16)
ORANGE, GREEN, RED, GOLD = (255, 140, 40), (64, 214, 120), (240, 82, 82), (255, 205, 60)

names = T["titles"] + ["Fit check", "Exploded view"]
starts = T["starts"] + [T["fit"], T["explode"]]
ends = starts[1:] + [T["end"]]
ends[len(T["titles"]) - 1] = T["fit"]          # last build split ends when the fit check starts
STOP = T["end"]
PB = [e / FPS + round(math.sin(i * 1.9 + 0.4) * 0.45 + 0.12, 2) for i, e in enumerate(ends)]   # invented PB
GOLDS = {1, 4}                                                                                   # "best segments"

def tfmt(sec):
    m, s = divmod(max(sec, 0.0), 60)
    return f"{int(m)}:{s:05.2f}"

def overlay(f):
    im = Image.open(f"{D}/frames/f_{f:04d}.png").convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    t = min(f, STOP) / FPS
    cur = max([i for i, s in enumerate(starts) if f >= s], default=-1)
    # ---- splits panel
    x0, y0, pw, rh = 16, 16, 330, 22
    ph = 58 + rh * len(names) + 12
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), 12, fill=(14, 17, 24, 218))
    d.text((x0 + 14, y0 + 10), "AEROFRAME 3.5 · v3", font=f_hdr, fill=(255, 255, 255))
    d.text((x0 + 14, y0 + 32), "FreeCAD build · any% · PC frame", font=f_sub, fill=(150, 156, 168))
    for i, n in enumerate(names):
        y = y0 + 56 + i * rh
        done = f >= ends[i]
        if i == cur and not done:
            d.rectangle((x0 + 6, y - 2, x0 + pw - 6, y + rh - 4), fill=(48, 84, 160, 200))
        col = (255, 255, 255) if (done or i == cur) else (140, 146, 158)
        d.text((x0 + 14, y), n[:26], font=f_rowb if i == cur else f_row, fill=col)
        if done:
            st = ends[i] / FPS; delta = st - PB[i]
            dc = GOLD if i in GOLDS else (GREEN if delta < 0 else RED)
            d.text((x0 + pw - 140, y), f"{delta:+.2f}", font=f_num, fill=dc)
            d.text((x0 + pw - 66, y), tfmt(st), font=f_numb, fill=(255, 255, 255))
        elif i == cur:
            live = t - PB[i]
            if live > -1.0:
                d.text((x0 + pw - 140, y), f"{live:+.2f}", font=f_num, fill=GREEN if live < 0 else RED)
            d.text((x0 + pw - 66, y), tfmt(PB[i]), font=f_num, fill=(150, 156, 168))
        else:
            d.text((x0 + pw - 66, y), tfmt(PB[i]), font=f_num, fill=(110, 116, 128))
    # ---- timer
    ahead = t <= PB[max(cur, 0)] if cur < len(names) else True
    tc = GREEN if (f >= STOP or ahead) else RED
    s = tfmt(t); main, ms = s[:-3], s[-3:]
    tw = d.textlength(main, font=f_timer) + d.textlength(ms, font=f_timer_ms)
    bx = W - 30 - tw
    d.rounded_rectangle((bx - 22, H - 104, W - 16, H - 22), 12, fill=(14, 17, 24, 218))
    d.text((bx, H - 96), main, font=f_timer, fill=tc)
    d.text((bx + d.textlength(main, font=f_timer), H - 78), ms, font=f_timer_ms, fill=tc)
    # ---- caption
    if 0 <= cur < len(names) and f < STOP:
        if cur < len(T["titles"]):
            lab = f"STEP {cur + 1}/{len(T['titles'])}"; cap = T["titles"][cur]; det = T["details"][cur]
        elif cur == len(T["titles"]):
            lab = "FIT CHECK"; cap = "Motors, props, boards, camera, GPS, 4S1P pack"; det = "props out of view up to 40° uptilt"
        else:
            lab = "EXPLODED VIEW"; cap = "Chassis · lid · nose fairing"; det = "3 PC prints, 58 g"
        cw = max(d.textlength(cap, font=f_cap), d.textlength(det, font=f_det)) + 48
        d.rounded_rectangle((16, H - 122, 16 + cw, H - 22), 12, fill=(14, 17, 24, 218))
        d.text((38, H - 112), lab, font=f_lab, fill=ORANGE)
        d.text((38, H - 92), cap, font=f_cap, fill=(255, 255, 255))
        d.text((38, H - 54), det, font=f_det, fill=(200, 205, 214))
    # ---- legend (top right) while building
    if f < T["fit"]:
        lx = W - 230
        d.rounded_rectangle((lx, 16, W - 16, 74), 10, fill=(14, 17, 24, 190))
        d.rectangle((lx + 14, 28, lx + 28, 40), fill=(255, 219, 26)); d.text((lx + 36, 25), "material added", font=f_row, fill=(255, 255, 255))
        d.rectangle((lx + 14, 50, lx + 28, 62), fill=(242, 26, 41)); d.text((lx + 36, 47), "material removed", font=f_row, fill=(255, 255, 255))
    # ---- end card
    if f > STOP + 6:
        a = min(1.0, (f - STOP - 6) / 10)
        bx0, by0, bx1, by1 = 380, 130, W - 30, 520
        d.rounded_rectangle((bx0, by0, bx1, by1), 16, fill=(14, 17, 24, int(232 * a)))
        if a > 0.5:
            d.text((bx0 + 34, by0 + 26), "RUN COMPLETE", font=f_lab, fill=GREEN)
            d.text((bx0 + 34, by0 + 46), f"{tfmt(STOP / FPS)}  ·  new PB", font=f_big, fill=(255, 255, 255))
            lines = [("Printed parts", "chassis 42 g · lid 10 g · fairing 6 g = 58 g PC"),
                     ("Camera", "props and frame out of view, 10–40° uptilt"),
                     ("FEM (CalculiX)", "crash peaks 22–26 MPa · torsion 226 Hz"),
                     ("CFD (OpenFOAM)", "0.46 N at 15 m/s level · hover download 4 %"),
                     ("Tools", "FreeCAD Python · gmsh + CalculiX · OpenFOAM · Blender")]
            for k, (h, v) in enumerate(lines):
                yy = by0 + 128 + k * 46
                d.text((bx0 + 34, yy), h.upper(), font=f_lab, fill=ORANGE)
                d.text((bx0 + 34, yy + 16), v, font=f_mid, fill=(235, 238, 244))
    return Image.alpha_composite(im, ov).convert("RGB")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        for f in map(int, sys.argv[2:]):
            overlay(f).save(f"{D}/test/hud_{f:04d}.png")
        raise SystemExit
    N = T["last"]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
                          "-movflags", "+faststart", f"{D}/AeroFrame35_freecad_speedrun.mp4"], stdin=subprocess.PIPE)
    for f in range(0, N + 1):
        p.stdin.write(overlay(f).tobytes())
    p.stdin.close(); p.wait(); print("VIDEO done", (N + 1) / FPS, "s")
