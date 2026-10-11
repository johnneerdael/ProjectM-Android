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
