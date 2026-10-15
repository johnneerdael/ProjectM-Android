"""Agreement of the static-only grouping (static_grouping_export.py) with the engine-ruler bundle options, per option:
precision, recall and admitted count over all bundled presets with a measured row. In-sample for the calibration model
(bundled presets are its training set); the out-of-fold scoreboard is the honest estimate."""
import json, sys
from pathlib import Path
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
from preset_recipe import _attributes
idx = json.load(open(sys.argv[1])); rows, _ = _attributes()
defs = json.load(open(W / 'core/src/main/assets/preset-attributes/facets.json'))
order = [(g['id'], o['id']) for g in defs['groups'] if g['id'] != 'style' for o in g['options']]
names = [n for n in idx if n in rows and 'error' not in idx[n]]
tp = fp = fn = 0; lines = []
for group, option in order:
    a = sum(1 for n in names if option in (idx[n]['options'] or [])); t = sum(1 for n in names if option in rows[n][0])
    hit = sum(1 for n in names if option in (idx[n]['options'] or []) and option in rows[n][0])
    tp += hit; fp += a - hit; fn += t - hit
    lines.append(f'| {group} | {option} | {hit / max(a, 1):.0%} | {hit / max(t, 1):.0%} | {a} | {t} |')
none = sum(1 for n in names if not any(o in (idx[n]['options'] or []) for _, o in order))
print(f'presets compared: {len(names)} (export errors {sum(1 for r in idx.values() if "error" in r)}); presets with no Mood option: {none}')
print('| group | option | precision | recall | admitted | ruler members |'); print('|---|---|---|---|---|---|')
print('\n'.join(lines)); print(f'pooled: precision {tp / (tp + fp):.1%}, recall {tp / (tp + fn):.1%}')
dom = [n for n in names if idx[n].get('dominant_hue')]; print(f'dominant colour named for {len(dom)} presets; palette for {sum(1 for n in names if idx[n].get("palette"))}')
