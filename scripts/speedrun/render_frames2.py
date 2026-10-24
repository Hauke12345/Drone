import bpy, sys, os, time, json
args = sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath="/home/claude/frame/speedrun/frame_speedrun2.blend")
sc = bpy.context.scene
TM = json.load(open("/home/claude/frame/speedrun/timing2.json"))
out = os.environ.get("FRAMES_DIR", "/home/claude/frame/speedrun/frames2"); os.makedirs(out, exist_ok=True)
fl = range(int(args[1]), int(args[2]) + 1) if args and args[0] == "range" else [int(a) for a in args]
if os.environ.get("STRIDE"):
    k, n = map(int, os.environ["STRIDE"].split("/")); fl = [f for f in fl if f % n == k]
t = time.time()
for f in fl:
    p = f"{out}/f_{f:04d}.png"
    if os.path.exists(p) and not os.environ.get("FORCE"):
        continue
    vtx = any(a <= f <= b for a, b in TM["vertex"])
    sc.display.shading.color_type = "VERTEX" if vtx else "MATERIAL"
    sc.frame_set(f); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
print("DONE", len(fl), "frames", round(time.time() - t, 1), "s")
