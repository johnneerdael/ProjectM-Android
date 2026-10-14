"""Static audio-to-brightness proxy vs ruler brightness jumps (200 group set; static only)."""
import json, sys, glob, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
R = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
BRIGHT = ('colour', 'opacity', 'alpha', 'decay', 'gamma', 'echo', 'border', 'brighten', 'invert')
def one(path):
    import warnings; warnings.filterwarnings('ignore')
    from preset_recipe import build_recipe
    try: r = build_recipe(json.load(open(path)))
    except Exception as e: return Path(path).stem, None
    best = 0.; n = 0; total = 0
    for L in r['render']['layers']:
        for route in L.get('audio') or []:
            total += 1; sen = route.get('sensitivity')
            if not sen: continue
            n += 1
            if any(k in str(route.get('target')) for k in BRIGHT): best = max(best, sen['typical_frame_jump'])
    return Path(path).stem, {'proxy': best, 'routes': total, 'resolved': n}
if __name__ == '__main__':
    with ProcessPoolExecutor(6) as pool: rows = dict(pool.map(one, sorted(glob.glob(str(W / 'build/group-measure-2026-10-13/desc-d7ad1519/*.json')))))
    json.dump(rows, open(Path(__file__).with_name('strobe-proxy.json'), 'w'), indent=1)
    import numpy as np
    from scipy.stats import spearmanr
    xs, ys, res, tot = [], [], 0, 0
    for name, v in rows.items():
        f = R / (name + '.json')
        if not v or not f.exists(): continue
        ref = json.load(open(f)); xs.append(v['proxy']); ys.append(ref['global_brightness_jumps_per_10s']); res += v['resolved']; tot += v['routes']
    xs, ys = np.array(xs), np.array(ys)
    print(f'routes resolved {res}/{tot}; proxy vs ruler jumps Spearman {spearmanr(xs, ys).statistic:.3f} (n={len(xs)})')
    for thr in (.0, .01, .05, .1):
        sel = xs > thr; print(f'proxy>{thr}: n={int(sel.sum())} share flicker>=10: {np.mean(ys[sel] >= 10):.0%}; proxy<={thr}: share flicker>=10 {np.mean(ys[~sel] >= 10):.0%}')
