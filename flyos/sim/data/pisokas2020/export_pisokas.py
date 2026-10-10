"""Derive portable, explicit edges from the pinned published model artifact.
Run with scipy installed. No network access or source-code execution required.
"""
if not __debug__:
    raise RuntimeError("Source verification requires Python without -O/PYTHONOPTIMIZE")

import csv, hashlib, json
from pathlib import Path
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parent
NAME='connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat'
EXPECTED='abfdcb2918e3637e41d4ba7b7438e512f545dac6553ce89d5cfddb49de044b12'
assert hashlib.sha256((ROOT/NAME).read_bytes()).hexdigest()==EXPECTED
m=loadmat(ROOT/NAME)['con_matrix']
weights={1.0:6.07203896674184,1.1:47.9173822984772,-1.0:-35.6772759590409,-1.1:-19.3358579258735,3.0:99.9680554605268}
assert m.shape==(62,62)
assert (m[60:,:]==0).all() and (m[:,60:]==0).all()
nodes=[]
for i in range(60):
    group,base,count=('P-EN',0,16) if i<16 else ('P-EG',16,18) if i<34 else ('E-PG',34,18) if i<52 else ('Delta7',52,8)
    n={'index':i,'class':group,'class_index':i-base,'unit_kind':'representative model population'}
    if group in ['P-EG','E-PG']:
        n.update(half='A' if i-base<9 else 'B',column_index=(i-base)%9)
    if group=='P-EN':n.update(half='A' if i<8 else 'B',column_index=i%8)
    if group=='E-PG':n['cue_angle_degrees']=(((i-base)%9)%8)*45
    nodes.append(n)
edges=[]
for target in range(60):
    for source in range(60):
        v=float(m[target,source])
        if v:
            assert v in weights
            edges.append({'source':source,'target':target,'category_label':v,'published_model_strength':weights[v]})
assert len(edges)==326
with (ROOT/'pisokas2020_cx60_edges.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(edges[0]));w.writeheader();w.writerows(edges)
(ROOT/'pisokas2020_cx60_nodes.json').write_text(json.dumps(nodes,indent=2)+'\n')
metadata={
 'name':'Pisokas2020 Drosophila heading circuit: 60 connected representative model units',
 'paper':'https://doi.org/10.7554/eLife.53985',
 'repository':'https://github.com/johnpi/eLife_Pisokas_Heinze_Webb_2019',
 'source_commit':'dfb95dfeaad0da2df0f7f687846d4df44079a483',
 'source_file':'Exp_Recurrent_PB_EB/'+NAME,
 'source_sha256':EXPECTED,
 'source_license':'MIT; see LICENSE. Copyright (c) 2020 Kyobi S. Kakaria, Benjamin L. de Bivort and Ioannis Pisokas',
 'upstream_shape':[62,62], 'active_units':60,'directed_edges':326,
 'orientation':'upstream matrix[target,source]; source driver transposes before calling simulator',
 'strength_evidence':'collect_stats_long_run.m lines395-433; these are fitted MODEL strengths, not synapse counts',
 'category_strengths':{str(k):v for k,v in weights.items()},
 'class_counts':{'P-EN':16,'P-EG':18,'E-PG':18,'Delta7':8},
 'derivation':['Verify exact MAT SHA256','Read con_matrix','Discard only all-zero rows/columns60,61','Emit each nonzero as source=column,target=row','Map category labels through published parameter set','No pruning, random replacement, or invented neurons'],
 'limitations':['Not an EM-derived individual-neuron connectome','Representative model units collapse multiple anatomical cells','Anatomical overlap motivated wiring; connection strengths were optimized','No measured fly membrane dynamics or real watch-sensor calibration','No whole-brain, consciousness, organism or biological-equivalence claim','Deterministic fixed-point rate adaptation is a new dynamics model unless equivalence is demonstrated'],
 'cue_mapping':'EPG34..42 and43..51 each use [0,45,90,135,180,225,270,315,0] degrees from upstream cue code; model-relative, not compass calibrated',
 'pen_half_convention':'A=0..7;B=8..15; upstream comments disagree on hemisphere naming; establish rotation sign empirically',
 'files':{}
}
for fn in ['pisokas2020_cx60_edges.csv','pisokas2020_cx60_nodes.json',NAME,'collect_stats_long_run.m','PBexperimentModified.m','flyLI2.m','flyLIF2.m','LICENSE']:
 b=(ROOT/fn).read_bytes();metadata['files'][fn]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
(ROOT/'pisokas2020_cx60_provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'active_units':60,'edges':len(edges),'files':metadata['files']},indent=2))
