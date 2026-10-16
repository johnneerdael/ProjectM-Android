"""Corpus preview run (owner trial allowance 2026-10-16): the deterministic prediction illustration's frame
statistics (150 history steps at t = 5 s, declared checkpoint bands; the same frames the checkpoint prediction image
renders) for every corpus preset. Resumable: presets with a stats file are skipped. Per-preset cap 300 s."""
import json, gzip, base64, os, sys, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair')
R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'; O = W / 'build/preview-corpus-2026-10-16'
def one(name):
    out = O / 'stats' / (name[:-5] + '.json')
    if out.exists(): return None
    d = json.load(open(R / name)); tmp = O / 'tmp' / (d['sha256'] + '.json')
    tmp.write_bytes(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
    stats = O / 'tmp' / (d['sha256'] + '.stats.json'); png = O / 'tmp' / (d['sha256'] + '.png'); start = time.time()
    try:
        subprocess.run([str(W / 'build/preset-lab-venv/bin/python'), str(W / 'tools/milk-analyzer/prediction_illustration.py'), str(tmp), '--output', str(png),
                        '--frame-stats', str(stats), '--time', '5', '--history-steps', '150', '--audio', str(W / 'tools/milk-analyzer/fixtures/reference-band-sequence-2026-10-12.json')],
                       capture_output=True, timeout=300, check=False)
        row = json.load(open(stats)) if stats.exists() else {'error': 'no stats'}
    except subprocess.TimeoutExpired:
        row = {'error': 'timeout 300 s'}
    row.update(preset=d['name'], seconds=round(time.time() - start, 1)); row.pop('luma_series', None)
    out.write_text(json.dumps(row))
    for p in (tmp, stats, png): p.unlink(missing_ok=True)
    return row['seconds']
if __name__ == '__main__':
    import random; names = sorted(os.listdir(R)); random.Random(20261016).shuffle(names); done = 0  # random order: any partial run is a random sample
    with ThreadPoolExecutor(int(sys.argv[1])) as pool:
        for s in pool.map(one, names):
            done += 1
            if done % 200 == 0: print(done, flush=True)
    print('done', flush=True)
