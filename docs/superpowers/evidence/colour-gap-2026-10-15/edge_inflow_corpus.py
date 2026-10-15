"""Prototype static probe: edge inflow share of the warp (how much of the next canvas is read from the screen edge).

The warp stage is evaluated once (t = 5 s, bands 1, deterministic frame-program stepping as the other probes) on an
indicator canvas: 1 in the outer band (max(|x|,|y|) >= 0.9 in NDC, where borders are drawn) and 0 inside, at 96x54.
The mean output is the share of the next canvas that comes from the edge band, including clamped reads of samples
that leave the frame. A map that throws samples off screen (e.g. a Julia iteration with c outside the Mandelbrot set)
reads almost everything from the edge, so the canvas takes the edge's (border) colour. No frames are iterated."""
import json, gzip, base64, sys, os, pickle, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def probe(summary):
    import numpy as np
    import prediction_illustration as P
    from feedback_equilibrium import _stage_controls
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    program = (((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('warp') or {})
    if program.get('status') != 'exported': return {}
    w, h = 96, 54
    cols, rows = np.meshgrid((np.arange(w) + .5) / w, (np.arange(h) + .5) / h)
    band = (np.maximum(np.abs(2 * cols - 1), np.abs(2 * rows - 1)) >= .9).astype(np.float32)
    image = np.repeat(band[..., None], 3, axis=2)
    uv = np.stack([cols, rows, cols, rows], axis=-1).astype(np.float32)
    bands = {n: 1. for n in ('bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att')}
    controls = _stage_controls(facts, bands, (5.,))[5.]
    try:
        out = P._evaluate_stage(program['program'], image, uv, 5., 30., bands, controls=dict(controls), stage='warp')
    except Exception:
        return {}
    out = np.clip(np.where(np.isfinite(out), out, 0.), 0, 1)
    l = .2126 * out[..., 0] + .7152 * out[..., 1] + .0722 * out[..., 2]
    inner = band == 0
    return {'edge:inflow_share': float(l.mean()), 'edge:inflow_into_interior': float(l[inner].mean()), 'edge:band_share': float(band.mean())}
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
            if i % 2000 == 0: print(i, len(rows), flush=True)
    pickle.dump(rows, open(sys.argv[1], 'wb')); print('done', len(rows), flush=True)
