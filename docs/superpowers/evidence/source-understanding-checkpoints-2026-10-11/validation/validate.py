import json,sys
from pathlib import Path
import numpy as np
obs=json.loads(Path('build/validation-activity-2026-10-11/observations.json').read_text())
rows={}
for p in Path(sys.argv[1]).glob('results/*.json'):
    r=json.loads(p.read_text());rows[r['name']]=r
pairs=[(n,rows[n]['approximate_mood'],o) for n,o in obs.items() if n in rows and rows[n]['status']=='computed' and o['status']=='observed']
rank=lambda a:np.argsort(np.argsort(np.array(a)))
sp=lambda a,b:float(np.corrcoef(rank(a),rank(b))[0,1])
flow=np.array([o['mean_flow_screen_widths_per_s'] for _,_,o in pairs]);diff=np.array([o['mean_abs_frame_difference'] for _,_,o in pairs]);jumps=np.array([o['global_brightness_jumps_per_10s'] for _,_,o in pairs])
observed=flow/np.median(flow)+diff/np.median(diff)+np.minimum(jumps,60)/20
est=[m['activity_estimate'] for _,m,_ in pairs]
print('n',len(pairs),'spearman est~observed %.2f est~flow %.2f est~diff %.2f est~jumps %.2f'%(sp(est,observed),sp(est,flow),sp(est,diff),sp(est,jumps)))
conf=[i for i,(_,m,_) in enumerate(pairs) if m['confidence']!='low']
if len(conf)>3:print('confident n',len(conf),'spearman %.2f'%sp([est[i] for i in conf],[observed[i] for i in conf]))
