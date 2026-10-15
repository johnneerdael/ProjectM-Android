"""Readiness scoreboard v2: the shipped decision path, out of fold. Value rules on calibrated estimates (with the
activity score for Energy), then preset_recipe._apply_option_probabilities (per-option classifiers with their
thresholds and margin-based conflict resolution) and the No strobe gate, against ruler memberships.
argv[1] OOF predictions, argv[2] model (thresholds). Static only."""
import json, os, sys, math, gzip
from pathlib import Path
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
import preset_facets
from preset_recipe import _apply_option_probabilities, _no_strobe_gate, facet_activity
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(sys.argv[1])); pred = oof['predictions']; tf = oof['transforms']
model = json.load(gzip.open(sys.argv[2], 'rt'))
THRESH = {k: v['threshold'] for k, v in model['targets'].items() if k.startswith('facet_') and 'threshold' in v}
definition = preset_facets.load_definition()
FIELDS = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'warm_cool': 'warm_cool', 'coloured_share': 'coloured_share',
          'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference', 'jumps': 'global_brightness_jumps_per_10s'}
def inv(v, t): return math.expm1(v) if t == 'log1p' else (math.expm1(v) / 10 if t == 'log1p10' else v)
def metrics(values):
    m = {k: values.get(f) for k, f in FIELDS.items()}
    if all(m.get(k) is not None for k in ('frame_difference', 'flow', 'jumps')): m['activity'] = facet_activity({k: m[k] for k in ('frame_difference', 'flow', 'jumps')})
    return {k: v for k, v in m.items() if v is not None}
groups = {o['id']: g['id'] for g in definition['groups'] for o in g['options'] if g['id'] != 'style'}
stats = {}
for f in os.listdir(RULER):
    r = json.loads((RULER / f).read_text())
    if r.get('status') != 'measured' or r['preset'] not in pred: continue
    p = pred[r['preset']]; est = {k: inv(v, tf.get(k)) for k, v in p.items() if k in tf}
    truth = set(preset_facets.memberships(metrics(r), [], definition))
    options = list(preset_facets.memberships(metrics(est), [], definition))
    st = {k: {'value': v, 'threshold': THRESH[k]} for k, v in p.items() if k in THRESH}
    st['no_strobe_probability'] = {'value': p.get('no_strobe_probability')}; st['global_brightness_jumps_per_10s'] = {'value': est.get('global_brightness_jumps_per_10s')}
    options, _, _ = _apply_option_probabilities(st, definition, options, [], [])
    options, _, _ = _no_strobe_gate(st, options, [], [])
    for o, g in groups.items():
        a, b = o in options, o in truth
        s = stats.setdefault((g, o), [0, 0, 0, 0]); s[0 if a and b else 1 if a else 2 if b else 3] += 1
print('| facet | option | precision | recall | admitted | ruler members |'); print('|---|---|---|---|---|---|')
for (g, o), (tp, fp, fn, tn) in stats.items():
    print(f'| {g} | {o} | {tp / max(tp + fp, 1):.0%} | {tp / max(tp + fn, 1):.0%} | {tp + fp} | {tp + fn} |')
