"""Static display_palette vs engine ruler hues on the 200 group-measure descriptions (static only)."""
import json, sys, glob, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
R = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
def one(path):
    import warnings; warnings.filterwarnings('ignore')
    from preset_recipe import build_recipe
    try: return Path(path).stem, build_recipe(json.load(open(path)))['render']['display_palette']
    except Exception as e: return Path(path).stem, {'error': str(e)[:100]}
if __name__ == '__main__':
    with ProcessPoolExecutor(6) as pool: rows = dict(pool.map(one, sorted(glob.glob(str(W / 'build/group-measure-2026-10-13/desc-d7ad1519/*.json')))))
    json.dump(rows, open(Path(__file__).with_name(sys.argv[1] if len(sys.argv) > 1 else 'palette.json'), 'w'), indent=1)
    n = cov = hit = top1 = 0
    for name, p in rows.items():
        f = R / (name + '.json')
        if 'error' in p or not f.exists(): continue
        ref = json.load(open(f))
        if ref.get('status') != 'measured' or ref['coloured_share'] <= .2: continue
        n += 1; lead = next(iter(p['hue_shares']), None)
        if lead: cov += 1; hit += lead in list(ref['hue_shares'])[:2]; top1 += lead == next(iter(ref['hue_shares']))
    print(f'coloured {n}: palette present {cov} ({cov/n:.0%}); leading hue in ruler top-2 {hit}/{cov} ({hit/max(cov,1):.0%}); exact top-1 {top1}/{cov}; overall correct {hit/n:.0%}')
