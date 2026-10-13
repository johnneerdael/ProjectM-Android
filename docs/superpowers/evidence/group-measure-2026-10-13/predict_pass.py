import json, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
snap, tag = sys.argv[1], sys.argv[2]
G = Path(__file__).parent; out = G / f'pred-{tag}'; out.mkdir(exist_ok=True)
PY = G.parents[1] / 'build/preset-lab-venv/bin/python'
def one(p):
    target = out / (Path(p['name']).stem + '.pkl')
    if target.exists(): return p['name'], 'cached'
    try:
        r = subprocess.run([str(PY), str(G / 'predict_one.py'), snap, p['name'], p['sha256'], str(target)], capture_output=True, text=True, timeout=1500)
        return p['name'], (r.stdout.strip().splitlines() or ['?'])[-1] if r.returncode == 0 else 'crash: ' + r.stderr[-200:]
    except subprocess.TimeoutExpired:
        import pickle; pickle.dump({'status': 'timeout'}, open(target, 'wb')); return p['name'], 'timeout'
presets = json.load(open(G / 'selection.json'))['presets']
with ThreadPoolExecutor(6) as pool:
    for name, status in pool.map(one, presets):
        if status not in ('cached', 'predicted'): print(name, status, flush=True)
print('done', len(list(out.glob('*.pkl'))), flush=True)
