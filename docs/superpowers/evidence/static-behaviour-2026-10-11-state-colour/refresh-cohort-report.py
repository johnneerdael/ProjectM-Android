import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path('build/preset-corpus')
OLD=ROOT/'static-behaviour-2000-2026-10-10-transfer-v6'
NEW=ROOT/'static-behaviour-2000-2026-10-11-state-colour-v8-final'
OUT=Path('docs/superpowers/evidence/static-behaviour-2026-10-11-state-colour')
OUT.mkdir(parents=True,exist_ok=True)
def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def rows(folder):
    with gzip.open(folder/'rows.jsonl.gz','rt') as stream:
        for line in stream:yield json.loads(line)
def baseline(row):
    b=row['analysis']['visual_description']['static_behaviour']
    return {'preset':row['preset'],'hue':b['colour']['useful_hue_description'],
            'index':b['classification']['intensity']['value'],
            'bands':b['classification']['predicted_bands'],
            'gray_shapes':[c['component_id'] for c in b['colour']['components']
                if c['source_palette']['model']=='correlated_native_shared_scalar_rgb']}
prior={r['preset']['sha256']:baseline(r) for r in rows(OLD)}
counts=Counter();changes=[];illustrations=[]
for row in rows(NEW):
    b=row['analysis']['visual_description']['static_behaviour'];before=prior.pop(row['preset']['sha256']);after=baseline(row)
    assert before['preset']==after['preset']
    counts['presets']+=1
    counts['presets_with_useful_hues']+=after['hue']
    shapes=b['shape_state']['components']
    counts['active_shapes']+=len(shapes)
    counts['presets_with_shape_state_boxes']+=any(s['state_domains'] for s in shapes)
    paired=[s for s in shapes if {'x','y'}<=set(s['instance_output_domains'])]
    counts['shapes_with_paired_output_axes']+=len(paired)
    counts['presets_with_paired_output_axes']+=bool(paired)
    stochastic=[c for c in b['colour']['components'] if c['source_palette'].get('stochastic_vertex_colour')]
    counts['presets_with_stochastic_colour_recipes']+=bool(stochastic)
    counts['stochastic_colour_components']+=len(stochastic)
    aggregates=[c for c in b['prominence']['components'] if c.get('support',{}).get('method')=='aggregate polygon area envelope']
    counts['presets_with_aggregate_shape_support']+=bool(aggregates)
    counts['aggregate_support_components']+=len(aggregates)
    counts['finite_subunit_aggregate_support_components']+=sum(c['support']['area_fraction_interval'][1]<1 for c in aggregates)
    if {k:v for k,v in before.items() if k!='preset'}!={k:v for k,v in after.items() if k!='preset'}:
        changes.append({'preset':row['preset'],'before':before,'after':after})
    if ('how to impress dullards2' in row['preset']['relative_path'] or 'skekseas.milk' in row['preset']['relative_path']):
        illustrations.append({'preset':row['preset'],'shape_state':b['shape_state'],
            'shape_colour':[c for c in b['colour']['components'] if c['component_id'].startswith('shape_')],
            'automatic_eligible_bands':b['classification']['eligible_bands'],
            'native_numeric_certified':False,'appearance_accuracy_verified':False})
    assert not b['uses_rendered_images'] and not b['uses_equation_execution'] and not b['uses_shader_execution']
    assert not b['classification']['eligible_bands']
assert not prior
write('cohort-summary.json',json.loads((NEW/'summary.json').read_text()))
write('source-coverage.json',{'counts':dict(counts),'no_appearance_or_mood_accuracy_claim':True})
write('comparison.json',{'comparison':'same frozen 2000 sources and default declared context; v6 versus corrected v8',
    'changed_presets':len(changes),'useful_hue_claims_withdrawn':sum(c['before']['hue'] and not c['after']['hue'] for c in changes),
    'useful_hue_claims_added':sum(not c['before']['hue'] and c['after']['hue'] for c in changes),
    'changes':changes})
write('source-examples.json',illustrations)
write('source-identities.json',{'models':json.loads((NEW/'manifest.json').read_text())['model_modules'],
    'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OLD/'rows.jsonl.gz',NEW/'rows.jsonl.gz',NEW/'manifest.json']},
    'target':'published v2.3.34/35/36-equivalent pinned source34 engine',
    'live_latest_refresh':'GitHub API unavailable; no newly verified latest-release claim',
    'earlier_v8':'pre-review corner guard rows retained separately; not final qualification'})
print(json.dumps({'counts':dict(counts),'changed_presets':len(changes),'evidence':str(OUT)}))
