"""Prototype static probe: per-frame control series under the declared reference band sequence.

The exported frame program (the preset's per-frame equations; scalar EEL, nothing rendered) is stepped for 300
frames with the declared checkpoint bands (tools/milk-analyzer/fixtures/reference-band-sequence-2026-10-12.json),
under a deterministic work budget. Over frames 60-299 (the ruler window) it reports, per brightness/motion control,
the spread (std), mean absolute change per frame and the share of frames with a large change; boolean display flags
report their flip rate; the closed-form mesh displacement per frame (as control_flow_corpus.py) gives mean and std.
These are the control values the source equations produce for that audio, not rendered frames."""
import json, gzip, base64, sys, os, pickle, warnings, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer')); sys.path.insert(0, str(Path(__file__).resolve().parent))
BANDS = json.load(open(W / 'tools/milk-analyzer/fixtures/reference-band-sequence-2026-10-12.json'))['frames']
CONTINUOUS = {'zoom': .02, 'rot': .02, 'dx': .005, 'dy': .005, 'sx': .02, 'sy': .02, 'warp': .1, 'decay': .02, 'gamma': .2,
              'echo_alpha': .1, 'echo_zoom': .05, 'wave_a': .2, 'wave_r': .2, 'wave_g': .2, 'wave_b': .2, 'ob_a': .2, 'ib_a': .2, 'mv_a': .2}
FLAGS = ('darken', 'invert', 'brighten', 'solarize', 'additivewave', 'wave_usedots', 'wave_thick')
BUDGET = 6e6
def probe(summary):
    import numpy as np
    import prediction_illustration as P
    from eel_memory import WorkBudget
    from feedback_equilibrium import _program_nodes
    from control_flow_corpus import displacement, DEFAULTS
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    frame = (facts.get('/analysis/visual_description/stage_programs') or {}).get('frame') or {}
    if frame.get('status') != 'exported' or not (frame.get('state') or frame.get('outputs')): return {}
    constants = P._render_constants(facts.get('/analysis/visual_description/static_behaviour/context') or {})
    budget = WorkBudget(BUDGET); stepper = P._FrameStepper(frame, constants=constants, deadline=budget)
    cost = max(1, _program_nodes(frame.get('state')) + _program_nodes(frame.get('outputs')))
    series = []
    for k in range(300):
        if budget.left < cost: break
        budget.left -= cost
        bands = {n: float(BANDS[min(k, len(BANDS) - 1)][n]) for n in ('bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att')}
        out = stepper.step(float(np.float32((k + 1) / 30.)), 30., bands, k)
        series.append({n: v for n, v in {**out, **(stepper.start or {})}.items() if isinstance(v, (int, float)) and math.isfinite(v)})
    res = {'series:frames_stepped': float(len(series))}
    window = series[60:] if len(series) > 90 else series
    if len(window) < 30: return res
    for name, jump in CONTINUOUS.items():
        vals = np.array([s.get(name, np.nan) for s in window], float)
        if np.isnan(vals).all(): continue
        vals = vals[np.isfinite(vals)]
        if len(vals) < 2: continue
        d = np.abs(np.diff(vals))
        res[f'series:{name}/std'] = float(vals.std()); res[f'series:{name}/mean_step'] = float(d.mean()); res[f'series:{name}/jump_share'] = float(np.mean(d > jump))
    for name in FLAGS:
        vals = np.array([1. if s.get(name, 0) else 0. for s in window])
        if vals.any(): res[f'series:{name}/flip_rate'] = float(np.mean(np.diff(vals) != 0)); res[f'series:{name}/on_share'] = float(vals.mean())
    disp = []
    for s in window[::3]:
        c = {k: float(s[k]) if isinstance(s.get(k), (int, float)) else v for k, v in DEFAULTS.items()}
        d = displacement(c)
        if d is not None: disp.append(d)
    if disp: res['series:disp/mean'] = float(np.mean(disp)); res['series:disp/std'] = float(np.std(disp))
    return res
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
