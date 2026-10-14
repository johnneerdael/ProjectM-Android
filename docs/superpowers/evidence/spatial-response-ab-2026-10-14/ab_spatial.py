"""A/B: does the warp's spatial power response add information to the calibrated display model? (diagnostic)

Stage 1 (cached): current static descriptor rows for every corpus summary (fit_display_calibration._descriptor_row).
Stage 2 (cached): spatial response of the warp stage at reference scale: out(0.5 + noise) - out(0.5) for a
white-noise probe, radially binned power ratio per wavelength band. Static: one closed-form stage evaluation
pair, no frames stepped.
Stage 3: identical HistGradientBoosting 5-fold CV with and without the spatial columns; out-of-fold Spearman.
"""
import json, os, pickle, sys, time, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
W = Path(__file__).resolve().parents[2]; TOOLS = W / 'tools/milk-analyzer'; sys.path.insert(0, str(TOOLS))
OUT = Path(__file__).parent
CORPUS = W / 'build/preset-corpus/corpus-understanding-9606-r13/results'
RULER = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
EXCLUDE = [W / 'build/validation-activity-2026-10-11/heldout-observations.json', W / 'build/validation-activity-2026-10-11/observations.json']
EDGES = (0., 1 / 128, 1 / 32, 1 / 8, 1 / 3, .75)  # cycles per pixel: wavelengths >128, 32-128, 8-32, 3-8, <3 px
BANDS = ('gt128', '32_128', '8_32', '3_8', 'lt3')


def descriptor_row(path):
    import fit_display_calibration as F
    return F._descriptor_row(path)


def spatial(path, level=.5, amp=.05, size=(480, 270)):
    import numpy as np, prediction_illustration as P, feedback_equilibrium as E
    try:
        import base64, gzip
        record = json.loads(Path(path).read_text())
        if record.get('status') != 'computed' or not record.get('summary_gzip_base64'): return Path(path).stem, None
        name = record['name']; summary = json.loads(gzip.decompress(base64.b64decode(record['summary_gzip_base64'])))
        facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
        prog = (((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('warp') or {})
        if prog.get('status') != 'exported': return name, None
        t = time.perf_counter()
        w, h = size; cols, rows = np.meshgrid((np.arange(w) + .5) / w, (np.arange(h) + .5) / h)
        uv = np.stack([cols, rows, cols, rows], -1).astype(np.float32)
        bands = {k: 1. for k in ('bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att')}
        c = dict(E._stage_controls(facts, bands, (5.,), budget_seconds=.5)[5.])
        noise = np.random.default_rng(0).standard_normal((h, w, 1)).astype(np.float32) * amp
        def run(img):
            o = P._evaluate_stage(prog['program'], img, uv, 5., 30., bands, controls=dict(c), stage='warp')
            return np.clip(np.where(np.isfinite(o), o, 0), 0, 1).astype(np.float64)
        flat = run(np.full((h, w, 3), level, np.float32)); probe = run(np.clip(level + np.repeat(noise, 3, -1), 0, 1))
        delta = (probe - flat).mean(-1); delta -= delta.mean(); n = noise[..., 0].astype(np.float64)
        fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.rfftfreq(w)[None, :]; r = np.sqrt(fx ** 2 + fy ** 2)
        So = np.abs(np.fft.rfft2(delta)) ** 2; Si = np.abs(np.fft.rfft2(n - n.mean())) ** 2
        row = {}
        for key, a, b in zip(BANDS, EDGES, EDGES[1:]):
            m = (r >= a) & (r < b); row['spatial:log_power_ratio/' + key] = float(np.log10(max(So[m].sum(), 1e-12) / max(Si[m].sum(), 1e-12)))
        row['spatial:log_power_ratio/all'] = float(np.log10(max(So.sum(), 1e-12) / max(Si.sum(), 1e-12)))
        row['spatial:self_texture_std'] = float(flat.mean(-1).std())  # input-independent spatial content
        row['spatial:seconds'] = time.perf_counter() - t
        return name, row
    except Exception:  # noqa: BLE001 - an unevaluable program leaves the response missing
        return Path(path).stem, None


def main():
    paths = sorted(CORPUS / n for n in os.listdir(CORPUS))
    cache = OUT / 'descriptors-r13.pkl'
    if not cache.exists():
        with ProcessPoolExecutor(6) as pool: rows = [r for r in pool.map(descriptor_row, paths, chunksize=32) if r is not None]
        pickle.dump(rows, open(cache, 'wb')); print('descriptors', len(rows), flush=True)
    rows = pickle.load(open(cache, 'rb'))
    scache = OUT / 'spatial-r13.pkl'
    if not scache.exists():
        with ProcessPoolExecutor(6) as pool: sp = dict(pool.map(spatial, paths, chunksize=16))
        pickle.dump(sp, open(scache, 'wb')); print('spatial', sum(v is not None for v in sp.values()), flush=True)
    sp = pickle.load(open(scache, 'rb'))
    secs = sorted(v['spatial:seconds'] for v in sp.values() if v)
    print('spatial seconds median', round(secs[len(secs) // 2], 3), 'p90', round(secs[int(len(secs) * .9)], 3), 'max', round(secs[-1], 3))
    import numpy as np
    from scipy.stats import spearmanr
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import KFold
    import fit_display_calibration as F
    labels = {}
    for n in os.listdir(RULER):
        row = json.loads((RULER / n).read_text())
        if row.get('status') == 'measured': labels[row['preset']] = row
    excluded = set()
    for p in EXCLUDE:
        d = json.loads(p.read_text()); excluded |= set(d if isinstance(d, list) else d)
    names = [n for n, _ in rows]; base = [r for _, r in rows]
    def matrix(extra):
        rs = [dict(r, **({k: v for k, v in (sp.get(n) or {}).items() if k != 'spatial:seconds'} if extra else {})) for n, r in zip(names, base)]
        counts = {}
        for r in rs:
            for k in r: counts[k] = counts.get(k, 0) + 1
        cols = sorted(k for k, c in counts.items() if c >= len(rs) * .01); idx = {k: i for i, k in enumerate(cols)}
        X = np.full((len(rs), len(cols)), -1e9)
        for i, r in enumerate(rs):
            for k, v in r.items():
                j = idx.get(k)
                if j is not None and np.isfinite(v): X[i, j] = max(-1e30, min(1e30, v))
        return X, cols
    pos = {n: i for i, n in enumerate(names)}; report = {}
    for tag, extra in (('base', False), ('spatial', True)):
        X, cols = matrix(extra); report[tag] = {'columns': len(cols)}
        for target, transform in F.TARGETS.items():
            fit = [n for n in names if n in labels and labels[n].get(target) is not None and n not in excluded]
            y = np.array([F._transform(labels[k][target], transform) for k in fit]); Xf = X[[pos[k] for k in fit]]; oof = np.zeros(len(fit))
            for tr, te in KFold(5, shuffle=True, random_state=11).split(Xf):
                oof[te] = HistGradientBoostingRegressor(max_iter=250, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=20,
                                                        l2_regularization=1., random_state=7).fit(Xf[tr], y[tr]).predict(Xf[te])
            report[tag][target] = round(float(spearmanr(oof, y).statistic), 4)
        print(tag, report[tag], flush=True)
    (OUT / 'ab-spatial-report.json').write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
