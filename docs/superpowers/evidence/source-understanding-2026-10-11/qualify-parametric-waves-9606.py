"""Full-pack source primitive census, without shader/feedback execution."""
import hashlib,json,multiprocessing,subprocess,sys,time,gzip
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,str(Path('tools/milk-analyzer').resolve()))
from corpus_store import discover
from forecast import model_file_hashes

READER=Path('build/preset-corpus/source34/adapters/milk-native-reader').resolve()
OUT=Path('build/preset-corpus/parametric-waves-full9606-2026-10-11')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def initialize(models):
    global MODELS
    MODELS=models
def evaluate(case):
    from effect_families import _Analysis,_CACHE
    from scene_equations import _scalar,source_settings
    from engine_profiles import CORE_2334_ENGINE
    start=time.perf_counter();row={'preset':{k:case[k] for k in ('relative_path','sha256')},'status':'unresolved'}
    if model_file_hashes()!=MODELS:raise ValueError('frozen model changed')
    token=_CACHE.set({})
    try:
        assert sha(case['path'])==case['sha256']
        data=json.loads(subprocess.check_output([str(READER),case['path']],timeout=30))
        assert data['parser_inputs']['engine']==CORE_2334_ENGINE
        data['preset_sha256']=case['sha256'];data['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
        assert sha(case['path'])==case['sha256']
        analysis=_Analysis(data,'gles300',None);analysis.input_scenario=None
        analysis.main_equations();analysis.primitives()
        values=source_settings(data)
        active=[i for i in range(4) if _scalar(values,f'wavecode_{i}_enabled',0,'bool')]
        radial=[f for f in analysis.families if f['mechanism']=='parametric_radial_curve']
        recipes=[{'component_id':f['component'],'recipe':f['parameters']['source_curve_recipe']}
                 for f in radial if 'source_curve_recipe' in f['parameters']]
        row.update(status='computed',active_custom_wave_indices=active,
            radial_construction_count=len(radial),recipes=recipes,
            equation_unknowns=analysis.unknowns,
            source_scope='enabled primitive source before shader selection, contribution gates and final visibility')
    except (ValueError,KeyError,RecursionError,OverflowError,subprocess.TimeoutExpired) as error:
        row.update(error_type=type(error).__name__,reason=str(error))
    finally:_CACHE.reset(token)
    row['elapsed_seconds']=time.perf_counter()-start
    if model_file_hashes()!=MODELS:raise ValueError('frozen model changed during analysis')
    return row

if __name__=='__main__':
    cases=discover('core/src/main/assets/presets');models=model_file_hashes();counts=Counter();classes=Counter();errors=Counter()
    assert len(cases)==9606
    OUT.mkdir(parents=True,exist_ok=False)
    manifest={'reader_sha256':sha(READER),'model_modules':models,'presets':[{k:c[k] for k in ('relative_path','sha256')} for c in cases],
        'source_scope':'source primitive inventory, not whole-preset classification','uses_rendered_images':False,
        'uses_equation_execution':False,'uses_shader_execution':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(models,)) as pool:
        with gzip.open(OUT/'rows.jsonl.gz','wt') as stream:
            for i,row in enumerate(pool.map(evaluate,cases,chunksize=1),1):
                stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');counts[row['status']]+=1
                if row['status']=='computed':
                    counts['presets_with_active_custom_waves']+=bool(row['active_custom_wave_indices'])
                    counts['active_custom_waves']+=len(row['active_custom_wave_indices'])
                    counts['presets_with_radial_construction']+=bool(row['radial_construction_count'])
                    counts['presets_with_supported_recipes']+=bool(row['recipes'])
                    counts['supported_recipes']+=len(row['recipes'])
                    for r in row['recipes']:
                        classes[r['recipe']['curve_class']]+=1
                        counts['recipes_with_locus_relation']+=r['recipe'].get('source_locus_relation',{}).get('fixed_angle_branch_radial_rate_source_coordinates_per_second') is not None
                else:errors[row['reason']]+=1
                if i%1000==0:print(json.dumps({'completed':i,'total':9606}),flush=True)
    assert models==model_file_hashes()
    summary={'presets':len(cases),'counts':dict(counts),'recipe_classes':dict(classes),'errors':dict(errors),
        'wall_seconds':time.perf_counter()-start,'reader_sha256':sha(READER),'manifest_sha256':sha(OUT/'manifest.json'),
        'rows_sha256':sha(OUT/'rows.jsonl.gz'),'uses_rendered_images':False,'mood_accuracy_verified':False,
        'scope':'whole-pack primitive source coverage; shader selection/final visibility/mood remain separate'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary),flush=True)
