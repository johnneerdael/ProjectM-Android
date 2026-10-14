"""One preset through a frozen analyzer snapshot: export, description, 150 predicted frames, summary."""
import json, pickle, shutil, subprocess, sys, tempfile
from pathlib import Path
snapshot, name, sha, target = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve()
ROOT = Path(__file__).resolve().parents[2]
TOOLS = snapshot / 'tools/milk-analyzer'
PY = ROOT / 'build/preset-lab-venv/bin/python'
sys.path.insert(0, str(TOOLS)); sys.path.insert(1, str(Path(__file__).parent))
from common import summary
import numpy as np
row = {'status': 'error'}
with tempfile.TemporaryDirectory() as work:
    work = Path(work); (work / 'in').mkdir()
    shutil.copy(ROOT / 'core/src/main/assets/presets' / name, work / 'in' / name)
    manifest = ROOT / f'build/preset-corpus/source-compile-manifest-9606-2026-10-12/per-preset/{sha}.json'
    extra = ['--compile-manifest', str(manifest)] if manifest.exists() else []
    done = subprocess.run([str(PY), 'effect_family_export.py', str(work / 'in'), '--reader', str(ROOT / 'build/preset-corpus/source34/adapters/milk-native-reader'),
                           '--output', str(work / 'export'), '--input-scenario', str(ROOT / 'build/preset-corpus/source-sample-offset-scenario.json'),
                           '--behaviour-context', str(ROOT / 'build/preset-corpus/spiral-layer-spacing-context-2026-10-11.json'), *extra],
                          cwd=TOOLS, capture_output=True, text=True, timeout=900)
    results = list((work / 'export/results').glob('*.json')) if (work / 'export/results').exists() else []
    if not results: row = {'status': 'export_failed', 'error': done.stderr[-300:]}
    else:
        d = subprocess.run([str(PY), 'preset_understanding.py', str(results[0]), '--output', str(work / 'description.json')], cwd=TOOLS, capture_output=True, text=True, timeout=600)
        if d.returncode: row = {'status': 'description_failed', 'error': d.stderr[-300:]}
        else:
            from prediction_illustration import illustrate_field
            audio = json.load(open(TOOLS / 'fixtures/reference-band-sequence-2026-10-12.json'))
            frames = []
            import time as _t; _s=_t.perf_counter(); image, _, limits = illustrate_field(json.load(open(work / "description.json")), time=5, fps=30, history_steps=150, audio=audio, viewport=[64, 36],
                             frame_callback=lambda t, im: frames.append(np.clip(np.nan_to_num(im), 0, 1).astype(np.float32)))
            if len(frames) >= 150: row = {'status': 'predicted', 'predict_seconds': round(_t.perf_counter()-_s, 3), **summary(np.array(frames, np.float32))}
            else:
                # No per-pixel field: the illustrator draws only the final picture. Score it as a still clip.
                still = np.clip(np.nan_to_num(np.asarray(image, np.float32)), 0, 1)
                row = {'status': 'predicted', 'still_only': True, **summary(np.repeat(still[None], 150, axis=0))}
pickle.dump(row, open(target, 'wb'))
print(row['status'])
