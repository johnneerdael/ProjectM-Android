"""Residual gap scan: which static facts are over-represented among the presets the static model gets most wrong?

Static only: out-of-fold calibrated estimates (argv[1]) vs ruler, cached descriptor rows (argv[2]). For a target
(argv[3], default mean_luminance), take the worst 10% by absolute error and compare how often each descriptor
column is present (non-missing, non-zero) there vs in the rest. High lift = a static fact the model cannot use well.
"""
import json, os, pickle, sys, math, collections
from pathlib import Path
import numpy as np
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(sys.argv[1])); pred = oof['predictions']; tf = oof['transforms']
target = sys.argv[3] if len(sys.argv) > 3 else 'mean_luminance'
rows = pickle.load(open(sys.argv[2], 'rb')); base = dict(rows)
def inv(v, t): return math.expm1(v) if t == 'log1p' else (math.expm1(v) / 10 if t == 'log1p10' else v)
err = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r['preset'] in pred and target in pred[r['preset']] and r['preset'] in base and r.get(target) is not None:
        err[r['preset']] = inv(pred[r['preset']][target], tf.get(target)) - r[target]
names = sorted(err, key=lambda n: -abs(err[n])); k = len(names) // 10
worst, rest = set(names[:k]), names[k:]
over = sum(1 for n in worst if err[n] > 0)
def present(n): return {c for c, v in base[n].items() if v not in (0, None) and (not isinstance(v, float) or math.isfinite(v))}
cw, cr = collections.Counter(), collections.Counter()
for n in worst: cw.update(present(n))
for n in rest: cr.update(present(n))
rows_out = []
for c, a in cw.items():
    pw, pr = a / len(worst), cr[c] / len(rest)
    if pw >= .08: rows_out.append((pw / max(pr, 1e-3), pw, pr, c))
print(f'target {target}: worst {len(worst)} presets (mean |err| {np.mean([abs(err[n]) for n in worst]):.3f}; overestimated {over}), rest {len(rest)}')
for lift, pw, pr, c in sorted(rows_out, reverse=True)[:25]: print(f'lift {lift:5.2f}  worst {pw:.0%}  rest {pr:.0%}  {c[:150]}')
