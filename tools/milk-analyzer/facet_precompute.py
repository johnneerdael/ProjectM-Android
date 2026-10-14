"""Offline facet statistics from full-resolution static predictions (owner decision 2026-10-14).

Reads preset summaries from a corpus_understanding results folder, predicts 300 frames at 480x270 with the
declared reference audio (prediction_illustration, source facts only) and measures them with the engine
ruler's statistics (frames 60-299). Presets whose prediction depends on per-load randomness (detected by
comparing two seeds on a short low-resolution run) are averaged over several seeds, as the engine draws
anew at every load. Output: one JSON per preset plus the measured statistics; nothing runs on a device.
"""
import argparse, base64, gzip, importlib.util, json, os, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

POLICY = 'static-prediction-facet-statistics-v1'
FRAMES, WIDTH, HEIGHT, FPS = 300, 480, 270, 30
SEEDS = (1, 2, 3)
TARGETS = ('mean_luminance', 'mean_abs_frame_difference', 'mean_flow_screen_widths_per_s',
           'global_brightness_jumps_per_10s', 'mean_saturation', 'warm_cool')


def _summary(row):
    if row.get('summary_gzip_base64'):return json.loads(gzip.decompress(base64.b64decode(row['summary_gzip_base64'])))
    return row.get('summary')


def _frames(summary, audio, seed, width, height, count):
    import numpy as np
    from prediction_illustration import illustrate_field
    frames = []
    image, _, limits = illustrate_field(summary, time=count / FPS, fps=FPS, history_steps=count, audio=audio, viewport=[width, height], seed=seed,
                                        frame_callback=lambda t, im: frames.append((np.clip(np.nan_to_num(im), 0, 1) * 255 + .5).astype(np.uint8)))
    if len(frames) < count:frames = [(np.clip(np.nan_to_num(np.asarray(image, np.float32)), 0, 1) * 255 + .5).astype(np.uint8)] * count
    return np.array(frames, np.uint8), limits


def depends_on_seed(summary, audio):
    """True when two seeds give different frames on a short, small run (per-load randomness reaches the output)."""
    import numpy as np
    a, _ = _frames(summary, audio, 1, 96, 54, 30)
    b, _ = _frames(summary, audio, 2, 96, 54, 30)
    return not np.array_equal(a, b)


def preset_statistics(summary, audio, measure):
    started = time.perf_counter()
    stochastic = depends_on_seed(summary, audio)
    seeds = SEEDS if stochastic else (None,)
    runs = []
    with tempfile.TemporaryDirectory() as work:
        for seed in seeds:
            frames, limits = _frames(summary, audio, seed, WIDTH, HEIGHT, FRAMES)
            path = os.path.join(work, 'f.u8'); frames.tofile(path)
            runs.append({'seed': seed, **measure(path)})
    mean = {}
    for key in TARGETS:
        values = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
        mean[key] = sum(values) / len(values) if values else None
    return {'policy': POLICY, 'status': 'predicted', 'depends_on_seed': stochastic, 'seeds': list(seeds), 'statistics': mean,
            'runs': runs, 'limitations': limits, 'seconds': round(time.perf_counter() - started, 2),
            'uses_rendered_images': False, 'uses_engine_execution': False}


_STATE = {}


def _init(ruler_path):
    spec = importlib.util.spec_from_file_location('ruler', ruler_path); ruler = importlib.util.module_from_spec(spec); spec.loader.exec_module(ruler)
    _STATE['measure'] = ruler.measure
    here = Path(__file__).resolve().parent
    _STATE['audio'] = json.load(open(here / 'fixtures/reference-band-sequence-2026-10-12.json'))


def _one(task):
    result_path, out_path = task
    try:
        row = json.load(open(result_path)); summary = _summary(row)
        if row.get('status') not in (None, 'computed') or summary is None:
            record = {'policy': POLICY, 'status': 'no_summary', 'name': row.get('name')}
        else:
            record = {'name': row.get('name'), 'sha256': row.get('sha256'), **preset_statistics(summary, _STATE['audio'], _STATE['measure'])}
    except Exception as error:  # noqa: BLE001 - one failing preset is recorded, the run continues
        record = {'policy': POLICY, 'status': 'error', 'error': f'{type(error).__name__}: {error}'[:300]}
    tmp = str(out_path) + '.tmp'; json.dump(record, open(tmp, 'w')); os.replace(tmp, out_path)
    return record.get('status')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, help='corpus_understanding results folder')
    parser.add_argument('output', type=Path)
    parser.add_argument('--ruler', type=Path, required=True, help='native-ruler ruler.py (its measure() only)')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    tasks = [(str(p), args.output / p.name) for p in sorted(args.results.glob('*.json')) if not (args.output / p.name).exists()]
    if args.limit:tasks = tasks[:args.limit]
    print(json.dumps({'event': 'ready', 'pending': len(tasks)}), flush=True)
    done = 0
    with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(str(args.ruler),), max_tasks_per_child=25) as pool:
        for status in pool.map(_one, tasks):
            done += 1
            if done % 50 == 0:print(json.dumps({'event': 'progress', 'completed': done, 'pending': len(tasks)}), flush=True)
    print(json.dumps({'event': 'done', 'completed': done}), flush=True)


if __name__ == '__main__':
    sys.exit(main())
