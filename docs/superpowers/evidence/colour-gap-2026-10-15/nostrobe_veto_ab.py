"""No strobe A/B (static, out of fold, r15 descriptor cache): the shipped calm classifier (oof-r15) alone vs combined
with a dedicated strobing classifier (>= 10 jumps / 10 s) as a veto. For each rule, the largest admission with 0
strobing presets out of fold, and the pulses (1-9 jumps) it admits. Same 5-fold split and tree settings as the fit."""
import json, os, pickle, math
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
C = W / 'build/calibration-2026-10-14'
oof = json.load(open(C / 'oof-r15.json'))['predictions']
excluded = set()
for p in ('validation-activity-2026-10-11/heldout-observations.json', 'validation-activity-2026-10-11/observations.json'):
    d = json.load(open(W / 'build' / p)); excluded |= set(d if isinstance(d, list) else d)
labels = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r.get('global_brightness_jumps_per_10s') is not None: labels[r['preset']] = r
rows = pickle.load(open(C / 'descriptors-r15.pkl', 'rb'))
names = [n for n, _ in rows if n in labels and n in oof and n not in excluded and oof[n].get('no_strobe_probability') is not None]
base = dict(rows); del rows
counts = {}
for n in names:
    for k in base[n]: counts[k] = counts.get(k, 0) + 1
cols = sorted(k for k, c in counts.items() if c >= len(names) * .01); idx = {k: i for i, k in enumerate(cols)}
X = np.full((len(names), len(cols)), -1e9, dtype=np.float32)
for i, n in enumerate(names):
    for k, v in base[n].items():
        j = idx.get(k)
        if j is not None and isinstance(v, (int, float)) and math.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
del base
jumps = np.array([labels[n]['global_brightness_jumps_per_10s'] for n in names])
calm = np.array([oof[n]['no_strobe_probability'] for n in names])
jest = np.array([math.expm1(oof[n]['global_brightness_jumps_per_10s']) for n in names])
y = (jumps >= 10).astype(int); strobe = np.zeros(len(names))
for tr, te in StratifiedKFold(5, shuffle=True, random_state=11).split(X, y):
    strobe[te] = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.,
                                                random_state=7).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
np.save(C / 'nostrobe-veto-strobe-oof.npy', strobe); json.dump(names, open(C / 'nostrobe-veto-names.json', 'w'))
from sklearn.metrics import roc_auc_score
print('presets', len(names), 'strobing', int(y.sum()), 'strobe classifier AUC', round(roc_auc_score(y, strobe), 3), 'calm AUC for strobing', round(roc_auc_score(y, -calm), 3))
def best(mask_fn, grid):
    out = None
    for params in grid:
        m = mask_fn(*params)
        if (jumps[m] >= 10).sum() == 0 and (out is None or m.sum() > out[0]): out = (int(m.sum()), int(((jumps[m] >= 1) & (jumps[m] < 10)).sum()), params)
    return out
print('shipped gate p>=.93 & jumps<.05:', int(((calm >= .93) & (jest < .05)).sum()), 'admitted,', int((jumps[(calm >= .93) & (jest < .05)] >= 10).sum()), 'strobing')
print('calm + jumps only, max with 0 strobing:', best(lambda t, j: (calm >= t) & (jest < j), [(t, j) for t in np.arange(.80, .99, .01) for j in (.03, .05, .1)]))
print('calm + strobe veto, max with 0 strobing:', best(lambda t, s: (calm >= t) & (strobe <= s), [(t, s) for t in np.arange(.5, .99, .02) for s in (.002, .005, .01, .02, .03, .05)]))
print('calm + jumps + strobe veto:', best(lambda t, j, s: (calm >= t) & (jest < j) & (strobe <= s), [(t, j, s) for t in np.arange(.5, .99, .02) for j in (.05, .1, .2) for s in (.005, .01, .02, .03, .05)]))
# Margin: same rules with the threshold one grid step stricter must also hold 0 strobing (robustness)
