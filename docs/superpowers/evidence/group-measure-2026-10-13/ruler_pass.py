"""Native-ruler reference renders for the frozen selection (diagnostic measurement only)."""
import json, pickle, subprocess, tempfile, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from common import summary, W, H
ROOT = Path(__file__).resolve().parents[2]
RULER = ROOT / 'build/preset-corpus/native-ruler-2026-10-12/build/native-ruler'
SWIFT = Path.home() / 'Library/Android/sdk/emulator/lib64/gles_angle'
PCM = ROOT / 'build/preset-corpus/preset-understanding-checkpoint-2026-10-11/synthetic.f32'
TEX = ROOT / 'core/src/main/assets/textures'
OUT = Path('ruler'); OUT.mkdir(exist_ok=True)


def one(name):
    target = OUT / (Path(name).stem + '.pkl')
    if target.exists(): return name, 'cached'
    with tempfile.TemporaryDirectory() as work:
        (Path(work) / 'SwiftShader.ini').write_text('[Processor]\nThreadCount=1\n')
        prefix = Path(work) / 'r'
        done = subprocess.run([str(RULER), str(SWIFT), str(ROOT / 'core/src/main/assets/presets' / name), str(PCM), str(prefix), '150', str(W), str(H), str(TEX)],
                              capture_output=True, text=True, timeout=600, cwd=work)
        if done.returncode: row = {'status': 'render_error', 'error': done.stderr[-300:]}
        else:
            frames = np.fromfile(str(prefix) + '.rgb.u8', np.uint8).reshape(-1, H, W, 3).astype(np.float32) / 255
            row = {'status': 'measured', **summary(frames)}
    pickle.dump(row, open(target, 'wb'))
    return name, row['status']


names = [p['name'] for p in json.load(open('selection.json'))['presets']]
with ThreadPoolExecutor(6) as pool:
    for name, status in pool.map(one, names):
        if status not in ('cached', 'measured'): print(name, status, flush=True)
print('done', len(list(OUT.glob('*.pkl'))))
