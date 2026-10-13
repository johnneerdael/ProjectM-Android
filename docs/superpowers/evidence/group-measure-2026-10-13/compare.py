"""Group measure: predictions (per analyzer version) against native-ruler references, frames 60-149.
Diagnostic measurement only: nothing here feeds the source analysis."""
import json, pickle, sys
from pathlib import Path
import numpy as np
G = Path(__file__).parent
tags = sys.argv[1:] or ['base', 'head']
names = [Path(p['name']).stem for p in json.load(open(G / 'selection.json'))['presets']]
ruler = {n: pickle.load(open(G / 'ruler' / f'{n}.pkl', 'rb')) for n in names if (G / 'ruler' / f'{n}.pkl').exists()}


def corr(a, b):
    a = np.asarray(a, np.float64).ravel(); b = np.asarray(b, np.float64).ravel()
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else None


def metrics(p, r):
    return {'luma_err': abs(p['luma'] - r['luma']), 'rgb_err': float(np.abs(np.array(p['rgb']) - np.array(r['rgb'])).mean()),
            'sat_err': abs(p['saturation'] - r['saturation']), 'fd_err': abs(p['frame_difference'] - r['frame_difference']),
            'map_corr': corr(p['avg_map'].mean(-1), r['avg_map'].mean(-1)), 'colour_map_err': float(np.abs(p['avg_map'] - r['avg_map']).mean()),
            'series_corr': corr(p['luma_series'], r['luma_series'])}


rows = {}
for tag in tags:
    rows[tag] = {}
    for n in names:
        f = G / f'pred-{tag}' / f'{n}.pkl'
        if not f.exists() or n not in ruler or ruler[n]['status'] != 'measured': continue
        p = pickle.load(open(f, 'rb'))
        if p.get('status') != 'predicted': rows[tag][n] = None; continue
        rows[tag][n] = metrics(p, ruler[n])
common = [n for n in names if all(rows[t].get(n) for t in tags)]
report = {'presets_selected': len(names), 'ruler_measured': sum(r['status'] == 'measured' for r in ruler.values()),
          'compared': len(common), 'failed': {t: sum(1 for v in rows[t].values() if v is None) for t in tags}, 'versions': {}}
for t in tags:
    agg = {}
    for k in ('luma_err', 'rgb_err', 'sat_err', 'fd_err', 'colour_map_err'):
        v = np.array([rows[t][n][k] for n in common]); agg[k] = {'mean': round(float(v.mean()), 4), 'median': round(float(np.median(v)), 4)}
    for k in ('map_corr', 'series_corr'):
        v = np.array([rows[t][n][k] for n in common if rows[t][n][k] is not None]); agg[k] = {'mean': round(float(v.mean()), 4), 'median': round(float(np.median(v)), 4), 'n': int(len(v))}
    agg['luma_within_0.05'] = round(float(np.mean([rows[t][n]['luma_err'] < .05 for n in common])), 3)
    agg['map_corr_above_0.8'] = round(float(np.mean([(rows[t][n]['map_corr'] or 0) > .8 for n in common])), 3)
    report['versions'][t] = agg
if len(tags) == 2:
    a, b = tags
    report['paired'] = {k: {'improved': int(sum(rows[b][n][k] < rows[a][n][k] - 1e-4 for n in common)), 'worse': int(sum(rows[b][n][k] > rows[a][n][k] + 1e-4 for n in common))}
                        for k in ('luma_err', 'rgb_err', 'fd_err', 'colour_map_err')}
    report['paired']['map_corr'] = {'improved': int(sum((rows[b][n]['map_corr'] or 0) > (rows[a][n]['map_corr'] or 0) + 1e-3 for n in common)),
                                    'worse': int(sum((rows[b][n]['map_corr'] or 0) < (rows[a][n]['map_corr'] or 0) - 1e-3 for n in common))}
    delta = sorted(common, key=lambda n: rows[b][n]['colour_map_err'] - rows[a][n]['colour_map_err'])
    report['largest_gains'] = [(n, round(rows[a][n]['colour_map_err'], 3), round(rows[b][n]['colour_map_err'], 3)) for n in delta[:8]]
    report['largest_losses'] = [(n, round(rows[a][n]['colour_map_err'], 3), round(rows[b][n]['colour_map_err'], 3)) for n in delta[-8:][::-1]]
json.dump({'report': report, 'per_preset': {t: {n: rows[t][n] for n in common} for t in tags}}, open(G / ('report-' + '-'.join(tags) + '.json'), 'w'), indent=1, default=float)
print(json.dumps(report, indent=1, default=float))
