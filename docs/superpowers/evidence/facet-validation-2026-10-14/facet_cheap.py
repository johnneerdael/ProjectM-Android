"""Accuracy vs cost of cheaper static-prediction facet settings on the presets the full pass finished."""
import json, os, shutil, subprocess, sys, tempfile, time, importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
G = Path(__file__).parent; ROOT = G.parents[1]; snap = G / sys.argv[1]; tag = sys.argv[2]
TOOLS = snap / 'tools/milk-analyzer'; PY = ROOT / 'build/preset-lab-venv/bin/python'
CONFIGS = {'96x54-300': ((96, 54), 300), '96x54-120': ((96, 54), 120), '64x36-90': ((64, 36), 90)}
out = G / f'facet-cheap-{tag}'; out.mkdir(exist_ok=True)
done = [p for p in json.load(open(G / 'selection.json'))['presets'] if (G / 'facet-e2ee' / (Path(p['name']).stem + '.json')).exists()]
WORKER = r'''
import json, sys, time, importlib.util, numpy as np, cv2
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('ruler', sys.argv[2]); ruler = importlib.util.module_from_spec(spec); spec.loader.exec_module(ruler)
from prediction_illustration import illustrate_field
d = json.load(open(sys.argv[3])); audio = json.load(open(sys.argv[1] + '/fixtures/reference-band-sequence-2026-10-12.json'))
w, h, n = int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]); frames = []
t = time.time()
image, _, _ = illustrate_field(d, time=n / 30., fps=30, history_steps=n, audio=audio, viewport=[w, h],
                               frame_callback=lambda tt, im: frames.append((np.clip(np.nan_to_num(im), 0, 1) * 255 + .5).astype(np.uint8)))
cost = time.time() - t
if len(frames) < n: frames = [(np.clip(np.nan_to_num(np.asarray(image, np.float32)), 0, 1) * 255 + .5).astype(np.uint8)] * n
big = np.array([cv2.resize(f, (480, 270), interpolation=cv2.INTER_LINEAR) for f in frames], np.uint8)
if n < 300:  # measure() reads frames 60+: pad the start with the first frame so the predicted window is measured
    big = np.concatenate([np.repeat(big[:1], 300 - n, axis=0), big])
big.tofile(sys.argv[7]); row = ruler.measure(sys.argv[7]); row['seconds'] = cost
json.dump(row, open(sys.argv[8], 'w'))
'''
def one(p):
    stem = Path(p['name']).stem
    if all((out / f'{stem}.{c}.json').exists() for c in CONFIGS): return
    with tempfile.TemporaryDirectory() as work:
        work = Path(work); (work / 'in').mkdir(); shutil.copy(ROOT / 'core/src/main/assets/presets' / p['name'], work / 'in' / p['name'])
        manifest = ROOT / f"build/preset-corpus/source-compile-manifest-9606-2026-10-12/per-preset/{p['sha256']}.json"
        extra = ['--compile-manifest', str(manifest)] if manifest.exists() else []
        t = time.time()
        subprocess.run([str(PY), 'effect_family_export.py', str(work / 'in'), '--reader', str(ROOT / 'build/preset-corpus/source34/adapters/milk-native-reader'), '--output', str(work / 'export'),
                        '--input-scenario', str(ROOT / 'build/preset-corpus/source-sample-offset-scenario.json'), '--behaviour-context', str(ROOT / 'build/preset-corpus/spiral-layer-spacing-context-2026-10-11.json'), *extra],
                       cwd=TOOLS, capture_output=True, timeout=900)
        res = list((work / 'export/results').glob('*.json')) if (work / 'export/results').exists() else []
        if not res or subprocess.run([str(PY), 'preset_understanding.py', str(res[0]), '--output', str(work / 'd.json')], cwd=TOOLS, capture_output=True, timeout=600).returncode: return
        (work / 'w.py').write_text(WORKER)
        for c, ((w, h), n) in CONFIGS.items():
            target = out / f'{stem}.{c}.json'
            if target.exists(): continue
            try: subprocess.run([str(PY), str(work / 'w.py'), str(TOOLS), str(ROOT / 'build/preset-corpus/native-ruler-2026-10-12/ruler.py'), str(work / 'd.json'), str(w), str(h), str(n), str(work / 'f.u8'), str(target)], capture_output=True, timeout=900)
            except subprocess.TimeoutExpired: json.dump({'status': 'timeout'}, open(target, 'w'))
with ThreadPoolExecutor(4) as pool: list(pool.map(one, done))
print('done')
