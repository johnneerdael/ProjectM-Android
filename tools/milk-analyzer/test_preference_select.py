"""Preference selection: comfort filters, activity window, palette, tags and profiles."""
import pytest

from preference_select import select,validate


def entry(name,intensity,smooth,tags=(),flash=0.,flash_evidence='source-estimate',speed=.1,suit=None,confidence='medium'):
    return {'name':name,'sha256':'0'*64,'scores':{'intensity':intensity,'smoothness':smooth},'tags':list(tags),
            'activity_bands':[],'confidence':confidence,'profiles':{'gentle-home-tv-v1':{'suitability':suit,'constraints_violated':[]}},
            'features':{'flash.coherent_transitions_hz':flash,'motion.speed_p95_vp_s':speed},
            'evidence':{'flash.coherent_transitions_hz':flash_evidence}}


INDEX={'presets':[entry('calm.milk',15,92,['Smooth','Cold'],suit=95),entry('strobe.milk',85,30,['Flashing'],flash=4,suit=20),
                  entry('unknownflash.milk',20,85,flash=None,flash_evidence='unknown',suit=90),
                  entry('warmflow.milk',35,88,['Warm','Organic / Liquid'],suit=80),entry('fast.milk',40,70,speed=.8,suit=60)]}


def test_no_flashing_excludes_flashing_and_unknown_evidence():
    result=select(INDEX,{'profiles':['gentle-home-tv-v1'],'comfort':{'no_flashing':True}})
    names=[r['name'] for r in result['selected']]
    assert 'strobe.milk' not in names and 'unknownflash.milk' not in names
    assert names[0]=='calm.milk'


def test_activity_palette_and_speed_filters():
    assert sorted(r['name'] for r in select(INDEX,{'activity':[30,60]})['selected'])==['fast.milk','warmflow.milk']
    assert [r['name'] for r in select(INDEX,{'palette':'warm'})['selected']]==['warmflow.milk']
    names=[r['name'] for r in select(INDEX,{'comfort':{'max_speed_vp_s':.3}})['selected']]
    assert 'fast.milk' not in names


def test_tags_change_ranking():
    plain=select(INDEX,{'profiles':['gentle-home-tv-v1'],'comfort':{'no_flashing':True}})
    tagged=select(INDEX,{'profiles':['gentle-home-tv-v1'],'comfort':{'no_flashing':True},
                         'prefer_tags':['Organic / Liquid'],'avoid_tags':['Cold']})
    assert plain['selected'][0]['name']=='calm.milk'
    assert tagged['selected'][0]['name']=='warmflow.milk'


def test_invalid_preference_is_rejected():
    with pytest.raises(ValueError):validate({'mood':'chill'})
    with pytest.raises(ValueError):validate({'activity':[80,20]})


def test_feedback_likes_dislikes_and_complaints():
    def full(name,speed,organic,geometric,luma):
        e=entry(name,30,85,suit=70,speed=speed)
        e['features'].update({'structure.organic':organic,'structure.geometric':geometric,'brightness.mean_encoded_luma':luma,
                              'palette.mean_saturation':.5,'flash.coherent_delta_peak':0.})
        return e
    index={'presets':[full('liquid1.milk',.1,.9,.1,.3),full('liquid2.milk',.12,.85,.15,.32),
                      full('grid1.milk',.1,.1,.9,.3),full('fastgrid.milk',.9,.1,.9,.6)]}
    result=select(index,{'feedback':{'liked':['liquid1.milk'],'disliked':['grid1.milk'],'too_fast':['fastgrid.milk']}})
    names=[r['name'] for r in result['selected']]
    assert names==['liquid1.milk','liquid2.milk']
    assert result['effective_comfort']['max_speed_vp_s']==pytest.approx(.72)
    assert any('similar to a liked' in reason for reason in result['selected'][0]['reasons'])
    dark=select(index,{'feedback':{'too_dark':['liquid1.milk']}})
    assert 'liquid1.milk' not in [r['name'] for r in dark['selected']]
