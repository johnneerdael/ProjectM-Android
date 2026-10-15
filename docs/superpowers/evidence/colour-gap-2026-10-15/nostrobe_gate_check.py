"""No strobe gate re-check after a refit (static, OOF): admitted count and ruler jumps among the admitted, for the
shipped thresholds and a small grid. Strobing = ruler >= 10 jumps / 10 s; pulses = >= 1."""
import json, os, sys, math
from pathlib import Path
W = Path(__file__).resolve().parents[2]
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(sys.argv[1]))['predictions']
rows = []
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') == 'measured' and r['preset'] in oof and oof[r['preset']].get('no_strobe_probability') is not None:
        p = oof[r['preset']]; rows.append((p['no_strobe_probability'], math.expm1(p['global_brightness_jumps_per_10s']), r['global_brightness_jumps_per_10s']))
for pt in (.85, .9, .95):
    for jt in (.05, .1):
        adm = [j for p, e, j in rows if p >= pt and e < jt]
        print(f'p>={pt} jumps<{jt}: admitted {len(adm)}, strobing {sum(j >= 10 for j in adm)}, pulses {sum(1 <= j < 10 for j in adm)}')
