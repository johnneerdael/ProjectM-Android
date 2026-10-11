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
