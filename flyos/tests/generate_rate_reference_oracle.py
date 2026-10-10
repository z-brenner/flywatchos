"""Independent SI-voltage Euler oracle fixtures, using original MAT categories.
No production repo imports. No source scripts executed. NumPy/SciPy for research only.
"""
if not __debug__: raise RuntimeError("Run without -O/PYTHONOPTIMIZE")
import argparse,json,hashlib,pathlib, numpy as np
from scipy.io import loadmat
ROOT=pathlib.Path(__file__).resolve().parent;SRC=ROOT.parent/'sim/data/pisokas2020'
mat=SRC/'connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat'
assert hashlib.sha256(mat.read_bytes()).hexdigest()=='abfdcb2918e3637e41d4ba7b7438e512f545dac6553ce89d5cfddb49de044b12'
m=loadmat(mat)['con_matrix'][:60,:60]
strengths={1:6.07203896674184,1.1:47.9173822984772,-1:-35.6772759590409,-1.1:-19.3358579258735,3:99.9680554605268}
w=np.zeros((60,60))
for label,strength in strengths.items():w[m==label]=strength
angles=np.array([0,45,90,135,180,225,270,315,0]*2)
def forcing(angle,rate,turn=0):
 d=np.minimum(abs(angles-angle),360-abs(angles-angle));x=np.zeros(60);x[34:52]=np.maximum(0,1-d/90)*rate
 if turn>0:x[:8]=turn
 elif turn<0:x[8:16]=-turn
 return x

def update(v,drive):
 old=v.copy();i_syn=w @ (3e-10*np.tanh(100*old));i_ext=3e-10*drive
 return old+.0001*((-old/1e6+i_syn+i_ext)/2e-8)

probe={'description':'SI-form Euler from independently read original MAT; snapshots after update count; states u=100V. Synthetic triangular cue90deg,max200 applied0<=step<7500;thenoff. No Gaussian current noise/Bernoulli inputs/source preprocessing.','source_commit':'dfb95dfeaad0da2df0f7f687846d4df44079a483','source_mat_sha256':hashlib.sha256(mat.read_bytes()).hexdigest(),'dt_seconds':.0001,'C_F':2e-8,'R_ohm':1e6,'V0_volts':0,'current_scale_A':3e-10,'source_core_file_sha256':hashlib.sha256((SRC/'flyLI2.m').read_bytes()).hexdigest(),'snapshots':{}}
v=np.zeros(60);on=forcing(90,200);off=np.zeros(60)
for k in range(40000):
 v=update(v,on if k<7500 else off)
 if k+1 in [1,2,10,100,1000,7500,7501,10000,20000,40000]:probe['snapshots'][str(k+1)]=(100*v).tolist()
initial_u=np.linspace(-.3,.3,60);one_drive=forcing(225,80,-30)
probe['signed_initial_one_step']={'initial_u':initial_u.tolist(),'input':{'cue_degrees':225,'cue_rate_equivalent':80,'turn_rate_equivalent':-30},'rate_vector':one_drive.tolist(),'expected_u':(100*update(initial_u/100,one_drive)).tolist()}
probe['zero_input_after_40000_updates']=[0.0]*60
probe['turn_probes']={}
for turn in [50,-50]:
    v=np.zeros(60)
    for k in range(40000):
        drive=on.copy() if k<7500 else off.copy()
        if 10000<=k<20000:
            if turn>0:drive[:8]=turn
            else:drive[8:16]=-turn
        v=update(v,drive)
    probe['turn_probes'][str(turn)]={'description':'90deg200cue0to750ms; signed turn rate-equivalent input1000to2000ms; finalstate4000ms','expected_u':(100*v).tolist()}
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
parser.add_argument('--output',type=pathlib.Path,default=ROOT/'data/rate_reference_oracle.json')
args=parser.parse_args()
if args.check:
    previous=json.loads(args.output.read_text())
    def compare(a,b,path='root'):
        if isinstance(a,(float,int)):
            assert abs(a-b)<=1e-11, (path,a,b)
        elif isinstance(a,dict):
            assert a.keys()==b.keys(), path
            for key in a: compare(a[key],b[key],path+'.'+key)
        elif isinstance(a,list):
            assert len(a)==len(b), path
            for i,(x,y) in enumerate(zip(a,b)): compare(x,y,path+'.'+str(i))
        else: assert a==b,path
    compare(probe,previous)
    print('Independent original-MAT/SI-equation reference fixtures verified')
else:
    args.output.write_text(json.dumps(probe,indent=2)+'\n',encoding='utf-8',newline='\n')
