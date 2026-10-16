"""Static mood evidence export (research harness): one row per corpus preset for the main-branch static mood table.

Per preset: corpus sha256, static facet options (no colour ids), static display palette and dominant hue, and the 8
table values from the source-calibrated display estimate (activity from preset_recipe.facet_activity). The preset
identity is removed before facets_block, so no engine-ruler row is used. Output: gzip JSON
{schema, producer, rows}. No simulation output is read."""
import json, gzip, base64, sys, os, subprocess, hashlib, warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
W = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(W / 'tools/milk-analyzer'))
SCHEMA = 'projectm-tv-static-mood-evidence'
FIELDS = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'coloured_share': 'coloured_share',
          'warm_cool': 'warm_cool', 'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference',
          'jumps': 'global_brightness_jumps_per_10s'}
def one(path):
    warnings.filterwarnings('ignore')
    from preset_recipe import probe_render, facets_block, display_palette, facet_activity
    from calibrated_display import predict
    d = json.load(open(path))
    try:
        s = json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
        render = probe_render(s); display = predict(s, render=render)
        anon = dict(s); anon['preset'] = {}
        f = facets_block(anon, {'statistics': display})
        pal = display_palette({'display_estimate': {'statistics': display}, 'render': render})
        values = {k: (display.get(v) or {}).get('value') for k, v in FIELDS.items()}
        values['activity'] = facet_activity({'frame_difference': values['frame_difference'], 'flow': values['flow'], 'jumps': values['jumps']})
        return {'name': d['name'], 'sha256': d['sha256'], 'options': f.get('options') or [], 'palette': pal.get('palette') or [],
                'dominant': pal.get('dominant_hue'), 'values': values}
    except Exception as e:
        return {'name': d['name'], 'sha256': d['sha256'], 'error': str(e)[:200]}
if __name__ == '__main__':
    R = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
    paths = sorted(str(R / n) for n in os.listdir(R)); rows = []
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        for i, row in enumerate(pool.map(one, paths, chunksize=8)):
            rows.append(row)
            if i % 1000 == 0: print(i, flush=True)
    model = W / 'tools/milk-analyzer/fixtures/calibrated-display-model.json.gz'
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=W, capture_output=True, text=True).stdout.strip()
    out = {'schema': SCHEMA, 'version': 1,
           'producer': {'branch': 'feat/predictor-static-output-bounds', 'commit': commit,
                        'calibration_model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
                        'policy': 'static source analysis only; no ruler or simulation values'},
           'rows': sorted(rows, key=lambda r: r['name'])}
    Path(sys.argv[1]).write_bytes(gzip.compress(json.dumps(out, sort_keys=True).encode(), 9, mtime=0))
    print('done', len(rows), 'errors', sum(1 for r in rows if 'error' in r), flush=True)
