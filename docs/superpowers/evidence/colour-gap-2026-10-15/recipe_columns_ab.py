"""A/B: descriptor rows + recipe colour probe columns (recipe_columns.py) vs descriptor rows alone. Same 5-fold CV
as the calibration fit. Reports OOF Spearman for colour targets, leading-hue top-2 from the eight hue regressions,
and monochrome/pastel classifier AUC. Static only.

Derived matrix columns: the composite colour matrix maps input colour to display colour; its singular values say
how many colour directions survive (rank-1 = every input becomes one fixed chroma), and the saturation of
black + column per unit input bounds the displayed chroma."""
import json, os, pickle, sys, math
from pathlib import Path
import numpy as np
W = Path(__file__).resolve().parents[2]
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
rows = pickle.load(open(W / 'build/calibration-2026-10-14/descriptors-r14.pkl', 'rb'))
extra = pickle.load(open(sys.argv[1], 'rb'))
HUES = ('red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'pink')
def derived(e):
    out = dict(e)
    try:
        M = np.array([[e[f'recipe:matrix/{a}_to_{b}'] for b in 'rgb'] for a in 'rgb']); black = np.array([e[f'recipe:matrix/black_{c}'] for c in 'rgb'])
    except KeyError: return out
    s = np.linalg.svd(M, compute_uv=False)
    out['recipe:matrix/s1'] = float(s[0]); out['recipe:matrix/s2_over_s1'] = float(s[1] / s[0]) if s[0] > 1e-6 else 0.
    out['recipe:matrix/s3_over_s1'] = float(s[2] / s[0]) if s[0] > 1e-6 else 0.
    sats = []
    for i in range(3):
        v = np.clip(black + M[i] / .3 * .5, 0, 1); mx = v.max(); sats.append(float((mx - v.min()) / mx) if mx > 1e-6 else 0.)
    out['recipe:matrix/max_output_saturation'] = max(sats); out['recipe:matrix/mean_output_saturation'] = sum(sats) / 3
    mx = black.max(); out['recipe:matrix/black_saturation'] = float((mx - black.min()) / mx) if mx > 1e-6 else 0.
    return out
labels = {}
for n in os.listdir(RULER):
    r = json.loads((RULER / n).read_text())
    if r.get('status') == 'measured': labels[r['preset']] = r
names = [n for n, _ in rows if n in labels]; base = dict(rows)
def matrix(use):
    rs = [dict(base[n], **(derived(extra.get(n, {})) if use else {})) for n in names]
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
def reg(): return HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7)
def clf(): return HistGradientBoostingClassifier(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7)
for tag, use in (('base', False), ('+recipe', True)):
    X, cols = matrix(use); res = {}
    def oof_reg(y, mask):
        o = np.full(len(y), np.nan); Xi = X[mask]; yi = y[mask]; oi = np.zeros(len(yi))
        for tr, te in KFold(5, shuffle=True, random_state=11).split(Xi): oi[te] = reg().fit(Xi[tr], yi[tr]).predict(Xi[te])
        o[mask] = oi; return o
    for t in ('mean_saturation', 'coloured_share', 'mean_luminance'):
        y = np.array([labels[n].get(t) if labels[n].get(t) is not None else np.nan for n in names], float); m = ~np.isnan(y)
        o = oof_reg(np.nan_to_num(y), m); res[t] = round(float(spearmanr(o[m], y[m]).statistic), 4)
    hs = {}
    cs = np.array([labels[n].get('coloured_share') or 0 for n in names])
    for h in HUES:
        y = np.array([float((labels[n].get('hue_shares') or {}).get(h, 0.)) for n in names]); hs[h] = oof_reg(y, np.ones(len(y), bool))
    hit = tot = 0
    for i, n in enumerate(names):
        if cs[i] <= .2 or not labels[n].get('hue_shares'): continue
        lead = max(HUES, key=lambda h: hs[h][i]); tot += 1; hit += lead in list(labels[n]['hue_shares'])[:2]
    res['hue_top2'] = round(hit / tot, 4)
    lum = np.array([labels[n].get('mean_luminance') or 0 for n in names]); sat = np.array([labels[n].get('mean_saturation') or 0 for n in names])
    for opt, y in (('monochrome', cs < .1), ('pastel', (lum > .35) & (sat < .3) & (cs >= .1))):
        y = y.astype(int); o = np.zeros(len(y))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=11).split(X, y): o[te] = clf().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        res[opt + '_auc'] = round(float(roc_auc_score(y, o)), 4)
        order = np.argsort(-o); tp = np.cumsum(y[order]); prec = tp / np.arange(1, len(y) + 1)
        ok = np.where(prec >= .7)[0]; res[opt + '_recall@70'] = round(float(tp[ok.max()] / y.sum()), 3) if len(ok) else 0.
    print(tag, len(cols), 'columns', json.dumps(res), flush=True)
