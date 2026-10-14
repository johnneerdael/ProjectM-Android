"""Colour-through-feedback gap, baseline: how well do today's STATIC colour cues predict the engine ruler's hues?

Static only: build_recipe on the 200 group-measure descriptions (no frames stepped or rendered). Cues compared
with the ruler row (frames 60-299): the closed-form steady-state hue family, element palettes (shape
colour_over_time, wave colours) and the composite detail response. Metric: does the cue's leading hue match
one of the ruler's top-2 hues (presets with coloured_share > 0.2)?
"""
import json, sys, glob, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
R = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
DESCS = sorted(glob.glob(str(W / 'build/group-measure-2026-10-13/desc-d7ad1519/*.json')))


def cues(path):
    import warnings; warnings.filterwarnings('ignore')
    from preset_recipe import build_recipe
    try:
        s = json.load(open(path)); r = build_recipe(s)
    except Exception as error:
        return Path(path).stem, {'error': str(error)[:120]}
    fb = r['render']['feedback']; comp = r['render'].get('composite') or {}
    shapes = {}
    for L in r['render']['layers']:
        c = L.get('colour_over_time')
        if c and 'tint' not in (c.get('role') or ''):
            for h, v in c['hue_shares'].items(): shapes[h] = shapes.get(h, 0) + v
    return Path(path).stem, {'steady': (fb.get('steady_state') or {}).get('hue_family'),
                             'detail': list((comp.get('detail_response') or {}).get('hue_shares') or {})[:2],
                             'shapes': sorted(shapes, key=lambda h: -shapes[h])[:2],
                             'load_spread': bool(comp.get('load_spread')), 'hue_shader': bool(comp.get('hue_shader'))}


def main():
    with ProcessPoolExecutor(6) as pool: rows = dict(pool.map(cues, DESCS))
    json.dump(rows, open(Path(__file__).with_name('baseline-cues.json'), 'w'), indent=1)
    stats = {k: [0, 0] for k in ('steady', 'detail', 'shapes', 'any')}; coloured = 0; nocue = 0
    for name, c in rows.items():
        f = R / (name + '.json')
        if 'error' in c or not f.exists(): continue
        ref = json.load(open(f))
        if ref.get('status') != 'measured' or ref['coloured_share'] <= .2: continue
        coloured += 1; top = list(ref['hue_shares'])[:2]; hit_any = False; had = False
        for k in ('steady', 'detail', 'shapes'):
            v = c[k]; lead = v if isinstance(v, str) else (v[0] if v else None)
            if lead and lead != 'grayscale':
                had = True; stats[k][1] += 1
                if lead in top: stats[k][0] += 1; hit_any = True
        if had: stats['any'][1] += 1; stats['any'][0] += hit_any
        else: nocue += 1
    print('coloured presets', coloured, 'with no static hue cue', nocue)
    for k, (hit, n) in stats.items(): print(f'{k:7s} cue present {n:4d}  leading hue in ruler top-2: {hit}/{n} ({hit / max(n, 1):.0%})')


if __name__ == '__main__':
    main()
