#!/usr/bin/env python3
"""Independent SI/original-MAT timestep refinement, including input transitions.

The C reference has fixed 100 us dt. Finer timesteps live only in this oracle.
Convergence is numerical evidence for this specified input, not biology.
"""
if not __debug__: raise RuntimeError('Run without -O/PYTHONOPTIMIZE')
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1]
MAT=ROOT/'sim/data/pisokas2020/connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat'
assert hashlib.sha256(MAT.read_bytes()).hexdigest()=='abfdcb2918e3637e41d4ba7b7438e512f545dac6553ce89d5cfddb49de044b12'
categories=loadmat(MAT)['con_matrix'][:60,:60]
weights=np.zeros((60,60))
for category,value in {1:6.07203896674184,1.1:47.9173822984772,-1:-35.6772759590409,
                       -1.1:-19.3358579258735,3:99.9680554605268}.items():
    weights[categories==category]=value
angles=np.array([0,45,90,135,180,225,270,315,0]*2)
distance=np.minimum(abs(angles-90),360-abs(angles-90))
cue=np.zeros(60);cue[34:52]=np.maximum(0,1-distance/90)*200

def integrate(dt):
    voltage=np.zeros(60);result=[voltage.copy()]
    sample_every=round(.005/dt);cue_updates=round(.75/dt)
    for k in range(round(4/dt)):
        external=3e-10*cue if k<cue_updates else 0
        current=weights@(3e-10*np.tanh(100*voltage))+external
        voltage=voltage+dt*((-voltage/1e6+current)/2e-8)
        if (k+1)%sample_every==0:result.append(100*voltage.copy())
    return np.array(result)
coarse,middle,fine=(integrate(dt) for dt in (.0001,.00005,.000025))
assert coarse.shape==middle.shape==fine.shape==(801,60)
assert np.isfinite(coarse).all() and np.isfinite(middle).all() and np.isfinite(fine).all()
first=np.max(abs(coarse-middle));second=np.max(abs(middle-fine))
assert first>1e-4 and .4*first<second<.6*first,(first,second)
# Explicit post-cue-loss transient, separate from the settled 4-second endpoint.
loss_first=np.max(abs(coarse[150:201]-middle[150:201]))
loss_second=np.max(abs(middle[150:201]-fine[150:201]))
assert loss_first>1e-4 and .4*loss_first<loss_second<.6*loss_first,(loss_first,loss_second)
fixture=json.loads((ROOT/'tests/data/rate_reference_oracle.json').read_text())
for updates in (100,1000,7500,10000,20000,40000):
    assert np.max(abs(coarse[updates//50]-fixture['snapshots'][str(updates)]))<1e-11
print(f'SI/original-MAT refinement at801 common samples: max100→50us={first:.9g}, '
      f'50→25us={second:.9g}; post-cue-loss={loss_first:.9g}/{loss_second:.9g}')
