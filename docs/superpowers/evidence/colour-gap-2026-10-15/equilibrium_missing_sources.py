"""Which light sources does the feedback equilibrium miss? Among presets whose equilibrium display luma is < 0.01
(local and spread), compare descriptor facts of ruler-bright (> 0.3) vs ruler-dark (< 0.05) presets. Facts with high
lift in the bright group are energy the equilibrium does not model. Static only (cached r15 descriptors)."""
import json, os, pickle, math, collections
from pathlib import Path
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
lum = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured': lum[r['preset']] = r['mean_luminance']
rows = pickle.load(open(C / 'descriptors-r15.pkl', 'rb'))
groups = {'bright': [], 'dark': []}
for n, row in rows:
    a, b = row.get('equilibrium:display_local_luma'), row.get('equilibrium:display_spread_luma')
    if n not in lum or a is None or b is None or a >= .01 or b >= .01: continue
    g = 'bright' if lum[n] > .3 else 'dark' if lum[n] < .05 else None
    if g: groups[g].append({k.split('#')[0] for k, v in row.items() if isinstance(v, (int, float)) and math.isfinite(v) and v != 0})
del rows
cnt = {g: collections.Counter() for g in groups}
for g, sets in groups.items():
    for s in sets: cnt[g].update(s)
N = {g: len(v) for g, v in groups.items()}; print(N)
out = []
for k in set(cnt['bright']) | set(cnt['dark']):
    b, d = cnt['bright'][k] / N['bright'], cnt['dark'][k] / N['dark']
    if max(b, d) >= .15: out.append((b / max(d, .01), b, d, k))
print('-- over-represented in BRIGHT (missed light sources):')
for lift, b, d, k in sorted(out, reverse=True)[:30]: print(f'lift {lift:5.1f} bright {b:4.0%} dark {d:4.0%} {k[:150]}')
print('-- over-represented in DARK:')
for lift, b, d, k in sorted(out)[:15]: print(f'lift {lift:5.2f} bright {b:4.0%} dark {d:4.0%} {k[:150]}')
