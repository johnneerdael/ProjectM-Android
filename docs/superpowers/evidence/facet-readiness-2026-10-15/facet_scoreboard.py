"""Readiness scoreboard: static (calibrated, out-of-fold) facet membership vs engine-ruler membership, per option.

For each option with a metric rule, the static estimate and the ruler value are both put through the same rule.
Reported per option: agreement, precision (of the statically admitted, how many truly belong), recall, and admitted
count. Static only: OOF predictions from the calibration fit (argv[1]).
"""
import json, os, sys, math
from pathlib import Path
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(sys.argv[1])); pred = oof['predictions']; tf = oof['transforms']
facets = json.load(open(W / 'core/src/main/assets/preset-attributes/facets.json'))
MAP = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'warm_cool': 'warm_cool', 'flow': 'mean_flow_screen_widths_per_s',
       'frame_difference': 'mean_abs_frame_difference', 'jumps': 'global_brightness_jumps_per_10s'}
def inv(v, t): return math.expm1(v) if t == 'log1p' else (math.expm1(v) / 10 if t == 'log1p10' else v)
ops = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}
def member(values, option):
    for rule in option['all']:
        if 'metric' not in rule: return None
        k = MAP.get(rule['metric'])
        if k is None or values.get(k) is None: return None
        if not ops[rule['op']](values[k], rule['value']): return False
    return True
stats = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') != 'measured' or r['preset'] not in pred: continue
    est = {k: inv(v, tf.get(k)) for k, v in pred[r['preset']].items() if k in tf}
    for g in facets['groups']:
        for o in g['options']:
            a, b = member(est, o), member(r, o)
            if a is None or b is None: continue
            s = stats.setdefault((g['id'], o['id']), [0, 0, 0, 0])  # tp, fp, fn, tn
            s[0 if a and b else 1 if a else 2 if b else 3] += 1
print('| facet | option | agreement | precision | recall | admitted |'); print('|---|---|---|---|---|---|')
for (g, o), (tp, fp, fn, tn) in stats.items():
    n = tp + fp + fn + tn
    print(f'| {g} | {o} | {(tp + tn) / n:.0%} | {tp / max(tp + fp, 1):.0%} | {tp / max(tp + fn, 1):.0%} | {tp + fp} |')
