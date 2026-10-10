#!/usr/bin/env python3
"""Compare all native states with an independent original-MAT/SI oracle."""
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent
if not __debug__: raise RuntimeError('Run without -O/PYTHONOPTIMIZE')
actual=json.loads(subprocess.check_output([sys.argv[1]],text=True,timeout=30))
expected=json.loads((ROOT/'data/rate_reference_oracle.json').read_text())
worst=0.0

def vector(a,b):
    global worst
    assert len(a)==len(b)==60
    for x,y in zip(a,b):
        assert math.isfinite(x) and math.isfinite(y)
        worst=max(worst,abs(x-y))
        assert abs(x-y)<=1e-10+1e-11*abs(y), (x,y)
assert actual['dt_ms']==0.1
assert actual['snapshots'].keys()==expected['snapshots'].keys()
for key in actual['snapshots']: vector(actual['snapshots'][key],expected['snapshots'][key])
vector(actual['signed_initial_one_step'],expected['signed_initial_one_step']['expected_u'])
vector(actual['zero_input_after_40000_updates'],expected['zero_input_after_40000_updates'])
for key in ('-50','50'): vector(actual['turn_probes'][key],expected['turn_probes'][key]['expected_u'])
print(f'Native source drift vs independent SI oracle: max abs error {worst:.3g}; numeric tolerance, not bit identity')
