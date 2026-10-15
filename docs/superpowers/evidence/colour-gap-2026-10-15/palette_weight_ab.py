"""Palette weight A/B (static): recipes for the 200 group descriptions with OUT-OF-FOLD calibrated hue shares
substituted, then display_palette re-pooled for several calibrated_hue weights. Leading hue vs ruler top-2/top-1."""
import json, sys, glob, warnings, copy
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
R = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
import os; OOF = json.load(open(W / 'build/calibration-2026-10-14' / os.environ.get('OOF', 'oof-r14g.json')))['predictions']
def one(path):
    import warnings; warnings.filterwarnings('ignore')
    from preset_recipe import build_recipe
    try: return Path(path).stem, build_recipe(json.load(open(path)))
    except Exception as e: return Path(path).stem, None
if __name__ == '__main__':
    import preset_recipe
    held = len(sys.argv) > 1 and sys.argv[1] == 'checkpoints'
    group = sorted(glob.glob(str(W / 'build/group-measure-2026-10-13/desc-d7ad1519/*.json')))
    if held:  # held-out: checkpoint descriptions not in the 200 group set, latest per preset
        names = {Path(p).stem for p in group}; paths = {}
        for d in sorted(glob.glob(str(W / 'build/checkpoint-r*/v1/description.json'))):
            if not (Path(d).parents[1] / 'selection.json').exists(): continue
            preset = json.load(open(Path(d).parents[1] / 'selection.json'))['preset'][:-5]
            if preset not in names: paths[preset] = d
        with ProcessPoolExecutor(8) as pool: recipes = dict(zip(paths, (r for _, r in pool.map(one, paths.values()))))
    else:
        with ProcessPoolExecutor(8) as pool: recipes = dict(pool.map(one, group))
    base = dict(preset_recipe.PALETTE_WEIGHTS)
    cases = [(name, r) for name, r in recipes.items() if r and (R / (name + '.json')).exists() and name + '.milk' in OOF]
    refs = {name: json.load(open(R / (name + '.json'))) for name, _ in cases}
    for name, r in cases:
        st = r['display_estimate']['statistics']
        for k, v in OOF[name + '.milk'].items():
            if k.startswith('hue_share_'): st[k] = {'value': v}
    for w in (0., 3., 6., 12., 24., 1e6):
        preset_recipe.PALETTE_WEIGHTS.update(base, calibrated_hue=w)
        n = hit = top1 = 0
        for name, r in cases:
            ref = refs[name]
            if ref.get('status') != 'measured' or ref['coloured_share'] <= .2: continue
            lead = next(iter(preset_recipe.display_palette(r)['hue_shares']), None)
            n += 1; hit += lead in list(ref['hue_shares'])[:2]; top1 += lead == next(iter(ref['hue_shares']))
        print(f'calibrated weight {w:g}: coloured {n}; leading in top-2 {hit/n:.1%}; top-1 {top1/n:.1%}', flush=True)
