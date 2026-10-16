"""Per-preview static-math gap ledger (owner, 2026-10-16: act on each finished preview, never wait for the corpus).

Every finished preview is processed at once: static out-of-fold estimate vs preview vs engine ruler for luminance and
saturation; for the same preset, static mechanism facts computed on the spot (warp area magnification from the mesh
backward map, feedback equilibrium local/spread luma, warp detail gain). Rows go to ledger.jsonl; gap_report.md
compares mechanism facts between presets the static math misses while the preview is right ('static gap') and presets
where both are right ('agree'). The preview is a teacher for the static maths, never a label source."""
import json, gzip, base64, sys, time, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair')
sys.path.insert(0, str(W / 'tools/milk-analyzer')); sys.path.insert(0, str(W / 'build/colour-gap-2026-10-15'))
from magnification_corpus import probe as magnification
from feedback_equilibrium import equilibrium, stage_detail_gain
O = W / 'build/preview-corpus-2026-10-16'; RES = W / 'build/preset-corpus/corpus-understanding-9606-r14/results'
RU = W / 'build/preset-corpus/native-ruler-2026-10-12/corpus/results'
oof = json.load(open(W / 'build/calibration-2026-10-14/oof-floor80.json'))['predictions']
index = {}
for f in RES.iterdir():
    try: index[json.load(open(f))['name']] = f
    except Exception: pass
ledger = O / 'ledger.jsonl'; seen = set()
if ledger.exists():
    for line in ledger.read_text().splitlines():
        try: seen.add(json.loads(line)['preset'])
        except Exception: pass
def summary_of(name):
    d = json.load(open(index[name])); return json.loads(gzip.decompress(base64.b64decode(d['summary_gzip_base64'])))
def row_for(pv):
    name = pv['preset']; rf = RU / (name[:-5] + '.json')
    if not rf.exists() or name not in index or name not in oof: return None
    r = json.load(open(rf))
    if r.get('status') != 'measured': return None
    s = summary_of(name); facts = {f['path']: f['value'] for g in s['facts'].values() for f in g}
    e = equilibrium(s); g = stage_detail_gain(facts) or {}; m = magnification(s) or {}
    row = {'preset': name}
    for k in ('mean_luminance', 'mean_saturation'):
        row[k] = {'static': oof[name].get(k), 'preview': pv.get(k), 'ruler': r.get(k)}
    lum=lambda c:.2126*c[0]+.7152*c[1]+.0722*c[2]
    row.update(eq_local=e['display_local_luma'], eq_spread=e['display_spread_luma'], detail_gain=g.get('gain'), **m,
               eq_canvas_local=lum(e['canvas_local_rgb']), eq_canvas_spread=lum(e['canvas_spread_rgb']), preview_canvas=pv.get('canvas_mean_luminance'))
    return row
def classify(row, k='mean_luminance'):
    v = row[k]
    if None in v.values(): return None
    if abs(v['preview'] - v['ruler']) < .08 and abs(v['static'] - v['ruler']) > .15: return 'static_gap_' + ('under' if v['static'] < v['ruler'] else 'over')
    if abs(v['preview'] - v['ruler']) < .08 and abs(v['static'] - v['ruler']) < .08: return 'agree'
    return 'other'
def report():
    rows = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
    groups = {}
    for r in rows: groups.setdefault(classify(r), []).append(r)
    lines = [f'# Static-math gap ledger ({len(rows)} previews, {time.strftime("%Y-%m-%d %H:%M")})', '',
             '| class | n | median magnification | share magnif > 1.5 | eq local | eq spread | detail gain > 1.1 |', '|---|---|---|---|---|---|---|']
    for c in ('static_gap_under', 'static_gap_over', 'agree', 'other'):
        g = groups.get(c, [])
        if not g: continue
        mag = [r.get('mag:median') for r in g if r.get('mag:median') is not None]
        dg = [r.get('detail_gain') for r in g if r.get('detail_gain') is not None]
        lines.append(f"| {c} | {len(g)} | {np.median(mag) if mag else float('nan'):.2f} | {np.mean([x > 1.5 for x in mag]) if mag else float('nan'):.0%} | "
                     f"{np.median([r['eq_local'] for r in g]):.2f} | {np.median([r['eq_spread'] for r in g]):.2f} | {np.mean([x > 1.1 for x in dg]) if dg else float('nan'):.0%} |")
    (O / 'gap_report.md').write_text('\n'.join(lines) + '\n')
while True:
    for f in sorted((O / 'stats').glob('*.json')):
        try: pv = json.load(open(f))
        except Exception: continue
        if 'error' in pv or pv.get('preset') in seen: continue
        seen.add(pv['preset'])
        try: row = row_for(pv)
        except Exception as e: row = {'preset': pv['preset'], 'error': str(e)[:120]}
        if row and 'error' not in row:
            with open(ledger, 'a') as out: out.write(json.dumps(row) + '\n')
    report()
    if len(sys.argv) > 1 and sys.argv[1] == 'once': break
    time.sleep(60)
