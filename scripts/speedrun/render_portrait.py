import bpy, sys, os, time, json
args = sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath="/home/claude/frame/speedrun/frame_speedrun2.blend")
sc = bpy.context.scene
TM = json.load(open("/home/claude/frame/speedrun/timing2.json"))
sc.render.resolution_x, sc.render.resolution_y = 720, 900
fl_ = bpy.data.objects.get("Plane")
if fl_: fl_.scale = (25, 25, 1)
cam = sc.camera; cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36; cam.data.lens = float(os.environ.get("LENS", "52"))
out = os.environ.get("FRAMES_DIR", "/home/claude/frame/speedrun/frames_p"); os.makedirs(out, exist_ok=True)
fl = [int(a) for a in open(args[1]).read().split()] if args and args[0] == "list" else [int(a) for a in args]
if os.environ.get("STRIDE"):
    k, n = map(int, os.environ["STRIDE"].split("/")); fl = [f for i, f in enumerate(fl) if i % n == k]
t = time.time()
for f in fl:
    p = f"{out}/f_{f:04d}.png"
    if os.path.exists(p) and not os.environ.get("FORCE"):
        continue
    sc.display.shading.color_type = "VERTEX" if any(a <= f <= b for a, b in TM["vertex"]) else "MATERIAL"
    sc.frame_set(f); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
print("DONE", len(fl), round(time.time() - t, 1))
