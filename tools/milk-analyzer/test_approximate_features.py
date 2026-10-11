"""Approximate feature vector, research scores, tags and profile suitability."""
import pytest

from approximate_features import describe,feature_vector,scores,tags,suitability

STATIC='/analysis/visual_description/static_behaviour'


def summary(*facts,context=None):
    groups={name:[] for name in ('context','motion','flashing','audio','colour','feedback','construction','geometry')}
    groups['context'].append({'path':STATIC+'/context','value':context or {'viewport':[480,270],'feedback_fps':30}})
    for group,path,value in facts:groups[group].append({'path':path,'value':value})
    return {'policy':'preset-understanding-v1','facts':groups}


def zoom(low,high,audio=()):
    return ('motion',STATIC+'/mesh_field',{'status':'described','patterns':[{'pattern':'uniform_zoom',
            'percent_per_step_range':[low,high],'audio_inputs':list(audio)}]})


def mechanism(name,index=0):
    return ('construction','/analysis/families/%d'%index,{'mechanism':name,'stage':'warp'})


def test_slow_steady_zoom_is_smooth_chill():
    result=describe(summary(zoom(-.5,-.5)))
    assert result['scores']['intensity']['value']<30
    assert result['scores']['smoothness']['value']>=80
    assert 'Smooth' in [t['tag'] for t in result['tags']]


def test_audio_coupled_motion_lowers_smoothness_versus_steady():
    steady=feature_vector(summary(zoom(-3,-3)))
    beat=feature_vector(summary(zoom(-3,-3,audio=['bass'])))
    assert beat['motion.acceleration_p95_vp_s2']['value']>steady['motion.acceleration_p95_vp_s2']['value']
    assert scores(beat)['smoothness']['value']<scores(steady)['smoothness']['value']


def test_flashing_cycle_drives_intensity_floor():
    flash=('flashing',STATIC+'/flashing/records/0',{'kind':'shader_brightness_change','cycle_rate_hz':3,'brightness_delta_range':[0,.4]})
    result=describe(summary(zoom(-.5,-.5),flash))
    assert result['scores']['intensity']['value']>=70
    assert 'Flashing' in [t['tag'] for t in result['tags']]


def test_mechanisms_give_psychedelic_fractal_and_organic_tags():
    result=describe(summary(zoom(-1,-1),mechanism('nonlinear_feedback_map',0),mechanism('angular_mirror_fold',1),
                            mechanism('complex_quadratic_recurrence',2),mechanism('gradient_driven_advection',3)))
    names=[t['tag'] for t in result['tags']]
    assert 'Fractal' in names and 'Organic / Liquid' in names
    assert result['features']['structure.symmetry']['evidence']=='mechanism-estimate'


def test_warm_palette_from_flat_field_and_palette():
    flat=('feedback','/analysis/visual_description/nonlinear_texture_colour_bounds/flat_field',
          {'status':'conditional_flat_field_state','composite_rgb_at_state':[.8,.3,.05]})
    result=describe(summary(zoom(-1,-1),flat))
    assert result['features']['palette.warm_cool']['value']>=.4
    assert 'Warm' in [t['tag'] for t in result['tags']]


def test_unknown_features_widen_intervals_and_lower_confidence():
    result=describe(summary())
    assert result['confidence']=='low' and result['activity_bands']==[]
    assert result['scores']['intensity']['interval'][1]>result['scores']['intensity']['value']


def test_profile_suitability_uses_research_fit_and_constraints():
    result=describe(summary(zoom(-.3,-.3)))
    gentle=result['profiles']['gentle-home-tv-v1']
    assert gentle['suitability'] is not None and gentle['preference_coverage']<=1
    party=result['profiles']['party-v1']
    assert party['suitability']<gentle['suitability']
