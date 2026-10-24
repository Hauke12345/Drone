import sys, os, json, numpy as np
sys.path.insert(0, os.getcwd())
import fov
from render import load_stl
D='out/parts/'
P=json.load(open('out/report.json'))['params']
piv=np.array([P['cam_pivot'][0],0,P['cam_pivot'][1]])
def verts(n): 
    v=load_stl(D+n).reshape(-1,3); return np.unique(np.round(v,2),axis=0)
groups={
 'props+motors': np.vstack([fov.disk_points(*(verts(f'ref_Prop{i}.stl').mean(0)[:2]), z, 88.9/2) for i in range(4) for z in (34.5,36.0,37.5)] + [verts(f'ref_Motor{i}.stl') for i in range(4)]),
 'battery 4S1P 18650': verts('ref_Battery_4S1P_18650.stl'),
 'battery LiPo': verts('ref_Battery_LiPo_tabless.stl'),
 'GPS': verts('ref_GPS.stl'),
 'frame (chassis+lid+hood)': np.vstack([verts('Chassis.stl'),verts('Lid.stl')] + ([verts('Hood.stl')] if os.path.exists(D+'Hood.stl') else [])),
}
# props flex: also check 2 mm lower tips
res={}
print('uptilt  ' + '  '.join(f'{k:>20s}' for k in groups))
for t in range(10,41,5):
    L=fov.lens_position(piv,t,9.0)
    row=[]
    for k,Pts in groups.items():
        # ignore points belonging to the camera bay right next to the lens (< 9 mm): lens hood region
        d=np.linalg.norm(Pts-L,axis=1); Q=Pts[d>float(os.environ.get("EXCL","9"))]
        m=fov.margin(Q,L,t); row.append(float(m.min()))
    res[t]=dict(zip(groups,row))
    print(f'{t:5d}   '+'  '.join(f'{v:20.3f}' for v in row))
json.dump(res,open('out/fov_margins.json','w'),indent=1)
