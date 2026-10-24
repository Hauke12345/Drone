import bpy, sys, os, time
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath="/home/claude/frame/speedrun/frame_speedrun.blend")
sc = bpy.context.scene
out = os.environ.get("FRAMES_DIR", "/home/claude/frame/speedrun/frames")
os.makedirs(out, exist_ok=True)
if args and args[0] == "range":
    fl = range(int(args[1]), int(args[2]) + 1)
else:
    fl = [int(a) for a in args]
t = time.time()
for f in fl:
    sc.frame_set(f); sc.render.filepath = f"{out}/f_{f:04d}.png"; bpy.ops.render.render(write_still=True)
print("DONE", len(fl), "frames", round(time.time() - t, 1), "s")
