"""A/B (static, out of fold): No strobe calm classifier on the r15 descriptor cache, with and without the prototype
audio-response columns (audio_response_corpus.py). Same weights, folds and trees as the fit. Reported: ROC AUC, and the
largest admission (calm p threshold grid, with the r15 jumps estimate < 0.05) holding 0 strobing presets plus the
admission at the same threshold one grid step stricter (margin check)."""
import json, os, pickle, math
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
oof = json.load(open(C / 'oof-r15.json'))['predictions']
extra = pickle.load(open(C / 'audio-response-cols.pkl', 'rb'))
excluded = set()
for p in ('validation-activity-2026-10-11/heldout-observations.json', 'validation-activity-2026-10-11/observations.json'):
    d = json.load(open(W / 'build' / p)); excluded |= set(d if isinstance(d, list) else d)
lab = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r.get('global_brightness_jumps_per_10s') is not None: lab[r['preset']] = r['global_brightness_jumps_per_10s']
rows = pickle.load(open(C / 'descriptors-r15.pkl', 'rb'))
names = [n for n, _ in rows if n in lab and n in oof and n not in excluded and oof[n].get('no_strobe_probability') is not None]
base = dict(rows); del rows
def matrix(with_extra):
    rs = [dict(base[n], **(extra.get(n, {}) if with_extra else {})) for n in names]
    counts = {}
    for r in rs:
        for k in r: counts[k] = counts.get(k, 0) + 1
    cols = sorted(k for k, c in counts.items() if c >= len(rs) * .01); idx = {k: i for i, k in enumerate(cols)}
    X = np.full((len(rs), len(cols)), -1e9, dtype=np.float32)
    for i, r in enumerate(rs):
        for k, v in r.items():
            j = idx.get(k)
            if j is not None and isinstance(v, (int, float)) and math.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
    return X, len(cols)
jumps = np.array([lab[n] for n in names]); y = (jumps < 1).astype(int); weight = np.where(jumps >= 10, 4., np.where(jumps >= 1, 2., 1.))
jest = np.array([math.expm1(oof[n]['global_brightness_jumps_per_10s']) for n in names])
print('presets', len(names), 'with audio columns', sum(1 for n in names if extra.get(n)))
for tag, flag in (('base', False), ('+audio', True)):
    X, ncols = matrix(flag); p = np.zeros(len(names))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=11).split(X, y):
        p[te] = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.,
                                               random_state=7).fit(X[tr], y[tr], sample_weight=weight[tr]).predict_proba(X[te])[:, 1]
    grid = np.arange(.80, .995, .01); best = None
    for i, t in enumerate(grid):
        m = (p >= t) & (jest < .05)
        if (jumps[m] >= 10).sum() == 0 and i + 1 < len(grid):
            m2 = (p >= grid[i + 1]) & (jest < .05)
            if (jumps[m2] >= 10).sum() == 0 and (best is None or m.sum() > best[0]):
                best = (int(m.sum()), int(((jumps[m] >= 1) & (jumps[m] < 10)).sum()), round(float(t), 2))
    print(f'{tag}: {ncols} columns; AUC {roc_auc_score(y, p):.3f}; largest 0-strobing admission (stable one step stricter): {best}', flush=True)
    np.save(C / f'audio-ab-{tag.strip("+")}.npy', p)
