"""Prototype static probe: warp detail gain (spatial perturbation loop gain) per corpus preset.

The warp stage is evaluated once (t = 5 s, bands 1, frame program stepped under the deterministic work budget as the
existing probes do) on a dim grey canvas (level 0.1) carrying small zero-mean grey noise (amplitude 0.02, smoothed at
1 and 2 px), at 96x54 with matching blur inputs. Detail gain = std(output luma - its 9x9 local mean) /
std(input luma - its local mean). Above 1, fine structure grows each frame until it clips (pattern-forming feedback),
whatever the flat-field gain. No frames are rendered or iterated. Output: pickle {preset: {column: value}}."""
import json, gzip, base64, sys, os, pickle, warnings, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def local_detail(l):
    import numpy as np
    from scipy.ndimage import uniform_filter
    return l - uniform_filter(l, 9, mode='wrap')
def probe(summary):
    import numpy as np
    from scipy.ndimage import gaussian_filter
    import prediction_illustration as P
    from feedback_equilibrium import _stage_controls
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    program = (((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('warp') or {})
    if program.get('status') != 'exported': return {}
    w, h = 96, 54; rng = np.random.default_rng(0)
    noise = gaussian_filter(rng.standard_normal((h, w)), 1, mode='wrap') + .5 * gaussian_filter(rng.standard_normal((h, w)), 2, mode='wrap')
    noise = noise / noise.std() * .02
    image = np.repeat((.1 + noise)[..., None], 3, axis=2).astype(np.float32)
    cols, rows = np.meshgrid((np.arange(w) + .5) / w, (np.arange(h) + .5) / h)
    uv = np.stack([cols, rows, cols, rows], axis=-1).astype(np.float32)
    bands = {n: 1. for n in ('bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att')}
    controls = _stage_controls(facts, bands, (5.,))[5.]
    try:
        out = P._evaluate_stage(program['program'], image, uv, 5., 30., bands, controls=dict(controls), stage='warp')
    except Exception:
        return {}
    out = np.where(np.isfinite(out), out, 0.)
    lum = lambda a: .2126 * a[..., 0] + .7152 * a[..., 1] + .0722 * a[..., 2]
    gin = local_detail(lum(image)).std(); gout = local_detail(lum(np.clip(out, 0, 1))).std()
    return {'detail:warp_detail_gain': float(gout / gin) if gin > 0 else None, 'detail:warp_flat_out': float(lum(np.clip(out, 0, 1)).mean())}
def one(path):
    warnings.filterwarnings('ignore')
    try:
        d = json.load(open(path)); s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        return d['name'], probe(s)
    except Exception:
        return None
if __name__ == '__main__':
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    paths = sorted(str(R / n) for n in os.listdir(R))
    if len(sys.argv) > 3: paths = [p for p in paths if any(k in json.load(open(p))['name'] for k in sys.argv[3].split('|'))]
    rows = {}
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, row in enumerate(pool.map(one, paths, chunksize=8)):
            if row: rows[row[0]] = row[1]
            if i % 1000 == 0: print(i, len(rows), flush=True)
    pickle.dump(rows, open(sys.argv[1], 'wb')); print('done', len(rows), flush=True)
