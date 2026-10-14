"""Cross-fitted monotone quantile mapping of OOF estimates onto the ruler distribution; writes a mapped OOF file."""
import json, os, sys, math
import numpy as np
from pathlib import Path
W = Path(__file__).resolve().parents[2]; RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(sys.argv[1])); pred = oof['predictions']; tf = oof['transforms']
labels = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r['preset'] in pred: labels[r['preset']] = r
names = sorted(labels); rng = np.random.default_rng(11); fold = rng.integers(0, 5, len(names))
out = {n: dict(pred[n]) for n in names}
for t, transform in tf.items():
    keys = [i for i, n in enumerate(names) if t in pred[names[i]] and labels[names[i]].get(t) is not None]
    def fwd(v): return math.log1p(v) if transform == 'log1p' else (math.log1p(10 * v) if transform == 'log1p10' else v)
    p = np.array([pred[names[i]][t] for i in keys]); y = np.array([fwd(labels[names[i]][t]) for i in keys]); fk = fold[keys]
    q = np.linspace(0, 1, 101)
    for k in range(5):
        tr, te = fk != k, fk == k
        xp, yp = np.quantile(p[tr], q), np.quantile(y[tr], q)
        xp, idx = np.unique(xp, return_index=True); yp = yp[idx]
        mapped = np.interp(p[te], xp, yp)
        for i, v in zip(np.array(keys)[te], mapped): out[names[i]][t] = float(v)
json.dump({'predictions': out, 'transforms': tf}, open(sys.argv[2], 'w'))
