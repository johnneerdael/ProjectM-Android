"""Work units and seconds to step each sampled preset's frame program to t=5 s (no cut), to size the budget."""
import json,gzip,base64,sys,os,random,time,warnings
from concurrent.futures import ProcessPoolExecutor
def one(path):
    warnings.filterwarnings('ignore'); sys.path.insert(0,'tools/milk-analyzer')
    from preset_recipe import _facts
    import feedback_equilibrium as F, eel_memory as M
    made=[]; orig=M.WorkBudget.__init__
    def init(self,units): orig(self,units); made.append(self)
    M.WorkBudget.__init__=init
    d=json.load(open(path)); s=json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64']))); facts=_facts(s)
    t=time.perf_counter(); F._stage_controls_uncached(facts,{'bass':1.,'mid':1.,'treb':1.,'bass_att':1.,'mid_att':1.,'treb_att':1.},(5.,),budget_units=1e12)
    return d['name'],time.perf_counter()-t,1e12-made[0].left
if __name__=='__main__':
    R='build/preset-corpus/corpus-understanding-9606-r14/results/'; files=sorted(os.listdir(R)); random.Random(7).shuffle(files)
    with ProcessPoolExecutor(4) as pool: rows=list(pool.map(one,[R+f for f in files[:int(sys.argv[1])]]))
    import numpy as np
    from scipy.stats import spearmanr
    T=np.array([r[1] for r in rows]); U=np.array([r[2] for r in rows])
    print('spearman seconds vs units',round(spearmanr(T,U).statistic,3),'median units/s',round(float(np.median(U/np.maximum(T,1e-3))),0))
    for q in (.5,.9,.95,.97,.98,.99): print('units q',q,round(float(np.quantile(U,q)),0),'seconds q',round(float(np.quantile(T,q)),2))
    for name,t,u in sorted(rows,key=lambda r:-r[1])[:10]: print(round(t,2),round(u),name[:50])
