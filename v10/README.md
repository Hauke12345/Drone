# AeroFrame 3.5 — v10

Electronics re-layout of the v9 frame, so the stock 1404 motor wires reach the board.

![top view v9 vs v10](media/AeroFrame35_v10_layout_top.png)

## What changed (chassis only)
- **AIO (FC + ESC) in the centre** (x = 0, 25.5 and 20 mm patterns), motor pads at the corners: motor wire runs 79–82 mm → **64.5 mm** on all four arms
- **VTX** on its own mount at the rear, x = −27 mm, next to the antenna exit
- **Turtle V2 board** moved to x = +31 mm, clear of the 32 mm AIO
- **USB-C slot** moved to x = −8 mm
- Lid and hood are unchanged from v9

## Centre of mass (estimate)
~209 g all-up with a 4S 650 mAh LiPo. With the battery in the v9 position the CoM sits ~6.6 mm ahead of the motor centre; sliding the battery **8 mm back** brings it to ~3.6 mm (front/rear motor load ≈ 53/47 %).

![CoM](media/AeroFrame35_v10_com_side.png)

## Files
- `cad/AeroFrame35_v10_chassis.stl`, `_lid.stl`, `_hood.stl` — print files (mm)
- `cad/AeroFrame35.step`, `cad/AeroFrame35.FCStd` — full model; `reference_parts.step` — placeholder electronics
- `scripts/build_frame_v10.py` — FreeCAD build script (`FRAME_OUT=<dir> freecadcmd build_frame_v10.py`)

Printed in grey PETG on a Bambu. Board fit was checked against the CAD; FEM and CFD were not re-run for v10 (changes are inside the pod).
