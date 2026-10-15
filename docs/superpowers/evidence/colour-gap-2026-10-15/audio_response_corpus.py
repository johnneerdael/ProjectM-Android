"""Prototype static probe: displayed-brightness response to audio, per corpus preset.

For three declared audio states (neutral: all bands 1; transient: bass/mid/treb 2 over averages 1, which fires
above(bass, bass_att)-style beat detectors; quiet: bands 0.3 over averages 1) the frame program is stepped to t = 5 s
under the deterministic work budget (as the existing probes do) and each exported stage program (warp, composite) is
evaluated once on a flat mid-grey canvas. Columns: stage output luma per state and the largest change from neutral,
plus the change of audio-sensitive frame controls (decay, gamma, echo, wave/border alpha, zoom, rot). No frames are
rendered and no feedback is iterated. Output: pickle {preset: {column: value}} for --extra-columns."""
import json, gzip, base64, sys, os, pickle, warnings, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
STATES = {'neutral': dict(bass=1., mid=1., treb=1., bass_att=1., mid_att=1., treb_att=1.),
          'transient': dict(bass=2., mid=2., treb=2., bass_att=1., mid_att=1., treb_att=1.),
          'quiet': dict(bass=.3, mid=.3, treb=.3, bass_att=1., mid_att=1., treb_att=1.)}
CONTROLS = ('decay', 'gamma', 'echo_alpha', 'echo_zoom', 'wave_a', 'ob_a', 'ib_a', 'zoom', 'rot', 'warp', 'darken', 'invert', 'brighten', 'solarize')
def luma(rgb): return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
def probe(summary):
    import numpy as np
    import prediction_illustration as P
    from feedback_equilibrium import _stage_controls
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    stages = ((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {})
    width, height = 48, 27; time = 5.
    cols, rows = np.meshgrid((np.arange(width) + .5) / width, (np.arange(height) + .5) / height)
    uv = np.stack([cols, rows, cols, rows], axis=-1).astype(np.float32)
    image = np.full((height, width, 3), .5, np.float32)
    out = {}; values = {}
    for state, bands in STATES.items():
        controls = _stage_controls(facts, bands, (time,))[time]
        values[state] = {'controls': controls}
        for stage in ('warp', 'composite'):
            program = stages.get(stage) or {}
            if program.get('status') != 'exported': continue
            try:
                res = P._evaluate_stage(program['program'], image, uv, time, 30., bands, controls=dict(controls), stage=stage)
            except Exception:
                continue
            res = np.where(np.isfinite(res), res, 0.)
            values[state][stage] = luma(np.clip(res, 0, 1).reshape(-1, 3).mean(0))
    for stage in ('warp', 'composite'):
        if all(stage in values[s] for s in STATES):
            for s in STATES: out[f'audio:{stage}_luma/{s}'] = float(values[s][stage])
            out[f'audio:{stage}_luma_change'] = float(max(abs(values[s][stage] - values['neutral'][stage]) for s in ('transient', 'quiet')))
    for name in CONTROLS:
        vs = [values[s]['controls'].get(name) for s in STATES]
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in vs):
            out[f'audio:control_change/{name}'] = float(max(abs(vs[1] - vs[0]), abs(vs[2] - vs[0])))
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
    paths = sorted(str(R / n) for n in os.listdir(R)); rows = {}
    if len(sys.argv) > 3: paths = paths[:int(sys.argv[3])]
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, row in enumerate(pool.map(one, paths, chunksize=8)):
            if row: rows[row[0]] = row[1]
            if i % 1000 == 0: print(i, len(rows), flush=True)
    pickle.dump(rows, open(sys.argv[1], 'wb')); print('done', len(rows), flush=True)
