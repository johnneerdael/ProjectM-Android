"""A/B (static, out of fold, r15 descriptor cache): luminance / frame difference / flow / facet bright & dark recall with
and without the warp detail-gain probe and the outline-corrected equilibrium columns. Same regressor and folds as the fit."""
import json, os, pickle, math
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from scipy.stats import spearmanr
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
dg = pickle.load(open(C / 'detail-gain-cols.pkl', 'rb'))
eq = pickle.load(open(C / 'equilibrium-outline.pkl', 'rb'))
excluded = set()
for p in ('validation-activity-2026-10-11/heldout-observations.json', 'validation-activity-2026-10-11/observations.json'):
    d = json.load(open(W / 'build' / p)); excluded |= set(d if isinstance(d, list) else d)
lab = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured': lab[r['preset']] = r
rows = pickle.load(open(C / 'descriptors-r15.pkl', 'rb'))
names = [n for n, _ in rows if n in lab and n not in excluded]
base = dict(rows); del rows
def extra(n, variant):
    out = {}
    if variant in ('detail', 'both'): out.update({k: v for k, v in (dg.get(n) or {}).items() if v is not None})
    if variant in ('outline', 'both') and n in eq:
        out['equilibrium:display_local_luma'], out['equilibrium:display_spread_luma'] = eq[n][0], eq[n][1]
    return out
def matrix(variant):
    rs = [dict(base[n], **extra(n, variant)) for n in names]
    counts = {}
    for r in rs:
        for k in r: counts[k] = counts.get(k, 0) + 1
    cols = sorted(k for k, c in counts.items() if c >= len(rs) * .01); idx = {k: i for i, k in enumerate(cols)}
    X = np.full((len(rs), len(cols)), -1e9, dtype=np.float32)
    for i, r in enumerate(rs):
        for k, v in r.items():
            j = idx.get(k)
            if j is not None and isinstance(v, (int, float)) and math.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
    return X
targets = {'mean_luminance': lambda v: v, 'mean_abs_frame_difference': lambda v: math.log1p(10 * v)}
for variant in ('base', 'outline', 'detail', 'both'):
    X = matrix(variant); line = [variant]
    for t, tf in targets.items():
        y = np.array([tf(lab[n][t]) for n in names]); oof = np.zeros(len(y))
        for tr, te in KFold(5, shuffle=True, random_state=11).split(X):
            oof[te] = HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr], y[tr]).predict(X[te])
        line.append(f'{t} {spearmanr(oof, y).statistic:.4f}')
        if t == 'mean_luminance':
            mae = np.mean(np.abs(oof - y)); line.append(f'MAE {mae:.4f}')
    print(' | '.join(line), flush=True)
