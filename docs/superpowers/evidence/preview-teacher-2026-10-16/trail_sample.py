"""Random-sample check of the trail-histogram display estimate against the ruler (static, no previews)."""
import json, gzip, base64, os, sys, random, pickle, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair'); sys.path.insert(0, str(W / 'build/preview-corpus-2026-10-16')); sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def one(path):
    warnings.filterwarnings('ignore')
    from trail_equilibrium import trail_display
    try:
        d = json.load(open(path)); s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        return d['name'], trail_display(s)
    except Exception:
        return None
if __name__ == '__main__':
    import numpy as np
    from scipy.stats import spearmanr
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    names = sorted(os.listdir(R)); random.Random(int(sys.argv[2])).shuffle(names); paths = [str(R / n) for n in names[:int(sys.argv[1])]]
    with ProcessPoolExecutor(10) as ex: res = dict(r for r in ex.map(one, paths, chunksize=4) if r)
    pickle.dump(res, open(W / f'build/preview-corpus-2026-10-16/trail-sample-{sys.argv[2]}.pkl', 'wb'))
    eq = pickle.load(open(W / 'build/calibration-2026-10-14/equilibrium-outline.pkl', 'rb'))
    RU = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; rows = []
    for n, t in res.items():
        rf = RU / (n[:-5] + '.json')
        if not rf.exists() or n not in eq: continue
        r = json.load(open(rf))
        if r.get('status') == 'measured': rows.append((eq[n][0], eq[n][1], t, r['mean_luminance']))
    a = np.array(rows); print('random presets', len(a))
    for i, l in enumerate(('eq local', 'eq spread', 'trail histogram')): print(f'{l:16s} Spearman vs ruler {spearmanr(a[:, i], a[:, 3]).statistic:.3f}  MAE {np.mean(abs(a[:, i] - a[:, 3])):.3f}')
