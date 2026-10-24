import json, numpy as np, sys
sys.path.insert(0,'.')
from frd_tools import read_frd, von_mises
(ids, X), blocks = read_frd(__import__('os').environ.get('BASE','out')+'/fem_static/static.frd')
idx = {n:i for i,n in enumerate(ids)}
cases = json.load(open(__import__('os').environ.get('BASE','out')+'/fem_static/cases.json'))['cases']
disp = [b for b in blocks if b[0]=='DISP']; strs = [b for b in blocks if b[0]=='STRESS']
RM=77.5
def pad(a):
    c=np.array([RM*np.cos(np.radians(a)),RM*np.sin(np.radians(a))])
    return (np.abs(X[:,2]-22)<0.05)&(np.hypot(X[:,0]-c[0],X[:,1]-c[1])<9.6)
fixed=(np.abs(X[:,2]-28.6)<0.05)&(X[:,0]>-35)&(X[:,0]<31)&(np.abs(X[:,1])<18.5)
near_bc=np.zeros(len(X),bool)
# exclude 2 mm around the fixed footprint edge and the loaded pad tops (load/BC singularities)
from numpy.linalg import norm
res={}
for k,name in enumerate(cases):
    U=np.zeros((len(X),3)); U[[idx[n] for n in disp[k][1]]]=disp[k][2][:,:3]
    S=np.zeros((len(X),6)); S[[idx[n] for n in strs[k][1]]]=strs[k][2]
    vm=von_mises(S)
    excl=(X[:,2]>28.0)&(X[:,0]>-37)&(X[:,0]<33)&(np.abs(X[:,1])<20.5)   # lid area under the battery (BC)
    for a in (45,135,225,315): excl|=pad(a)
    v=vm[~excl]; Xv=X[~excl]
    i=np.argmax(v)
    out=dict(max_vm=float(v.max()), p999_vm=float(np.percentile(v,99.9)), max_at=Xv[i].round(1).tolist())
    for a,nm in ((45,'FL'),(135,'RL'),(225,'RR'),(315,'FR')):
        u=U[pad(a)].mean(0); out['disp_'+nm]=u.round(3).tolist()
    # top stress locations
    top=np.argsort(v)[-200:]
    out['hot_x_range']=[float(Xv[top,0].min()),float(Xv[top,0].max())]
    res[name]=out
    print(name, json.dumps(out))
json.dump(res,open(__import__('os').environ.get('BASE','out')+'/fem_static/results_fixed.json','w'),indent=1)
