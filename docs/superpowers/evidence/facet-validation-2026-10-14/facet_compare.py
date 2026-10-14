"""Static-prediction facet statistics vs engine-ruler labels on the group selection; baseline: calibrated model OOF."""
import json, math, os, subprocess, sys
from pathlib import Path
from scipy.stats import spearmanr
G = Path(__file__).parent; ROOT = G.parents[1]; tag = sys.argv[1]; selection = sys.argv[2] if len(sys.argv) > 2 else 'selection.json'
TF = {'mean_luminance': None, 'mean_abs_frame_difference': 'log1p10', 'mean_flow_screen_widths_per_s': 'log1p10',
      'global_brightness_jumps_per_10s': 'log1p', 'mean_saturation': None, 'warm_cool': None}
tf = lambda v, k: math.log1p(10 * v) if k == 'log1p10' else math.log1p(v) if k == 'log1p' else v
R = ROOT / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
ruler = {}
for n in os.listdir(R):
    row = json.load(open(R / n)); ruler[row['preset']] = row
ours = {}
for p in json.load(open(G / selection))['presets']:
    f = G / f'facet-{tag}' / (Path(p['name']).stem + '.json')
    if f.exists():
        row = json.load(open(f))
        if row.get('status') == 'predicted' and p['name'] in ruler and ruler[p['name']].get('status') == 'measured': ours[p['name']] = row
base = json.load(open(ROOT / 'build/calibration-2026-10-12/oof-r12v3.json'))['predictions']
names = [n for n in ours if n in base]
print('presets compared', len(names))
for k, kind in TF.items():
    pairs = [(ours[n].get(k), ruler[n].get(k), base[n].get(k)) for n in names]
    pairs = [x for x in pairs if None not in x]
    s_ours = spearmanr([a for a, _, _ in pairs], [b for _, b, _ in pairs]).correlation
    s_base = spearmanr([c for _, _, c in pairs], [b for _, b, _ in pairs]).correlation
    print(f'{k:34s} static {s_ours:.3f}   calibrated {s_base:.3f}   (n={len(pairs)})')
out = G / f'facet-{tag}-oof.json'; sub = G / f'facet-{tag}-base-oof.json'
json.dump({'predictions': {n: {k: tf(ours[n][k], kind) for k, kind in TF.items() if ours[n].get(k) is not None} for n in names}}, open(out, 'w'))
json.dump({'predictions': {n: base[n] for n in names}}, open(sub, 'w'))
S = '/private/tmp/claude-501/-Users-jneerdael-Scripts-Projectm-TV--worktrees-predictor-memory-repair/6ede8e77-c9c9-48ac-9881-a34ad107af46/scratchpad/facet_agreement.py'
for label, path in (('static', out), ('calibrated', sub)):
    for mode in ([], ['remap']):
        r = subprocess.run([str(ROOT / 'build/preset-lab-venv/bin/python'), S, str(path), *mode], cwd=ROOT, capture_output=True, text=True)
        try: groups = json.loads(r.stdout)['groups']
        except Exception: groups = r.stderr[-300:]
        print(label, 'remap' if mode else 'direct', groups, 'mean', round(sum(groups.values()) / len(groups), 3) if isinstance(groups, dict) else '')
