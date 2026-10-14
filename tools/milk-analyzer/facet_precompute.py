"""Offline facet statistics from full-resolution static predictions (owner decision 2026-10-14).

Reads preset summaries from a corpus_understanding results folder, predicts 300 frames at 480x270 with the
declared reference audio (prediction_illustration, source facts only) and measures them with the engine
ruler's statistics (frames 60-299). Presets whose prediction depends on per-load randomness (detected by
comparing two seeds on a short low-resolution run) are averaged over the cold load and several seeds, as the engine draws
anew at every load. Output: one JSON per preset plus the measured statistics; nothing runs on a device.
"""
import argparse, base64, gzip, importlib.util, json, os, re, sys, tempfile, time
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


def peak_brightness_change(frames, start=60):
    """Largest frame-to-frame change of mean grey from frame `start` (the ruler's grey: 320x180 INTER_AREA,
    Rec.601), the quantity whose 0.08 crossings the ruler counts as global brightness jumps."""
    import cv2
    import numpy as np
    grey = np.array([cv2.cvtColor(cv2.resize(f, (320, 180), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).mean() / 255
                     for f in frames[start:]])
    return float(np.abs(np.diff(grey)).max()) if len(grey) > 1 else 0.


_PER_LOAD = re.compile(r'"op": "rand"|"rand_frame"|"rand_preset"|"_vDiffuse"|"hue_shader"|"canonical_texture": "(?:noise|rand)')


def per_load_random(summary):
    """True when per-load randomness can reach the prediction, read from the source facts: rand calls,
    rand_frame/rand_preset, the composite hue shader (random hue offsets), noise or random textures, or the
    legacy corner tint. No frames are predicted (depends_on_seed is the two-run check it was validated with)."""
    if _PER_LOAD.search(json.dumps(summary)):return True
    for group in (summary.get('facts') or {}).values():
        for fact in group:
            value = fact.get('value')
            if str(fact.get('path', '')).endswith('/legacy_response') and isinstance(value, dict):
                tint = value.get('tint_amount')
                if type(tint) in (int, float) and tint > .001:return True
    return False


def depends_on_seed(summary, audio):
    """True when two seeds give different frames on a short, small run (per-load randomness reaches the output)."""
    import numpy as np
    a, _ = _frames(summary, audio, 1, 96, 54, 30)
    b, _ = _frames(summary, audio, 2, 96, 54, 30)
    return not np.array_equal(a, b)


def preset_statistics(summary, audio, measure):
    started = time.perf_counter()
    stochastic = per_load_random(summary)
    # Seed None is the cold load (projectm-eval's stream from a fresh engine, what a capture right after app
    # start shows); the numbered seeds stand for other stream positions (the app's stream runs on across presets).
    seeds = (None,) + SEEDS if stochastic else (None,)
    runs = []
    with tempfile.TemporaryDirectory() as work:
        for seed in seeds:
            frames, limits = _frames(summary, audio, seed, WIDTH, HEIGHT, FRAMES)
            path = os.path.join(work, 'f.u8'); frames.tofile(path)
            runs.append({'seed': seed, **measure(path), 'peak_brightness_change': peak_brightness_change(frames)})
    mean = {}
    for key in TARGETS:
        values = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
        mean[key] = sum(values) / len(values) if values else None
    # Safety statistic: the worst seed, not the mean (a flash under any per-load draw counts).
    mean['peak_brightness_change'] = max((r.get('peak_brightness_change') or 0.) for r in runs) if runs else None
    return {'policy': POLICY, 'status': 'predicted', 'depends_on_seed': stochastic, 'seeds': list(seeds), 'statistics': mean,
            'random_flash': random_flash(summary, audio), 'random_texture_dependent': random_texture_dependent(summary), 'runs': runs, 'limitations': limits, 'seconds': round(time.perf_counter() - started, 2),
            'uses_rendered_images': False, 'uses_engine_execution': False}


# rand_frame is a fresh uniform draw for every shader every frame (MilkdropShader::LoadVariables). A term that is
# singular in the draw (e.g. 1/length(sin(uv*rand_frame.xy))) can flood the screen on rare draws, which a few
# seeded runs never show. The flash probe integrates the draw's distribution on a log grid instead.
FLASH_JUMP = .08  # the ruler's global brightness jump (mean grey change between frames)
PROBE_SIZE = (160, 90)
_GRID = ((.001, .003), (.01, .027), (.1, .27), (.5, .4), (.9, .27), (.99, .027), (.999, .003))
_COARSE = ((.005, .01), (.5, .98), (.995, .01))


def _grey(image):
    import numpy as np
    image = np.clip(np.nan_to_num(np.asarray(image, np.float32)), 0, 1)
    return float((image[..., :3] @ np.array([.299, .587, .114], np.float32)).mean())


def random_flash_risk(evaluate, draw, base_jump):
    """Probability that this frame's rand_frame draw makes a global brightness jump (> FLASH_JUMP).

    evaluate(vector) gives the frame's display under that draw; draw is the frame's own draw and base_jump the
    displayed grey change into this frame with it. Components whose extremes change the display are active; the
    draw's uniform distribution over them is integrated cell by cell (log grid near 0 and 1, where singular terms
    live; a coarse grid for more than two active components); the others keep their own draw."""
    import itertools
    import numpy as np
    shown = np.asarray(evaluate(draw), np.float32); reference = _grey(shown)
    if not np.isfinite(reference):reference = 0.
    active = []
    for component in range(4):
        # Any change counts: a component can matter only jointly with another (1/|rand.xy| needs both small).
        for value in (.001, .999):
            vector = list(draw); vector[component] = value
            if np.abs(np.nan_to_num(np.asarray(evaluate(vector), np.float32) - shown)).max() > 1e-6:active.append(component);break
    grid = _GRID if len(active) <= 2 else _COARSE
    probability, worst, worst_vector = 0., abs(base_jump), list(draw)
    for cell in itertools.product(grid, repeat=len(active)):
        vector = list(draw); weight = 1.
        for component, (value, width) in zip(active, cell):vector[component] = value; weight *= width
        jump = _grey(evaluate(vector)) - reference + base_jump
        if abs(jump) > FLASH_JUMP:probability += weight
        if abs(jump) > worst:worst, worst_vector = abs(jump), vector
    return {'active_components': active, 'max_jump': round(worst, 4), 'flash_probability_per_frame': round(probability, 6),
            'worst_vector': [round(v, 4) for v in worst_vector]}


def _either(*probabilities):
    """Probability that at least one of independent events happens."""
    miss = 1.
    for p in probabilities:miss *= 1 - p
    return 1 - miss


_RANDOM_TEXTURE = re.compile(r'"canonical_texture": "rand\d\d')


def random_texture_dependent(summary):
    """True when an exported shader program samples a randNN texture: the engine draws that image from the
    texture library at every load, so displayed brightness and flashing depend on the draw (a seeded
    stand-in shows one candidate)."""
    return bool(_RANDOM_TEXTURE.search(json.dumps(summary)))


def random_flash(summary, audio, frames=150):
    """Probe the loudest declared frame in 60..frames-1 of a preset whose shaders read rand_frame.

    The warp and composite draw independently (MilkdropShader::LoadVariables per shader): each stage's draw is
    probed with the other at its own draw, and the stage probabilities combine as independent events."""
    if 'rand_frame' not in json.dumps(summary):return {'reads_rand_frame': False}
    from prediction_illustration import illustrate_field
    loudness = [sum(row.get(b, 0.) for b in ('bass', 'mid', 'treb')) for row in audio['frames'][:frames]]
    # Native frame k renders with declared row k (time (k+1)/fps).
    k = max(range(60, len(loudness)), key=loudness.__getitem__)
    greys, result = [], {}
    def probe(evaluate, draws):
        jump = greys[-1] - greys[-2] if len(greys) > 1 else 0.
        stages = {stage: random_flash_risk(lambda v, stage=stage: evaluate(v, stage), draw, jump) for stage, draw in draws.items()}
        # base_jump > FLASH_JUMP: the probed frame flashes whatever the draw (probability 1 by itself).
        result.update(stages=stages, base_jump=round(jump, 4), max_jump=max(r['max_jump'] for r in stages.values()),
                      flash_probability_per_frame=round(_either(*(r['flash_probability_per_frame'] for r in stages.values())), 6))
    illustrate_field(summary, time=(k + 1) / FPS, fps=FPS, history_steps=k + 1, audio=audio, viewport=list(PROBE_SIZE), rand_probe={'frame': k, 'probe': probe},
                     frame_callback=lambda t, im: greys.append(_grey(im)))
    return {'reads_rand_frame': True, 'probe_frame': k, **result}


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
