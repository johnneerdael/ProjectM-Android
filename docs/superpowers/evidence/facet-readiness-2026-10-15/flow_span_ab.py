"""Flow A/B: add derived control-span columns (max - min of mesh control value ranges) to the cached descriptors.

Static only. Columns ending in /value_range/max#max and the matching /min#max give a span per control; audio-driven
zoom/rotation swings move the picture, which separate min/max columns express poorly to trees. Same 5-fold CV as the fit.
"""
import json, os, pickle, sys, math
from pathlib import Path
import numpy as np
W = Path(__file__).resolve().parents[2]
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from scipy.stats import spearmanr
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
rows = pickle.load(open(W / 'build/calibration-2026-10-14/descriptors-r13-current.pkl', 'rb'))
labels = {}
for n in os.listdir(RULER):
    r = json.loads((RULER / n).read_text())
    if r.get('status') == 'measured': labels[r['preset']] = r
def spans(row):
    out = {}
    for k, v in row.items():
        if k.endswith('/value_range/max#max') and 'mesh_field/controls/' in k:
            lo = row.get(k[:-len('max#max')] + 'min#max')
            if isinstance(lo, (int, float)) and math.isfinite(lo) and math.isfinite(v):
                control = k.split('mesh_field/controls/')[1].split('/')[0]
                key = 'derived:mesh_span/' + control
                out[key] = max(out.get(key, 0.), abs(v - lo))
                if control in ('zoom', 'sx', 'sy') and v > 0 and lo > 0: out['derived:mesh_log_span/' + control] = max(out.get('derived:mesh_log_span/' + control, 0.), abs(math.log(v / lo)))
    return out
names = [n for n, _ in rows if n in labels]; base = dict(rows)
target = 'mean_flow_screen_widths_per_s'
def matrix(extra):
    rs = [dict(base[n], **(spans(base[n]) if extra else {})) for n in names]
    counts = {}
    for r in rs:
        for k in r: counts[k] = counts.get(k, 0) + 1
    cols = sorted(k for k, c in counts.items() if c >= len(rs) * .01); idx = {k: i for i, k in enumerate(cols)}
    X = np.full((len(rs), len(cols)), -1e9)
    for i, r in enumerate(rs):
        for k, v in r.items():
            j = idx.get(k)
            if j is not None and np.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
    return X, cols
y = np.array([math.log1p(10 * labels[n][target]) for n in names])
for tag, extra in (('base', False), ('+spans', True)):
    X, cols = matrix(extra); oof = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=11).split(X):
        oof[te] = HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr], y[tr]).predict(X[te])
    print(tag, len(cols), 'columns; flow OOF Spearman', round(float(spearmanr(oof, y).statistic), 4), flush=True)
