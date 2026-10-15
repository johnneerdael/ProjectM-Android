"""Per-option facet classifiers vs regression-then-threshold (static, out of fold, cached r13 descriptors).

For each metric facet option, a classifier learns ruler membership directly. Reported: recall at the precision the
regression rule achieves (like-for-like) and recall at 80% precision.
"""
import json, os, pickle, sys, math
from pathlib import Path
import numpy as np
W = Path(__file__).resolve().parents[2]
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
rows = pickle.load(open(W / 'build/calibration-2026-10-14/descriptors-r13-current.pkl', 'rb'))
oof = json.load(open(W / 'build/calibration-2026-10-14/oof-r13h.json')); pred = oof['predictions']; tf = oof['transforms']
facets = json.load(open(W / 'core/src/main/assets/preset-attributes/facets.json'))
MAP = {'coloured_share': 'coloured_share', 'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'warm_cool': 'warm_cool',
       'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference', 'jumps': 'global_brightness_jumps_per_10s'}
ops = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}
def inv(v, t): return math.expm1(v) if t == 'log1p' else (math.expm1(v) / 10 if t == 'log1p10' else v)
def member(values, option, options):
    for rule in option['all']:
        if 'not_option' in rule:
            m = member(values, options[rule['not_option']], options)
            if m is None: return None
            if m: return False
            continue
        if 'metric' not in rule: return None
        k = MAP.get(rule['metric']); v = values.get(k)
        if v is None: return None
        if not ops[rule['op']](v, rule['value']): return False
    return True
labels = {}
for n in os.listdir(RULER):
    r = json.loads((RULER / n).read_text())
    if r.get('status') == 'measured': labels[r['preset']] = r
names = [n for n, _ in rows if n in labels and n in pred]; base = {n: r for n, r in rows}
counts = {}
for n in names:
    for k in base[n]: counts[k] = counts.get(k, 0) + 1
cols = sorted(k for k, c in counts.items() if c >= len(names) * .01); idx = {k: i for i, k in enumerate(cols)}
X = np.full((len(names), len(cols)), -1e9)
for i, n in enumerate(names):
    for k, v in base[n].items():
        j = idx.get(k)
        if j is not None and np.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
print('| option | regression precision / recall | classifier recall at same precision | classifier recall at 80% precision |')
print('|---|---|---|---|')
for g in facets['groups']:
    opts = {o['id']: o for o in g['options']}
    for o in g['options']:
        if o['id'] in ('normal', 'balanced', 'drifting', 'no_strobe') or not all('metric' in r or 'not_option' in r for r in o['all']): continue
        y = np.array([bool(member(labels[n], o, opts)) for n in names]); reg = np.array([bool(member({k: inv(v, tf.get(k)) for k, v in pred[n].items() if k in tf}, o, opts)) for n in names])
        if y.sum() < 50: continue
        p = np.zeros(len(names))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=11).split(X, y):
            p[te] = HistGradientBoostingClassifier(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1., random_state=7).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        rp = (reg & y).sum() / max(reg.sum(), 1); rr = (reg & y).sum() / y.sum()
        order = np.argsort(-p); tp = np.cumsum(y[order]); prec = tp / np.arange(1, len(y) + 1); rec = tp / y.sum()
        def recall_at(target):
            ok = np.where(prec >= target)[0]
            return float(rec[ok.max()]) if len(ok) else 0.
        print(f'| {g["id"]}/{o["id"]} | {rp:.0%} / {rr:.0%} | {recall_at(rp):.0%} | {recall_at(.8):.0%} |', flush=True)
