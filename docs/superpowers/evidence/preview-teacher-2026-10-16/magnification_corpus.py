"""Static probe: area magnification of the feedback warp (forward-map Jacobian), per corpus preset.

The mesh backward map (prediction_illustration._backward_map, per pixel at 96x54) is evaluated at t = 5 s with the
frame-program state stepped under neutral bands (feedback_equilibrium._stage_controls, deterministic budget). Area
magnification m = 1 / |det J_backward| (how much a drawn pixel's area grows per feedback step). Columns: median and
mean (capped at 10) of m over the screen, the share of the screen with m > 1.05, and m at the screen centre. The
equilibrium's spread bound assumes area-preserving transport; a warp with m * gain > 1 grows drawn content until it
fills the screen. No frames are rendered."""
import json, gzip, base64, sys, os, pickle, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def probe(summary):
    import numpy as np
    import prediction_illustration as P
    from feedback_equilibrium import _stage_controls
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    mesh = facts.get('/analysis/visual_description/static_behaviour/mesh_field') or {}
    bands = {b: 1. for b in ('bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att')}
    stage = _stage_controls(facts, bands, (5.,))[5.]
    saved = dict(P._TERM_CONTEXT)
    try:
        P._TERM_CONTEXT.clear(); P._TERM_CONTEXT.update(stage=dict(stage), rng=np.random.default_rng(0), bands=bands)
        sample = P._backward_map(mesh, 96, 54, grid=None)
        if sample is None: return {}
        with np.errstate(all='ignore'):
            mx, my = (np.asarray(m, np.float64) for m in sample(5.))
            dxdy, dxdx = np.gradient(mx); dydy, dydx = np.gradient(my)
            det = np.abs(dxdx * dydy - dxdy * dydx); m = np.where(det > 1e-9, 1 / det, 10.)
            m = np.where(np.isfinite(m), np.minimum(m, 10.), 10.)
        return {'mag:median': float(np.median(m)), 'mag:mean_cap10': float(m.mean()), 'mag:share_gt105': float(np.mean(m > 1.05)),
                'mag:centre': float(m[27, 48])}
    except Exception:
        return {}
    finally:
        P._TERM_CONTEXT.clear(); P._TERM_CONTEXT.update(saved)
def one(path):
    warnings.filterwarnings('ignore')
    try:
        d = json.load(open(path)); s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        return d['name'], probe(s)
    except Exception:
        return None
if __name__ == '__main__':
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    paths = sorted(str(R / n) for n in os.listdir(R)); rows = {}
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, row in enumerate(pool.map(one, paths, chunksize=8)):
            if row: rows[row[0]] = row[1]
            if i % 2000 == 0: print(i, flush=True)
    pickle.dump(rows, open(sys.argv[1], 'wb')); print('done', len(rows), flush=True)
