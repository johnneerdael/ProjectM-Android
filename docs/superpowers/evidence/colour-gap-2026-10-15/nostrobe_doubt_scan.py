"""No strobe recall scan (static, OOF r15): among calm presets (0 jumps), which descriptor facts make the classifier
doubt (p < 0.5 vs p >= 0.9)? For each, also its presence among strobing presets (>= 10 jumps): a fact frequent in
doubted-calm AND rare in strobing is a confusion the model could learn away; one frequent in strobing is real doubt."""
import json, os, pickle, math, collections
from pathlib import Path
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'; C = W / 'build/calibration-2026-10-14'
oof = json.load(open(C / 'oof-r15.json'))['predictions']
lab = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r.get('global_brightness_jumps_per_10s') is not None: lab[r['preset']] = r['global_brightness_jumps_per_10s']
rows = pickle.load(open(C / 'descriptors-r15.pkl', 'rb'))
def present(row):
    out = set()
    for k, v in row.items():
        if isinstance(v, (int, float)) and math.isfinite(v) and v != 0:
            out.add(k.split('#')[0] if '#' in k else k)
    return out
groups = {'doubt': [], 'trust': [], 'strobe': []}
for n, row in rows:
    if n not in lab or n not in oof or oof[n].get('no_strobe_probability') is None: continue
    p = oof[n]['no_strobe_probability']; j = lab[n]
    g = 'strobe' if j >= 10 else 'doubt' if j == 0 and p < .5 else 'trust' if j == 0 and p >= .9 else None
    if g: groups[g].append(present(row))
del rows
cnt = {g: collections.Counter() for g in groups}
for g, sets in groups.items():
    for s in sets: cnt[g].update(s)
N = {g: len(v) for g, v in groups.items()}; print(N)
out = []
for k in set(cnt['doubt']) | set(cnt['trust']):
    d, t, s = cnt['doubt'][k] / N['doubt'], cnt['trust'][k] / N['trust'], cnt['strobe'][k] / N['strobe']
    if d >= .1 and d / max(t, .005) >= 2.5: out.append((d / max(t, .005), d, t, s, k))
print('facts over-represented in doubted calm presets (vs trusted calm), with strobing share:')
for lift, d, t, s, k in sorted(out, reverse=True)[:40]:
    print(f'lift {lift:5.1f} doubt {d:4.0%} trust {t:4.0%} strobe {s:4.0%} {"CONFUSION " if s < d * .8 else ""}{k[:140]}')
