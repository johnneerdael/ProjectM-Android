"""Palette concentration A/B (static, out of fold). Predicted hue shares (oof-r15) are too flat on single-colour
presets (overlap 57% where the ruler's top colour > 60%) and one global sharpening power cannot fix that without
hurting spread palettes. Here a regressor predicts the ruler's top-colour share from the r16 descriptors (5-fold,
fit settings); the per-preset power is chosen from that prediction (powers fitted on the training folds only, by
concentration bin), then palette overlap with the ruler is compared."""
import json, os, pickle, math
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from scipy.stats import spearmanr
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
H = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'pink']
oof = json.load(open(C / 'oof-r15.json'))['predictions']
excluded = set()
for p in ('validation-activity-2026-10-11/heldout-observations.json', 'validation-activity-2026-10-11/observations.json'):
    d = json.load(open(W / 'build' / p)); excluded |= set(d if isinstance(d, list) else d)
lab = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r['coloured_share'] > .2: lab[r['preset']] = r
rows = pickle.load(open(C / 'descriptors-r16.pkl', 'rb'))
names = [n for n, _ in rows if n in lab and n in oof and n not in excluded and all(f'hue_share_{h}' in oof[n] for h in H)]
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
T = np.array([[lab[n]['hue_shares'].get(h, 0.) for h in H] for n in names]); T /= np.maximum(T.sum(1, keepdims=True), 1e-9)
P = np.array([[max(1e-4, oof[n][f'hue_share_{h}']) for h in H] for n in names]); P /= P.sum(1, keepdims=True)
top = T.max(1); conc = np.zeros(len(names)); powers_used = np.ones(len(names))
POWERS = (1., 1.5, 2., 2.5, 3., 4.)
def overlap(Q, T): return np.minimum(Q, T).sum(1)
def sharpen(P, k): Q = P ** k; return Q / Q.sum(1, keepdims=True)
for tr, te in KFold(5, shuffle=True, random_state=11).split(X):
    model = HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr], top[tr])
    inner = np.zeros(len(tr))
    for a, b in KFold(5, shuffle=True, random_state=3).split(tr):  # concentration estimates for the training rows, out of fold too
        inner[b] = HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr][a], top[tr][a]).predict(X[tr][b])
    conc[te] = model.predict(X[te])
    edges = np.quantile(inner, [0, .25, .5, .75, 1.]); edges[0], edges[-1] = -1, 2
    for lo, hi in zip(edges, edges[1:]):
        m_tr = (inner >= lo) & (inner < hi); m_te = (conc[te] >= lo) & (conc[te] < hi)
        best = max(POWERS, key=lambda k: overlap(sharpen(P[tr][m_tr], k), T[tr][m_tr]).mean() if m_tr.any() else 0)
        powers_used[te[m_te]] = best
Q = np.array([sharpen(P[i:i + 1], powers_used[i])[0] for i in range(len(names))])
print('presets', len(names), '; top-colour share predicted OOF: Spearman', round(float(spearmanr(conc, top).statistic), 3))
for lbl, m in (('all', np.ones(len(names), bool)), ('dominant >60%', top > .6), ('mixed 40-60%', (top >= .4) & (top <= .6)), ('spread <40%', top < .4)):
    print(f'{lbl:14s} overlap flat {100 * overlap(P[m], T[m]).mean():.1f}%  concentration-sharpened {100 * overlap(Q[m], T[m]).mean():.1f}%')
print('powers used:', {k: int((powers_used == k).sum()) for k in POWERS})
