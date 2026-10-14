"""Random-draw flash probe (facet_precompute.random_flash, working tree) on a selection, from r13 corpus summaries."""
import json, sys, os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
G = Path(__file__).parent; ROOT = G.parents[1]
sys.path.insert(0, str(ROOT / 'tools/milk-analyzer'))
R13 = ROOT / 'build/preset-corpus/corpus-understanding-9606-r13/results'
def one(p):
    import facet_precompute as F
    out = G / f'flash-{sys.argv[2]}' / (Path(p['name']).stem + '.json')
    if out.exists():return
    import hashlib; src = R13 / (hashlib.sha256(p['name'].encode()).hexdigest()[:20] + '.json')
    if not src.exists():return
    row = json.load(open(src)); summary = F._summary(row)
    if summary is None:return
    audio = json.load(open(ROOT / 'tools/milk-analyzer/fixtures/reference-band-sequence-2026-10-12.json'))
    try:rec = F.random_flash(summary, audio)
    except Exception as e:rec = {'error': str(e)[:200]}
    json.dump({'name': p['name'], **rec}, open(out, 'w'))
if __name__ == '__main__':
    (G / f'flash-{sys.argv[2]}').mkdir(exist_ok=True)
    with ProcessPoolExecutor(int(sys.argv[3])) as pool:list(pool.map(one, json.load(open(G / sys.argv[1]))['presets']))
    print('done')
