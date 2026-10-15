"""A/B (static, out of fold, r16 descriptors): + control-series columns (control_series_corpus.py) for flow, frame
difference and jumps (regressions, fit settings) and the No strobe calm classifier (fit weights; AUC and admissions
before the 1st/2nd/3rd strobing preset with the r15 jumps estimate < 0.05)."""
import json, os, pickle, math
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
extra = pickle.load(open(C / 'control-series-cols.pkl', 'rb')); oof = json.load(open(C / 'oof-r15q.json'))['predictions']
excluded = set()
for p in ('validation-activity-2026-10-11/heldout-observations.json', 'validation-activity-2026-10-11/observations.json'):
    d = json.load(open(W / 'build' / p)); excluded |= set(d if isinstance(d, list) else d)
lab = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured': lab[r['preset']] = r
rows = pickle.load(open(C / 'descriptors-r16.pkl', 'rb'))
names = [n for n, _ in rows if n in lab and n not in excluded and n in oof]
base = dict(rows); del rows
def matrix(with_extra):
    rs = [dict(base[n], **(extra.get(n) or {} if with_extra else {})) for n in names]
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
reg = lambda: HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7)
jumps = np.array([lab[n]['global_brightness_jumps_per_10s'] for n in names]); y_calm = (jumps < 1).astype(int)
w = np.where(jumps >= 10, 4., np.where(jumps >= 1, 2., 1.)); jest = np.array([math.expm1(oof[n]['global_brightness_jumps_per_10s']) for n in names])
for tag, flag in (('base', False), ('+series', True)):
    X = matrix(flag); line = [tag]
    for t, tf in (('mean_flow_screen_widths_per_s', lambda v: math.log1p(10 * v)), ('mean_abs_frame_difference', lambda v: math.log1p(10 * v)),
                  ('global_brightness_jumps_per_10s', math.log1p)):
        y = np.array([tf(lab[n][t]) for n in names]); o = np.zeros(len(y))
        for tr, te in KFold(5, shuffle=True, random_state=11).split(X): o[te] = reg().fit(X[tr], y[tr]).predict(X[te])
        line.append(f'{t.split("_")[1]} {spearmanr(o, y).statistic:.4f}')
    p = np.zeros(len(names))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=11).split(X, y_calm):
        p[te] = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr], y_calm[tr], sample_weight=w[tr]).predict_proba(X[te])[:, 1]
    order = np.argsort(-np.where(jest < .05, p, -1)); cum = np.cumsum(jumps[order] >= 10)
    line.append(f'no_strobe AUC {roc_auc_score(y_calm, p):.4f} admitted before strobing #1/#2/#3: ' + '/'.join(str(int(np.argmax(cum >= k))) for k in (1, 2, 3)))
    print(' | '.join(line), flush=True)
