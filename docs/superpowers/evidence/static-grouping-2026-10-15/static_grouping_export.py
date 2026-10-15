"""Static-only Mood grouping for every corpus preset (no ruler row, no simulation).

For each corpus summary: the recipe render probes (probe_render), the source-calibrated display estimate with the
shipped model (calibrated_display.predict), then facets_block with the preset identity removed so the bundled
engine-ruler row is bypassed, and the display palette. Output: static-index.json {preset: {options, possible,
unresolved, palette, dominant_hue}} and an agreement report against the engine-ruler options (in-sample for the
model on bundled presets; the out-of-fold scoreboard is the honest estimate)."""
import json, gzip, base64, sys, os, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
def one(path):
    warnings.filterwarnings('ignore')
    from preset_recipe import probe_render, facets_block, display_palette
    from calibrated_display import predict
    try:
        d = json.load(open(path)); s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        render = probe_render(s); display = predict(s, render=render)
        anon = dict(s); anon['preset'] = {}
        f = facets_block(anon, {'statistics': display})
        pal = display_palette({'display_estimate': {'statistics': display}, 'render': render})
        return d['name'], {'options': f.get('options'), 'possible': f.get('possible_options'), 'unresolved': f.get('unresolved_options'),
                           'palette': pal.get('palette'), 'dominant_hue': pal.get('dominant_hue'), 'dominance': pal.get('dominance')}
    except Exception as e:
        return d.get('name') if 'd' in dir() else None, {'error': str(e)[:200]}
if __name__ == '__main__':
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    paths = sorted(str(R / n) for n in os.listdir(R)); out = {}
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, (name, row) in enumerate(pool.map(one, paths, chunksize=8)):
            if name: out[name] = row
            if i % 1000 == 0: print(i, flush=True)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=0, sort_keys=True))
    print('done', len(out), 'errors', sum(1 for r in out.values() if 'error' in r), flush=True)
