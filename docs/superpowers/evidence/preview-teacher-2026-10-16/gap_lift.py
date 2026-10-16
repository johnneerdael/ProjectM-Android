"""Which static facts mark the presets where the static maths misses but the preview (source maths, frame by frame) is
right? Ledger classes vs descriptor-fact presence (r16 cache): lift = share in gap class / share in 'agree' class."""
import json, pickle, math, collections, sys
from pathlib import Path
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair')
rows = [json.loads(l) for l in open(W / 'build/preview-corpus-2026-10-16/ledger.jsonl')]
def cls(r, k='mean_luminance'):
    v = r[k]
    if None in v.values(): return None
    if abs(v['preview'] - v['ruler']) < .08 and abs(v['static'] - v['ruler']) > .15: return 'under' if v['static'] < v['ruler'] else 'over'
    if abs(v['preview'] - v['ruler']) < .08 and abs(v['static'] - v['ruler']) < .08: return 'agree'
want = {r['preset']: cls(r) for r in rows}
desc = pickle.load(open(W / 'build/calibration-2026-10-14/descriptors-r16.pkl', 'rb'))
sets = collections.defaultdict(list)
for n, row in desc:
    c = want.get(n)
    if c: sets[c].append({k.split('#')[0] for k, v in row.items() if isinstance(v, (int, float)) and math.isfinite(v) and v != 0})
del desc
cnt = {c: collections.Counter() for c in sets}
for c, ss in sets.items():
    for s in ss: cnt[c].update(s)
N = {c: len(v) for c, v in sets.items()}; print(N)
for gap in ('under', 'over'):
    out = []
    for k in set(cnt[gap]) | set(cnt['agree']):
        a, b = cnt[gap][k] / N[gap], cnt['agree'][k] / N['agree']
        if a >= .15 and a / max(b, .01) >= 2: out.append((a / max(b, .01), a, b, k))
    print(f'-- static {gap}-estimates vs agree: facts over-represented')
    for lift, a, b, k in sorted(out, reverse=True)[:22]: print(f'lift {lift:5.1f} {gap} {a:4.0%} agree {b:4.0%} {k[:140]}')
