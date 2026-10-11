"""Preset recipe: render facts, generic intent and music reactivity, optional program."""
import json

from preset_recipe import build_recipe

STATIC='/analysis/visual_description/static_behaviour'
BASE='/analysis/visual_description'


def summary(*facts):
    groups={name:[] for name in ('context','motion','flashing','audio','colour','feedback','construction','geometry')}
    groups['context'].append({'path':STATIC+'/context','value':{'viewport':[480,270],'feedback_fps':30}})
    for group,path,value in facts:groups[group].append({'path':path,'value':value})
    return {'policy':'preset-understanding-v1','preset':{'name':'x.milk','sha256':'0'*64},'description':'d','facts':groups}


def record():
    return summary(
        ('motion',STATIC+'/mesh_field',{'status':'described','controls':{},'patterns':[
            {'pattern':'uniform_zoom','percent_per_step_range':[-7,-2],'content_motion':'contracts toward the screen centre','audio_inputs':['bass']},
            {'pattern':'planar_travelling_wave','control':'dy','region':{'y':[.35,.65]},'oscillator':{'planar_wavelength_pixels':100,
             'phase_speed_pixels_per_second':-64,'travel_direction_xy':[-1,0]},'amplitude_pixels_range':[7,28],'amplitude_dependencies':['bass_att']}]}),
        ('feedback',STATIC+'/feedback_persistence',{'status':'conditional_quantized_decay_orbit','decay_gain':.9,
            'steps_to_half_interval':[7,7],'floor_level_interval':[4,5]}),
        ('construction',BASE+'/elements/0/id','builtin_wave'),('construction',BASE+'/elements/0/stage','drawing'),
        ('audio',BASE+'/elements/0/waveform_recipe',{'form_name':'two_channel_parallel_traces','audio_inputs':['waveform_left','waveform_right'],
            'wave_x':.5,'wave_y':.7}),
        ('construction',BASE+'/elements/1/id','shape_0'),('construction',BASE+'/elements/1/stage','drawing'),
        ('construction',BASE+'/elements/1/parameters',{'sides':6,'instances':4}),
        ('audio',BASE+'/elements/1/audio_routes/0',{'input_code':1,'control':'opacity','has_threshold_or_clamp':True}),
        ('construction','/analysis/families/0',{'mechanism':'angular_mirror_fold','stage':'composite','parameters':{'sector_count':6}}))


def test_intent_lists_generic_effects_and_reactivity():
    recipe=build_recipe(record())
    effects=[e['effect'] for e in recipe['intent']['effects']]
    assert {'trails','zoom_flow','ripple','audio_waveform','shapes','kaleidoscope'}<=set(effects)
    kaleidoscope=[e for e in recipe['intent']['effects'] if e['effect']=='kaleidoscope'][0]
    assert kaleidoscope['sectors']==6
    reactivity={(r['band'],r['target']):r for r in recipe['intent']['reactivity']}
    assert reactivity[('bass','opacity')]['kind']=='brightness'
    assert reactivity[('bass','opacity')]['response']=='threshold_or_clamped'
    assert ('bass','uniform_zoom') in reactivity and ('waveform','line shape follows the audio waveform') in reactivity
    assert recipe['intent']['effects'][0]['half_life_s']==7/30
    json.dumps(recipe,allow_nan=False)


def test_program_is_optional_and_off_by_default():
    source={'sections':{'per_frame_':{'active':True,'source':'zoom=1;','tree':{'function':'sequence'},'status':'parsed'}},'values':{'fDecay':'0.9'}}
    assert 'program' not in build_recipe(record(),source)
    assert build_recipe(record(),source,include_program=True)['program']['sections']['per_frame_']['source']=='zoom=1;'
