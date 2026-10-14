"""Held-out check: display_palette on checkpoint presets r129-r205 (not in the 200 set), against the ruler."""
import json, sys, glob, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
R = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
group = {Path(p).stem for p in glob.glob(str(W / 'build/group-measure-2026-10-13/desc-d7ad1519/*.json'))}
def one(n):
    import warnings; warnings.filterwarnings('ignore')
    from preset_recipe import build_recipe
    C = W / f'build/checkpoint-r{n}'
    try:
        sel = json.load(open(C / 'selection.json')); r = build_recipe(json.load(open(C / 'v1/description.json')))
        st = (r['render']['feedback'].get('steady_state') or {}).get('hue_family')
        return n, sel, r['render']['display_palette'], st
    except Exception as e: return n, None, {'error': str(e)[:80]}, None
if __name__ == '__main__':
    with ProcessPoolExecutor(6) as pool: rows = list(pool.map(one, range(129, 206)))
    n = cov = hit = st_hit = 0
    for k, sel, p, st in rows:
        if not sel or 'error' in p or sel['preset'][:-5] in group: continue
        f = R / (sel['preset'][:-5] + '.json')
        if not f.exists(): continue
        ref = json.load(open(f))
        if ref.get('status') != 'measured' or ref['coloured_share'] <= .2: continue
        n += 1; top = list(ref['hue_shares'])[:2]; lead = next(iter(p['hue_shares']), None)
        if lead: cov += 1; hit += lead in top
        st_hit += bool(st and st != 'grayscale' and st in top)
    print(f'held-out coloured {n}: palette present {cov}; leading hue in ruler top-2 {hit}/{cov}; overall {hit/max(n,1):.0%}  (steady-state cue alone: {st_hit/max(n,1):.0%})')
