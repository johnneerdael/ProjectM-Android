import json, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
G = Path(__file__).parent; snap, tag, workers = sys.argv[1], sys.argv[2], int(sys.argv[3]); selection = sys.argv[4] if len(sys.argv) > 4 else 'selection.json'; out = G / f'facet-{tag}'; out.mkdir(exist_ok=True)
PY = G.parents[0] / 'preset-lab-venv/bin/python'
def one(p):
    target = out / (Path(p['name']).stem + '.json')
    if target.exists(): return
    try: subprocess.run([str(PY), str(G / 'facet_one.py'), str(G / snap), p['name'], p['sha256'], str(target)], capture_output=True, timeout=1800)
    except subprocess.TimeoutExpired: json.dump({'status': 'timeout'}, open(target, 'w'))
with ThreadPoolExecutor(workers) as pool: list(pool.map(one, json.load(open(G / selection))['presets']))
print('done', len(list(out.glob('*.json'))))
