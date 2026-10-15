"""triage_facets.py A B: static Mood-facet decisions (facets_block on the source-calibrated display estimate, the
bundled ruler row bypassed) vs the engine-ruler options from the attribute bundle. Milliseconds; no simulation."""
import json, sys, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair'); sys.path.insert(0, str(W / 'tools/milk-analyzer'))
from preset_recipe import facets_block
defs = json.load(open(W / 'core/src/main/assets/preset-attributes/facets.json'))
group_of = {o['id']: g['id'] for g in defs['groups'] for o in g['options']}
adm = wrong = rul = hit = 0
for n in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    C = W / f'build/checkpoint-r{n}'; v = C / ('v1/' + (sys.argv[3] if len(sys.argv) > 3 else 'recipe.json'))
    if not v.exists(): print(f'r{n} missing'); continue
    r = json.load(open(v)); desc = json.load(open(C / 'v1/description.json'))
    ruler = set((r.get('facets') or {}).get('options') or [])
    summary = dict(desc); summary['preset'] = {}
    static = set(facets_block(summary, r['display_estimate'])['options']) - {o['id'] for g in defs['groups'] if g['id'] == 'style' for o in g['options']}
    ruler -= {o['id'] for g in defs['groups'] if g['id'] == 'style' for o in g['options']}
    bad = sorted(static - ruler); miss = sorted(ruler - static)
    adm += len(static); wrong += len(bad); rul += len(ruler); hit += len(static & ruler)
    print(f"r{n} admitted {','.join(sorted(static)) or '-'} | WRONG {','.join(bad) or '-'} | omitted {','.join(miss) or '-'}")
print(f'static admissions {adm}, wrong {wrong} (precision {1 - wrong / max(adm, 1):.0%}); ruler options recalled {hit}/{rul}')
