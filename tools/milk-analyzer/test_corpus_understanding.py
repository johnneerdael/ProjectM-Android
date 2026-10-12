"""Corpus understanding report aggregates compact rows without calibration claims."""
import json

from corpus_understanding import report


def row(name,activity,bands,confidence='medium',status='computed'):
    value={'name':name,'sha256':'0'*64,'status':status}
    if status=='computed':
        value['approximate_mood']={'activity_estimate':activity,'activity_interval':[activity,activity],'bands':bands,
            'possible_bands':bands,'confidence':confidence,'prior_driver_share':0.,'components':{},'strict_eligible_bands':[],
            'abstained':not bands,'unresolved_driver_count':0}
    return value


def test_report_groups_bands_and_keeps_errors(tmp_path):
    (tmp_path/'results').mkdir()
    rows=[row('a.milk',12,['Chill']),row('b.milk',27,['Chill','Normal']),row('c.milk',80,['Intense'],'low'),
          row('d.milk',0,[],status='timeout'),row('e.milk',50,[],'low')]
    for index,value in enumerate(rows):(tmp_path/'results'/f'{index}.json').write_text(json.dumps(value))
    summary=report(tmp_path)
    assert summary['status']=={'computed':4,'timeout':1}
    assert summary['abstained_presets']==1
    assert summary['approximate_band_counts']=={'Chill':2,'Normal':1,'Intense':1}
    assert summary['strict_eligible_presets']==0
    assert summary['calibrated'] is False
    groups=json.loads((tmp_path/'collections.json').read_text())
    assert [r['name'] for r in groups['Chill']]==['a.milk','b.milk']


def test_rescore_recomputes_mood_from_saved_summary(tmp_path):
    import base64,gzip
    from corpus_understanding import rescore
    (tmp_path/'results').mkdir()
    summary={'policy':'preset-understanding-v1','facts':{'context':[{'path':'/analysis/visual_description/static_behaviour/context',
        'value':{'viewport':[480,270],'feedback_fps':30}}],'motion':[{'path':'/analysis/visual_description/static_behaviour/mesh_field',
        'value':{'status':'described','patterns':[{'pattern':'uniform_zoom','percent_per_step_range':[-7,-2],'audio_inputs':['bass']}]}}]}}
    value=row('z.milk',0,[]);value['summary_gzip_base64']=base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode()
    (tmp_path/'results'/'z.json').write_text(json.dumps(value))
    result=rescore(tmp_path)
    saved=json.loads((tmp_path/'results'/'z.json').read_text())
    assert saved['approximate_mood']['activity_estimate']>5
    assert result['presets']==1


def test_preference_index_carries_facets(tmp_path):
    (tmp_path/'results').mkdir()
    value=row('a.milk',20,['Chill'])
    facets={'policy':'preset-facets-v1','options':['chill'],'evidence':'source-calibrated'}
    value['preference']={'scores':{},'tags':[],'possible_tags':[],'activity_bands':[],'confidence':'medium','profiles':{},
                         'features':{},'facets':facets}
    (tmp_path/'results'/'a.json').write_text(json.dumps(value))
    report(tmp_path)
    index=json.loads((tmp_path/'preference-index.json').read_text())
    assert index['presets'][0]['facets']==facets


def test_rescore_writes_source_calibrated_facets_into_the_index(tmp_path):
    import base64,gzip
    from corpus_understanding import rescore
    (tmp_path/'results').mkdir()
    summary={'policy':'preset-understanding-v1','preset':{'name':'not-bundled.milk','sha256':'1'*64},
        'facts':{'context':[{'path':'/analysis/visual_description/static_behaviour/context','value':{'viewport':[480,270],'feedback_fps':30}}]}}
    value=row('not-bundled.milk',0,[]);value['summary_gzip_base64']=base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode()
    (tmp_path/'results'/'n.json').write_text(json.dumps(value))
    rescore(tmp_path)
    facets=json.loads((tmp_path/'preference-index.json').read_text())['presets'][0]['facets']
    assert facets['policy']=='preset-facets-v1' and facets['evidence']=='source-calibrated'
    assert {'monochrome','pastel'}<=set(facets['unresolved_options'])


def test_worker_passes_the_presets_offline_compile_manifest(tmp_path, monkeypatch):
    import hashlib
    import corpus_understanding as C
    import effect_family_export
    preset = tmp_path / 'a.milk'; preset.write_bytes(b'[preset00]\n')
    sha = hashlib.sha256(preset.read_bytes()).hexdigest()
    manifests = tmp_path / 'manifests'; manifests.mkdir(); (manifests / (sha + '.json')).write_text('{"kind": "x"}')
    seen = []
    def fake_export(path, **kwargs):
        seen.append(kwargs.get('compile_manifest'));return {'status': 'error', 'error': 'stop'}, None
    monkeypatch.setattr(effect_family_export, 'export_preset', fake_export)
    monkeypatch.setattr(effect_family_export, 'loaded_model_hashes', lambda: 'm')
    options = {'reader': 'r', 'timeout': 30, 'input_scenario': None, 'behaviour_context': None, 'compile_manifests': str(manifests)}
    C.work(preset, options, 'm')
    C.work(preset, {**options, 'compile_manifests': str(tmp_path)}, 'm')
    assert seen == [{'kind': 'x'}, None]


def test_worker_timeout_is_not_swallowed_by_broad_exception_handlers():
    import corpus_understanding as C
    assert not issubclass(C._Timeout, Exception) and issubclass(C._Timeout, BaseException)
