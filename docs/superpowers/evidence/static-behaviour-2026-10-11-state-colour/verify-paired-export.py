import hashlib
import json
import math
from pathlib import Path
import jsonschema

ROOT=Path('build/preset-corpus/static-behaviour-final100-2026-10-11-state-colour-v8')
OUT=Path('docs/superpowers/evidence/static-behaviour-2026-10-11-state-colour')
schema=json.loads(Path('tools/milk-analyzer/export-contract/source-appearance.schema.json').read_text())
validator=jsonschema.Draft202012Validator(schema)
manifest=json.loads((ROOT/'run-manifest.json').read_text())
models=manifest['configuration']['model_modules']
current={name:hashlib.sha256((Path('tools/milk-analyzer')/name).read_bytes()).hexdigest() for name in models}
assert models==current
errors=[];records=0;behaviours=0;state_rows=0;violations=0
for path in sorted((ROOT/'results').glob('*.json')):
    row=json.loads(path.read_text());records+=1
    assert row['status']=='computed'
    description=row['analysis']['visual_description']
    errors.extend({'file':path.name,'error':e.message,'path':list(e.absolute_path)} for e in validator.iter_errors(description))
    b=description['static_behaviour'];behaviours+=1
    assert not b['uses_rendered_images'] and not b['uses_equation_execution'] and not b['uses_shader_execution']
    for name,value in b['model_sources'].items():assert models[name]==value
    for state in b['shape_state']['components']:
        state_rows+=1
        assert not state['native_numeric_certified'] and not state['visible_motion_certified']
        for name,pair in state['state_domains'].items():
            assert len(pair)==2 and all(type(v) in {int,float} and math.isfinite(v) for v in pair) and pair[0]<=pair[1]
            assert state['obligations'][name]=={'initialization':'proven','transition':'proven'}
        for pair in state['instance_output_domains'].values():
            assert len(pair)==2 and all(type(v) in {int,float} and math.isfinite(v) for v in pair) and pair[0]<=pair[1]
    if b['classification']['unknown_contributors'] and 'Chill' in b['classification']['eligible_bands']:violations+=1
assert records==behaviours==100
assert not errors and not violations
OUT.mkdir(parents=True,exist_ok=True)
result={'records':records,'behaviour_reports':behaviours,'shape_state_rows':state_rows,
        'schema_errors':errors,'model_hash_mismatches':[],'state_interval_and_obligation_checks':True,
        'unknown_activity_chill_violations':violations,'uses_rendered_reference':False}
(OUT/'export-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
