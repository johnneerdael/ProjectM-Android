"""Corpus gate for the shape-outline equilibrium term: recompute equilibrium display luma for every corpus preset with
the current code and compare with the r15 cached values (previous code) against ruler mean luminance."""
import json, gzip, base64, sys, os, pickle, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def one(path):
    warnings.filterwarnings('ignore')
    from feedback_equilibrium import equilibrium
    try:
        d = json.load(open(path)); s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        e = equilibrium(s); return d['name'], (e['display_local_luma'], e['display_spread_luma'], e['elements'])
    except Exception:
        return None
if __name__ == '__main__':
    import numpy as np
    from scipy.stats import spearmanr
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    paths = sorted(str(R / n) for n in os.listdir(R)); new = {}
    with ProcessPoolExecutor(10) as pool:
        for row in pool.map(one, paths, chunksize=8):
            if row: new[row[0]] = row[1]
    pickle.dump(new, open(W / 'build/calibration-2026-10-14/equilibrium-outline.pkl', 'wb'))
    old = dict(pickle.load(open(W / 'build/calibration-2026-10-14/recipe-equilibrium-cols-r15.pkl', 'rb')))
    RU = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; lum = {}
    for f in os.listdir(RU):
        r = json.loads((RU / f).read_text())
        if r.get('status') == 'measured': lum[r['preset']] = r['mean_luminance']
    names = [n for n in new if n in lum and old.get(n, {}).get('equilibrium:display_local_luma') is not None]
    y = np.array([lum[n] for n in names])
    for tag, idx, key in (('local', 0, 'equilibrium:display_local_luma'), ('spread', 1, 'equilibrium:display_spread_luma')):
        a = np.array([old[n][key] for n in names]); b = np.array([new[n][idx] for n in names])
        print(f'{tag}: Spearman vs ruler luminance old {spearmanr(a, y).statistic:.4f} new {spearmanr(b, y).statistic:.4f}; changed {int((np.abs(a - b) > 1e-6).sum())}')
    zero_old = [n for n in names if old[n]['equilibrium:display_local_luma'] < .01 and old[n]['equilibrium:display_spread_luma'] < .01]
    zero_new = [n for n in names if new[n][0] < .01 and new[n][1] < .01]
    for tag, z in (('old', zero_old), ('new', zero_new)):
        print(f'{tag}: equilibrium < .01: {len(z)} presets, ruler < .12 {np.mean([lum[n] < .12 for n in z]):.1%}, ruler mean {np.mean([lum[n] for n in z]):.3f}')
    moved = [n for n in zero_old if n not in set(zero_new)]
    print(f'left the black group: {len(moved)}, their ruler mean {np.mean([lum[n] for n in moved]) if moved else float("nan"):.3f}, ruler > .2 {np.mean([lum[n] > .2 for n in moved]) if moved else 0:.0%}')
