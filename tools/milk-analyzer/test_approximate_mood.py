"""Approximate mood: labelled drivers, editable rules, no silent Chill."""
import pytest

from approximate_mood import approximate_mood,validate_rules

STATIC='/analysis/visual_description/static_behaviour'


def summary(*facts,context=None):
    groups={name:[] for name in ('context','motion','flashing','audio','colour','feedback','construction')}
    groups['context'].append({'path':STATIC+'/context','value':context or {'viewport':[480,270],'feedback_fps':30}})
    for group,path,value in facts:groups[group].append({'path':path,'value':value})
    return {'policy':'preset-understanding-v1','facts':groups}


def zoom(low,high,audio=()):
    return ('motion',STATIC+'/mesh_field',{'status':'described','patterns':[{'pattern':'uniform_zoom','percent_per_step_range':[low,high],
            'audio_inputs':list(audio)}]})


def test_empty_summary_is_low_confidence_not_certified_chill():
    result=approximate_mood(summary())
    assert result['confidence']=='low'
    assert result['bands']==[] and result['abstained'] is True
    assert result['calibrated'] is False
    assert result['activity_estimate']==5.0


def test_partial_field_and_unscored_records_widen_interval_and_abstain():
    partial=('motion',STATIC+'/mesh_field',{'status':'partial','patterns':[{'pattern':'spatially_varying_zoom'}]})
    flash=('flashing',STATIC+'/flashing/records/0',{'kind':'other_brightness','maximum_brightness_change_per_second':None})
    result=approximate_mood(summary(partial,flash))
    assert result['confidence']=='low' and result['bands']==[]
    assert result['activity_interval'][1]>=80
    assert result['unresolved_driver_count']>=2


def test_audio_is_counted_once_per_band():
    route=('audio','/analysis/visual_description/elements/0/audio_routes/0',{'input_code':1,'control':'zoom'})
    result=approximate_mood(summary(zoom(-7,-2,audio=['bass','bass_att']),route))
    assert result['components']['audio']==pytest.approx(.34)


def test_fast_audio_zoom_scores_higher_than_slow_zoom():
    slow=approximate_mood(summary(zoom(-.1,-.1)))
    fast=approximate_mood(summary(zoom(-7,-2,audio=['bass'])))
    assert fast['activity_estimate']>slow['activity_estimate']
    assert fast['components']['audio']>0
    assert slow['confidence']=='high' and slow['bands']==['Chill']


def test_prior_only_mechanism_widens_interval_and_lowers_confidence():
    prior=('motion',STATIC+'/motion/contributions/0',{'kind':'procedural_shader_motion','component_id':'shader_warp'})
    result=approximate_mood(summary(prior))
    assert result['confidence']=='low' and result['bands']==[]
    assert result['activity_interval'][0]<result['activity_estimate']<result['activity_interval'][1]
    assert result['drivers'][0]['kind']=='prior'


def test_known_flash_cycle_raises_flash_component():
    flash=('flashing',STATIC+'/flashing/records/0',{'kind':'shader_brightness_change','cycle_rate_hz':4,'brightness_delta_range':[0,.5]})
    result=approximate_mood(summary(flash))
    assert result['components']['flash']==1.0
    assert 'Intense' in result['possible_bands'] or result['activity_estimate']>=35


def test_rules_are_editable_and_validated():
    result=approximate_mood(summary(zoom(-7,-2)),{'motion_weight':0.})
    assert result['activity_estimate']==5.0
    with pytest.raises(ValueError):validate_rules({'unknown':1})
    with pytest.raises(ValueError):validate_rules({'base':-1})


def test_strict_eligibility_is_reported_separately():
    classification=('mood',STATIC+'/classification',{'eligible_bands':[]})
    record=summary(zoom(-7,-2));record['facts']['mood']=[{'path':classification[1],'value':classification[2]}]
    assert approximate_mood(record)['strict_eligible_bands']==[]


def test_shader_lookup_time_partial_is_a_prior_not_unresolved():
    record=summary(('motion',STATIC+'/motion/contributions/0',{'kind':'authored_sampling_time_partial','component_id':'shader_warp',
        'speed_interval_vp_per_second':[0,None],'estimate_kind':'unknown'}))
    result=approximate_mood(record)
    assert [d['kind'] for d in result['drivers']]==['prior']
    assert result['unresolved_driver_count']==0


def test_uncovered_strict_component_is_unresolved_but_covered_one_is_not():
    classification=('mood',STATIC+'/classification',{'unknown_contributors':[
        {'component_id':'shape_0','dimension':'motion'},{'component_id':'shader_warp','dimension':'motion'}]})
    prior=('motion',STATIC+'/motion/contributions/0',{'kind':'procedural_shader_motion','component_id':'shader_warp'})
    record=summary(prior);record['facts']['mood']=[{'path':classification[1],'value':classification[2]}]
    result=approximate_mood(record)
    reasons=[d['reason'] for d in result['drivers'] if d['kind']=='unresolved']
    assert reasons==['no approximate driver for shape_0']


def test_audio_route_to_brightness_adds_flash_prior():
    route=('audio','/analysis/visual_description/elements/2/audio_routes/0',{'input_code':1,'control':'opacity'})
    motion=('audio','/analysis/visual_description/elements/2/audio_routes/1',{'input_code':1,'control':'position_x'})
    result=approximate_mood(summary(zoom(-2,-1),route,motion))
    flash=[d for d in result['drivers'] if d['dimension']=='flash']
    assert len(flash)==1 and flash[0]['kind']=='prior' and flash[0]['reason']=='audio-driven brightness/colour in 1 element'
    assert result['components']['flash']>0
    more=[('audio','/analysis/visual_description/elements/%d/audio_routes/0'%i,{'input_code':1,'control':'colour_r'}) for i in range(5)]
    assert approximate_mood(summary(zoom(-2,-1),*more))['components']['flash']>result['components']['flash']


def test_self_advection_bound_and_lookup_speed_are_source_motion():
    advection=('motion','/analysis/visual_description/sampling_geometry/stages/warp/3/sample_value_offset_envelope',
               {'source_model':'sample_value_offset_bounds','offset_range_uv':[[-.015,.015],[-.02,.02]]})
    lookup=('motion','/analysis/visual_description/sampling_geometry/stages/warp/4/sampling_motion',
            {'policy':'source-affine-sampling-time-motion-v1','maximum_lookup_axis_speed_uv_per_second':[.3,.4]})
    result=approximate_mood(summary(advection,lookup))
    kinds={d['reason']:d for d in result['drivers']}
    assert kinds['self-advection displacement (typical fraction of bound)']['value']==pytest.approx(.02*30*.25)
    assert kinds['time-driven lookup motion (half of ceiling)']['value']==pytest.approx(.25)
    assert result['confidence'] in ('high','medium')
