"""One preset through a frozen snapshot: export, description, 300 predicted frames measured like the engine ruler."""
import json, shutil, subprocess, sys, tempfile, importlib.util
from pathlib import Path
snapshot, name, sha, target = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve()
ROOT = Path(__file__).resolve().parents[2]
TOOLS = snapshot / 'tools/milk-analyzer'; PY = ROOT / 'build/preset-lab-venv/bin/python'
sys.path.insert(0, str(TOOLS))
import numpy as np
spec = importlib.util.spec_from_file_location('ruler', ROOT / 'build/preset-corpus/native-ruler-2026-10-12/ruler.py'); ruler = importlib.util.module_from_spec(spec); spec.loader.exec_module(ruler)
row = {'status': 'error'}
with tempfile.TemporaryDirectory() as work:
    work = Path(work); (work / 'in').mkdir()
    shutil.copy(ROOT / 'core/src/main/assets/presets' / name, work / 'in' / name)
    manifest = ROOT / f'build/preset-corpus/source-compile-manifest-9606-2026-10-12/per-preset/{sha}.json'
    extra = ['--compile-manifest', str(manifest)] if manifest.exists() else []
    subprocess.run([str(PY), 'effect_family_export.py', str(work / 'in'), '--reader', str(ROOT / 'build/preset-corpus/source34/adapters/milk-native-reader'),
                    '--output', str(work / 'export'), '--input-scenario', str(ROOT / 'build/preset-corpus/source-sample-offset-scenario.json'),
                    '--behaviour-context', str(ROOT / 'build/preset-corpus/spiral-layer-spacing-context-2026-10-11.json'), *extra], cwd=TOOLS, capture_output=True, timeout=900)
    results = list((work / 'export/results').glob('*.json')) if (work / 'export/results').exists() else []
    if results and not subprocess.run([str(PY), 'preset_understanding.py', str(results[0]), '--output', str(work / 'd.json')], cwd=TOOLS, capture_output=True, timeout=600).returncode:
        from prediction_illustration import illustrate_field
        audio = json.load(open(TOOLS / 'fixtures/reference-band-sequence-2026-10-12.json'))
        frames = []
        image, _, _ = illustrate_field(json.load(open(work / 'd.json')), time=10, fps=30, history_steps=300, audio=audio,
                                       frame_callback=lambda t, im: frames.append((np.clip(np.nan_to_num(im), 0, 1) * 255 + .5).astype(np.uint8)))
        if len(frames) < 300:frames = [(np.clip(np.nan_to_num(np.asarray(image, np.float32)), 0, 1) * 255 + .5).astype(np.uint8)] * 300
        raw = work / 'f.rgb.u8'; np.array(frames, np.uint8).tofile(raw)
        row = {'status': 'predicted', **ruler.measure(str(raw))}
    else:row = {'status': 'export_or_description_failed'}
json.dump(row, open(target, 'w'))
print(row['status'])
