"""Prototype static probe: expected screen motion from the evaluated mesh controls.

The frame program is stepped to t = 5 s (deterministic work budget, as the other probes) under neutral audio (bands 1)
and a beat transient (bass/mid/treb 2 over averages 1). From the resulting per-frame controls (zoom, zoomexp, rot,
cx, cy, sx, sy, dx, dy, warp) the MilkDrop backward mesh map is applied to a 32x18 grid in closed form
(u' = c + R(-rot)((u - c) / (zoom^(r^zoomexp) * s)) - d, aspect-corrected), and the mean displacement per frame
(screen widths) is reported for both states plus their difference (pulsing). Warp amplitude is reported as a control
value only. No frames are rendered; this is the per-step map, not visible optical flow."""
import json, gzip, base64, sys, os, pickle, warnings, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
STATES = {'neutral': dict(bass=1., mid=1., treb=1., bass_att=1., mid_att=1., treb_att=1.),
          'transient': dict(bass=2., mid=2., treb=2., bass_att=1., mid_att=1., treb_att=1.)}
DEFAULTS = {'zoom': 1., 'zoomexp': 1., 'rot': 0., 'cx': .5, 'cy': .5, 'sx': 1., 'sy': 1., 'dx': 0., 'dy': 0., 'warp': 0.}
def displacement(c, aspect=270 / 480):
    import numpy as np
    u, v = np.meshgrid((np.arange(32) + .5) / 32, (np.arange(18) + .5) / 18)
    x, y = (u - .5) * 2, (v - .5) * 2 * aspect
    r = np.sqrt(x * x + y * y) / math.sqrt(1 + aspect * aspect)
    zoom = float(c['zoom']); zexp = float(c['zoomexp'])
    if not (zoom > 0 and math.isfinite(zoom) and math.isfinite(zexp)): return None
    z = zoom ** np.power(np.maximum(r, 1e-6), zexp)
    cx, cy = (c['cx'] - .5) * 2, (c['cy'] - .5) * 2 * aspect
    px, py = (x - cx) / (z * c['sx']), (y - cy) / (z * c['sy'])
    a = -c['rot']; qx, qy = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    nx, ny = qx + cx - 2 * c['dx'], qy + cy - 2 * c['dy'] * aspect
    d = np.sqrt((nx - x) ** 2 + (ny - y) ** 2) / 2  # in screen widths
    return float(np.mean(d[np.isfinite(d)])) if np.isfinite(d).any() else None
def probe(summary):
    from feedback_equilibrium import _stage_controls
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    out = {}; vals = {}
    for state, bands in STATES.items():
        ctl = _stage_controls(facts, bands, (5.,))[5.]
        c = {k: float(ctl[k]) if isinstance(ctl.get(k), (int, float)) and math.isfinite(ctl[k]) else v for k, v in DEFAULTS.items()}
        vals[state] = displacement(c)
        if state == 'neutral':
            for k in ('zoom', 'rot', 'dx', 'dy', 'warp'): out['ctlflow:neutral_' + k] = c[k]
    if vals['neutral'] is not None:
        out['ctlflow:disp_neutral'] = vals['neutral']
        if vals['transient'] is not None:
            out['ctlflow:disp_transient'] = vals['transient']; out['ctlflow:disp_pulse'] = abs(vals['transient'] - vals['neutral'])
    return out
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
    if len(sys.argv) > 3: paths = paths[:int(sys.argv[3])]
    rows = {}
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, row in enumerate(pool.map(one, paths, chunksize=8)):
            if row: rows[row[0]] = row[1]
            if i % 2000 == 0: print(i, len(rows), flush=True)
    pickle.dump(rows, open(sys.argv[1], 'wb')); print('done', len(rows), flush=True)
