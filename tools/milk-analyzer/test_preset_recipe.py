"""Preset recipe: render facts, generic intent and music reactivity, optional program."""
import json
import math

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


# Mood facets block: measured bundle values by name, otherwise source-calibrated estimates; never simulation output.
import hashlib
from pathlib import Path

import preset_facets
from preset_recipe import facets_block

ATTRIBUTES=Path(__file__).resolve().parents[2]/'core/src/main/assets/preset-attributes/attributes.tsv'
PRESETS=Path(__file__).resolve().parents[2]/'core/src/main/assets/presets'


def _row(name):
    for line in ATTRIBUTES.read_text().splitlines():
        if line.startswith(name+'\t'):return line.split('\t')


def test_recipe_facets_block_uses_calibrated_values_and_marks_unresolved():
    recipe=build_recipe(record())
    facets=recipe['facets']
    definition=preset_facets.load_definition()
    assert facets['policy']=='preset-facets-v1'
    assert facets['definition_sha256']==hashlib.sha256(preset_facets.DEFINITION.read_bytes()).hexdigest()
    assert facets['evidence']=='source-calibrated' and facets['style_evidence']=='source-structure-facts'
    assert facets['activity_source']=='frozen-facet-reference-from-calibrated-statistics'
    assert {'monochrome','pastel'}<=set(facets['unresolved_options'])
    assert set(facets['options'])<=set(preset_facets.option_ids(definition))
    assert not set(facets['options'])&set(facets['unresolved_options'])
    assert 'kaleidoscope' in facets['options']  # angular_mirror_fold mechanism in the fixture
    for name in ('luminance','saturation','warm_cool','flow','frame_difference','jumps','activity'):
        value=facets['values'][name]
        assert value['evidence']=='source-calibrated' and value['interval'][0]<=value['interval'][1]
    assert facets['values']['coloured_share']=={'value':None,'evidence':'not-estimated'}
    point={k:v['value'] for k,v in facets['values'].items() if v['value'] is not None}
    expected=[o for o in preset_facets.memberships(point,facets['style'],definition) if o not in facets['unresolved_options']]
    assert facets['options']==expected
    assert recipe['display_estimate']['statistics']['mean_luminance']['value']==facets['values']['luminance']['value']
    json.dumps(facets,allow_nan=False)


def test_facets_block_uses_measured_bundle_row_by_name():
    name='404.milk'
    measured=summary();measured['preset']={'name':name,'sha256':hashlib.sha256((PRESETS/name).read_bytes()).hexdigest()}
    facets=facets_block(measured)
    row=_row(name)
    assert facets['evidence']=='engine-ruler-measured'
    assert facets['options']==row[1].split(',')
    assert facets['unresolved_options']==[] and facets['possible_options']==[]
    assert facets['values']['luminance']=={'value':float(row[2]),'evidence':'engine-ruler-measured'}
    assert facets['values']['activity']['value']==float(row[9])


def test_facets_block_ignores_bundle_row_when_preset_bytes_differ():
    renamed=summary();renamed['preset']={'name':'404.milk','sha256':'0'*64}
    facets=facets_block(renamed)
    assert facets['evidence']=='source-calibrated'
    assert 'bundled preset bytes differ' in facets['note']


def test_facet_activity_reproduces_bundled_activity_from_the_frozen_reference():
    from preset_recipe import facet_activity
    lines=[l.split('\t') for l in ATTRIBUTES.read_text().splitlines() if not l.startswith('#')]
    measured=[l for l in lines if l[9]!='-'][::997]
    assert len(measured)>=9
    for row in measured:
        value=facet_activity({'frame_difference':float(row[7]),'flow':float(row[6]),'jumps':float(row[8])})
        assert abs(value-float(row[9]))<.005,row[0]


def test_possible_options_are_those_not_constant_across_the_intervals():
    from preset_recipe import facet_options
    definition=preset_facets.load_definition()
    values={'luminance':{'value':.17,'interval':[0.,.43]},'saturation':{'value':.6,'interval':[.55,.7]},
            'warm_cool':{'value':0.,'interval':[-.1,.1]},'flow':{'value':.1,'interval':[.07,.2]},
            'jumps':{'value':0.,'interval':[0.,.5]},'activity':{'value':.5,'interval':[.4,.6]},
            'coloured_share':{'value':None}}
    options,possible,unresolved=facet_options(values,[],definition)
    assert 'balanced' in options and {'dark','balanced','bright'}<=set(possible)
    assert 'dark' not in options and 'bright' not in options
    assert {'vivid','drifting','no_strobe','normal'}<=set(options)
    assert not {'vivid','drifting','no_strobe','normal','warm','cool'}&set(possible)
    assert unresolved==['monochrome','pastel']


def test_custom_warp_persistence_comes_from_the_warp_flat_colour_transfer(monkeypatch):
    # A custom warp keeps 90% of uniform content and adds nothing: decay does not apply, the
    # exported warp transfer gives the per-frame gain and the halving time.
    import math
    import feedback_equilibrium
    import preset_recipe as R
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer',
                        lambda facts, stage, **_: {'levels': [0., .5, 1.], 'rgb': [[0.] * 3, [.45] * 3, [.9] * 3]} if stage == 'warp' else None)
    facts = {'/analysis/visual_description/static_behaviour/feedback_persistence': {'decay_gain': None},
             '/analysis/visual_description/stage_programs': {'stages': {'warp': {'status': 'exported'}}}}
    feedback = R._render(facts)['feedback']
    assert feedback['decay'] is None
    transfer = feedback['warp_transfer']
    assert transfer['gain_rgb'] == [.9, .9, .9] and transfer['offset_rgb'] == [0., 0., 0.]
    assert abs(transfer['halving_frames'] - math.log(.5) / math.log(.9)) < 1e-9
    assert transfer['source'] == 'exported warp shader evaluated on flat colours'


def test_nonlinear_warp_transfer_reports_retention_per_level_and_iterated_halving(monkeypatch):
    # Dim content is kept whole (0.25 -> 0.25), bright content is cut: W(1)-W(0) alone would claim
    # almost instant fading. Iterating the table from full level gives the true halving time.
    import feedback_equilibrium
    import preset_recipe as R
    table = {'levels': [0., .25, .5, .75, 1.], 'rgb': [[0.] * 3, [.25] * 3, [.41] * 3, [.34] * 3, [.45] * 3]}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'warp' else None)
    facts = {'/analysis/visual_description/static_behaviour/feedback_persistence': {'decay_gain': None}}
    transfer = R._render(facts)['feedback']['warp_transfer']
    assert transfer['linear'] is False
    assert transfer['retention_by_level'][0] == {'level': .25, 'retention': 1.}
    assert transfer['halving_frames'] == 1  # 1.0 -> 0.45 in one frame
    assert transfer['steady_level_from_full'] == .25  # 0.45 -> ... converges onto the identity segment


def test_custom_composite_flat_transfer_is_the_displayed_palette(monkeypatch):
    import feedback_equilibrium
    import preset_recipe as R
    table = {'levels': [0., .5, 1.], 'rgb': [[0., 0., 0.], [.6, .4, .1], [.9, .7, .2]]}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'composite' else None)
    composite = R._render({})['composite']
    assert composite['flat_transfer']['rgb'] == table['rgb']
    assert composite['flat_transfer']['source'] == 'exported composite shader evaluated on flat canvas colours'
    assert composite['flat_transfer']['time_varying'] is False


def test_flat_transfer_that_moves_between_times_is_time_varying(monkeypatch):
    import feedback_equilibrium
    import preset_recipe as R
    table = {'levels': [0., 1.], 'rgb': [[0., 0., 0.], [.6, .8, .5]], 'rgb_spread': [[0., 0., 0.], [.2, .03, .25]], 'times': [2., 5., 8.]}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'composite' else None)
    assert R._render({})['composite']['flat_transfer']['time_varying'] is True


def test_recipe_carries_the_steady_state_hue_from_the_equilibrium(monkeypatch):
    import feedback_equilibrium
    import preset_recipe as R
    # Other keys the descriptor reads from the same equilibrium record.
    extra = {'display_local_luma': .2, 'display_spread_luma': .3, 'display_local_saturation': .7,
             'display_spread_saturation': .6, 'drawn_area_fraction': .1, 'elements': 1,
             'gain_rgb': [.9, .9, .9], 'offset_rgb': [0., 0., 0.], 'energy_rgb_per_frame': [.01, .01, .01]}
    monkeypatch.setattr(feedback_equilibrium, 'equilibrium', lambda summary: {
        'display_local_rgb': [.25, .15, .06], 'display_spread_rgb': [.5, .32, .21], 'canvas_local_rgb': [.3, .2, .1],
        'composite_model': 'composite_transfer', 'substitution_count': 1, **extra})
    state = R.build_recipe(record())['render']['feedback']['steady_state']
    assert state['display_local_rgb'] == [.25, .15, .06] and state['hue_family'] == 'orange'
    assert state['level_note'].startswith('a lower bound')
    monkeypatch.setattr(feedback_equilibrium, 'equilibrium', lambda summary: {
        'display_local_rgb': [0., 0., 0.], 'display_spread_rgb': [.001, .001, .001], 'canvas_local_rgb': [0., 0., 0.],
        'composite_model': 'legacy', 'substitution_count': 0, **extra})
    assert R.build_recipe(record())['render']['feedback']['steady_state']['hue_family'] is None


def _graph_linear(terms):
    """sum(coefficient*input) as an exported expression graph."""
    nodes=[];products=[]
    for name,coefficient in terms:
        nodes+=[{'op':'input','args':[],'detail':{'name':name}},{'op':'constant','args':[],'detail':{'value':coefficient}}]
        nodes.append({'op':'multiply','args':[len(nodes)-2,len(nodes)-1],'detail':{}});products.append(len(nodes)-1)
    root=products[0]
    for index in products[1:]:
        nodes.append({'op':'add','args':[root,index],'detail':{}});root=len(nodes)-1
    return {'root':root,'nodes':nodes,'complete':True}


def test_circle_wave_reports_the_effective_radius_with_the_mystery_offset():
    recipe=build_recipe(summary(
        ('construction',BASE+'/elements/0/id','builtin_wave'),
        ('audio',BASE+'/elements/0/waveform_recipe',{'form_name':'audio_deformed_circle','effective_mode':0,
            'wave_x':.5,'wave_y':.5,'normalized_mystery':-.58,'base_radius_model_units':.5,'sample_radial_gain':.4})))
    wave=next(layer for layer in recipe['render']['layers'] if layer.get('builtin_wave'))['builtin_wave']
    # Circle.cpp: radius = 0.5 + 0.4*pcm + mystery, drawn as |radius| around the centre.
    assert abs(wave['effective_base_radius_model_units']+.08)<1e-9
    assert wave['base_radius_model_units']==.5


def test_max_normalised_wave_colour_states_the_gate_and_unit_band_values():
    recipe=build_recipe(summary(
        ('construction',BASE+'/elements/0/id','builtin_wave'),
        ('audio',BASE+'/elements/0/waveform_recipe',{'form_name':'audio_deformed_circle','effective_mode':0,
            'control_expressions':{'wave_r':_graph_linear([('treb',.005),('bass',.005)]),'wave_g':_graph_linear([('bass',.005)]),
                                   'wave_b':_graph_linear([('bass',0.)])}}),
        ('colour',BASE+'/elements/0/wave_material',{'normalization_enabled':True,'blend_mode':'source_alpha_over',
            'channels':{'wave_r':{'raw_time_curve':{'curve_kind':'unknown'}},'wave_g':{'raw_time_curve':{'curve_kind':'unknown'}}}})))
    colour=next(layer for layer in recipe['render']['layers'] if layer.get('builtin_wave'))['colour']
    assert colour['max_normalised'] is True
    assert colour['max_normalise_rule']['threshold']==.01
    # projectM's bass/mid/treb hover around 1: here the largest channel sits exactly on the gate.
    assert abs(colour['channels']['wave_r']['value_at_unit_bands']-.01)<1e-12
    assert abs(colour['channels']['wave_g']['value_at_unit_bands']-.005)<1e-12
    assert colour['channels']['wave_r']['frame_expression']['complete']


def test_channel_selective_warp_transfer_reports_persistence_per_channel(monkeypatch):
    # ret = 0; ret.x = main.x - (blur3.x - blur1.x): on flat content red is kept whole and green/blue
    # are cleared. A channel mean would claim a third kept per frame (halving in 0.6 frames).
    import feedback_equilibrium
    table = {'levels': [0., .25, .5, .75, 1.], 'rgb': [[c, 0., 0.] for c in (0., .25, .5, .75, 1.)]}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'warp' else None)
    recipe = build_recipe(summary(('feedback', STATIC + '/feedback_persistence', {'decay_gain': None})))
    transfer = recipe['render']['feedback']['warp_transfer']
    assert transfer['channel_selective'] is True
    red, green = transfer['per_channel']['r'], transfer['per_channel']['g']
    assert red['gain'] == 1. and red['halving_frames'] is None and red['steady_level_from_full'] == 1.
    assert green['gain'] == 0. and green['halving_frames'] == 1 and green['steady_level_from_full'] == 0.
    assert transfer['halving_frames'] is None  # no single channel-mean persistence
    trails = next(e for e in recipe['intent']['effects'] if e['effect'] == 'trails')
    assert trails['half_life_s'] is None and trails['decay_per_frame'] == 1.


def test_composite_hue_shader_reports_periods_range_and_random_phase():
    import math
    hue = {'policy': 'source31-native-composite-hue-v1', 'consumed_rgb_components': [0, 1, 2],
           'raw_corner': {'angular_rate_rad_per_second_rgb': [30 * .0143, 30 * .0107, 30 * .0129]},
           'nominal_input_range_rgb': [[.75, 1.]] * 3, 'random_phase_lifetime': 'preset instance, selected at initialization'}
    recipe = build_recipe(summary(('construction', BASE + '/elements/0/id', 'shader_composite'),
                                  ('construction', BASE + '/elements/0/stage', 'composite'),
                                  ('colour', BASE + '/elements/0/native_colour_generators', [hue])))
    shader = recipe['render']['composite']['hue_shader']
    assert shader['channels'] == ['r', 'g', 'b']
    assert abs(shader['cycle_periods_seconds_rgb'][0] - 2 * math.pi / (30 * .0143)) < 1e-9
    assert shader['range_rgb'] == [[.75, 1.]] * 3
    assert 'random' in shader['phase']


def test_wrapping_warp_transfer_reports_a_level_cycle_not_a_halving(monkeypatch):
    # ret = frac(ret - 0.005) with a small dither: interior levels step down 0.005 per frame and
    # black wraps to near white, so every level cycles through the range every 200 frames.
    import feedback_equilibrium
    table = {'levels': [0., .25, .5, .75, 1.],
             'rgb': [[.92] * 3, [.245] * 3, [.495] * 3, [.745] * 3, [.92] * 3]}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'warp' else None)
    recipe = build_recipe(summary(('feedback', STATIC + '/feedback_persistence', {'decay_gain': None})))
    transfer = recipe['render']['feedback']['warp_transfer']
    assert abs(transfer['wrap']['shift_per_frame'] + .005) < 1e-9
    assert abs(transfer['wrap']['cycle_frames'] - 200) < 1e-6
    assert transfer['halving_frames'] is None and transfer['steady_level_from_full'] is None
    cycling = next(e for e in recipe['intent']['effects'] if e['effect'] == 'level_cycling')
    assert abs(cycling['cycle_s'] - 200 / 30) < 1e-6
    assert next(e for e in recipe['intent']['effects'] if e['effect'] == 'trails')['decay_per_frame'] is None


def test_per_load_random_switches_report_their_probability():
    # static const float sw1 = rand_preset.x >= .4; ... noise.r <= rand_preset.y
    nodes = [{'op': 'input', 'args': [], 'detail': {'name': 'rand_preset'}},
             {'op': 'member', 'args': [0], 'detail': {'field': 'x', 'swizzle': True}},
             {'op': 'constant', 'args': [], 'detail': {'value': .4}},
             {'op': 'greater_equal', 'args': [1, 2], 'detail': {}},
             {'op': 'member', 'args': [0], 'detail': {'field': 'y', 'swizzle': True}},
             {'op': 'input', 'args': [], 'detail': {'name': 'noise'}},
             {'op': 'less_equal', 'args': [5, 4], 'detail': {}},
             {'op': 'multiply', 'args': [3, 6], 'detail': {}}]
    program = {'root': 7, 'nodes': nodes}
    recipe = build_recipe(summary(('construction', BASE + '/stage_programs',
                                   {'stages': {'composite': {'status': 'exported', 'program': program}}})))
    switches = recipe['render']['composite']['per_load_random']
    assert switches['switches'] == [{'component': 'x', 'condition': '>= 0.4', 'probability_true': .6}]
    assert switches['continuous_components'] == ['y']
    variant = next(e for e in recipe['intent']['effects'] if e['effect'] == 'per_load_variant')
    assert variant == {'effect': 'per_load_variant', 'stage': 'composite', 'condition': 'rand_preset.x >= 0.4', 'probability_true': .6}
    assert 'rand_preset.x >= 0.4 (true in 60% of preset loads)' in recipe['description']


def test_random_redraw_events_of_the_random_palette_template():
    # mq21 = if(above(sin(time*.5), .9999), rand(3), mq21); q21 = mq21
    update = {'root': 0, 'nodes': [
        {'op': 'select', 'args': [1, 7, 9], 'detail': {}}, {'op': 'greater', 'args': [2, 6], 'detail': {}},
        {'op': 'sin', 'args': [3], 'detail': {}}, {'op': 'multiply', 'args': [4, 5], 'detail': {}},
        {'op': 'input', 'args': [], 'detail': {'name': 'time'}}, {'op': 'constant', 'args': [], 'detail': {'value': .5}},
        {'op': 'constant', 'args': [], 'detail': {'value': .9999}}, {'op': 'rand', 'args': [8], 'detail': {}},
        {'op': 'constant', 'args': [], 'detail': {'value': 3.}}, {'op': 'input', 'args': [], 'detail': {'name': 'mq21'}}]}
    initial = {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 0.}}]}
    q21 = {'root': 0, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'mq21'}}]}
    frame = {'status': 'exported', 'state': {'mq21': {'initial': initial, 'update': update}}, 'outputs': {'q21': q21}}
    recipe = build_recipe(summary(('construction', BASE + '/stage_programs', {'frame': frame, 'stages': {}})))
    redraw = recipe['render']['random_redraws']
    assert redraw['states'] == ['mq21'] and redraw['feeds'] == ['q21']
    # sin(t/2) > .9999 near t = pi + 4 pi k: first event about 3.1 s, then every 12.6 s.
    assert abs(redraw['event_times_s'][0] - math.pi) < .1
    assert abs(redraw['period_s'] - 4 * math.pi) < .1
    assert any(e['effect'] == 'random_redraw' for e in recipe['intent']['effects'])


def test_legacy_fshader_tint_is_reported_with_random_phase():
    recipe = build_recipe(summary(('feedback', BASE + '/legacy_response',
                                   {'tint_amount': 1.0, 'native_control_ranges': {}, 'gamma_absolute_weight_sum_upper': 1.0})))
    tint = recipe['render']['composite']['legacy_hue_tint']
    assert tint['amount'] == 1.0 and 'random' in tint['phase']


def test_neighbourhood_blur_mechanism_is_a_blur_effect_with_its_radius_drivers():
    data=record()
    data['facts']['construction'].append({'path':'/analysis/families/1','value':{'mechanism':'neighbourhood_blur','stage':'warp',
        'parameters':{'taps':8,'radius_spatial':True,'radius_audio':True,'radius_time':False,'offsets':[.01]}}})
    blur,=[e for e in build_recipe(data)['intent']['effects'] if e['effect']=='blur']
    assert blur=={'effect':'blur','stage':'warp','taps':8,'radius_spatial':True,'radius_audio':True,'radius_time':False,'offsets':[.01]}


def test_gradient_relief_mechanism_is_a_relief_effect():
    data=record()
    data['facts']['construction'].append({'path':'/analysis/families/1','value':{'mechanism':'gradient_relief','stage':'composite',
        'parameters':{'directions':2}}})
    relief,=[e for e in build_recipe(data)['intent']['effects'] if e['effect']=='relief']
    assert relief=={'effect':'relief','stage':'composite','directions':2}


def test_flat_transfer_of_a_relief_composite_covers_flat_areas_only(monkeypatch):
    import feedback_equilibrium
    import preset_recipe as R
    table={'levels':[0.,1.],'rgb':[[.04,.03,.05],[.04,.03,.05]]}
    monkeypatch.setattr(feedback_equilibrium,'stage_transfer',lambda facts,stage,**_:table if stage=='composite' else None)
    relief={'/analysis/families/0':{'mechanism':'gradient_relief','stage':'composite','parameters':{'directions':2}}}
    assert R._render(relief)['composite']['flat_transfer']['flat_areas_only'] is True
    assert R._render({})['composite']['flat_transfer']['flat_areas_only'] is False


def test_composite_whose_output_is_mostly_non_finite_is_marked_undefined(monkeypatch):
    import feedback_equilibrium
    import preset_recipe as R
    table = {'levels': [0., 1.], 'rgb': [[0., 0., 0.], [0., 0., 0.]], 'nonfinite_share': 1.}
    monkeypatch.setattr(feedback_equilibrium, 'stage_transfer', lambda facts, stage, **_: table if stage == 'composite' else None)
    assert R._render({})['composite']['flat_transfer']['output_undefined'] is True


def test_random_texture_samplers_are_listed_as_random_per_load():
    import preset_recipe as R
    program = {'root': 0, 'nodes': [{'op': 'sample', 'args': [], 'detail': {'sampler': 'sampler_rand00', 'canonical_texture': 'rand00'}},
                                    {'op': 'sample', 'args': [], 'detail': {'sampler': 'sampler_rand02_smalltiled', 'canonical_texture': 'rand02_smalltiled'}},
                                    {'op': 'sample', 'args': [], 'detail': {'sampler': 'sampler_main', 'canonical_texture': 'main'}}]}
    facts = {BASE + '/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': program}}}}
    rows = R._render(facts)['random_textures']
    assert rows == [{'stage': 'composite', 'slot': '00', 'name_filter': None}, {'stage': 'composite', 'slot': '02', 'name_filter': 'smalltiled'}]


def test_display_is_exact_when_nothing_feeds_the_canvas_and_the_composite_is_constant():
    # r100: no drawn layers, so the canvas stays at its cleared black; the composite maps black to white
    # with no spread at any sampled time, so the whole display is exactly white (not a lower bound).
    from preset_recipe import _display_is_exact
    empty = {'elements': 0, 'energy_rgb_per_frame': [0., 0., 0.], 'offset_rgb': [0., 0., 0.], 'substitution_count': 0}
    flat = {'levels': [0., .5, 1.], 'rgb': [[1., 1., 1.]] * 3, 'rgb_spread': [[0., 0., 0.]] * 3, 'time_varying': False, 'output_undefined': False}
    assert _display_is_exact(empty, flat)
    assert not _display_is_exact({**empty, 'elements': 1}, flat)
    assert not _display_is_exact({**empty, 'offset_rgb': [.01, 0., 0.]}, flat)
    assert not _display_is_exact(empty, {**flat, 'time_varying': True})
    assert not _display_is_exact(empty, {**flat, 'rgb_spread': [[.2, 0., 0.]] + [[0., 0., 0.]] * 2})
    assert not _display_is_exact(empty, None)


def test_offline_display_statistics_join_the_display_estimate_as_simulated():
    # facet_precompute's record (static prediction stepped and measured with the ruler's statistics) reaches
    # readers next to the calibrated estimate; r130 squeakers: calibrated saturation 0.33, simulated 0.68, real 0.65.
    from contract_schema import recipe_errors
    stats = {'mean_luminance': .126, 'mean_abs_frame_difference': .041, 'mean_flow_screen_widths_per_s': .2,
             'global_brightness_jumps_per_10s': 0., 'mean_saturation': .676, 'warm_cool': .41, 'peak_brightness_change': .02}
    record_ = {'policy': 'static-prediction-facet-statistics-v1', 'status': 'predicted', 'depends_on_seed': False, 'seeds': [None],
               'statistics': stats, 'random_flash': {'probability_per_frame': 0.}, 'random_texture_dependent': False}
    recipe = build_recipe(record(), display_statistics=record_)
    simulated = recipe['display_estimate']['simulated']
    assert simulated['statistics']['mean_saturation'] == .676 and simulated['peak_brightness_change'] == .02
    assert simulated['uses_rendered_images'] is False and 'frames 60-299' in simulated['reference']
    assert not recipe_errors(recipe)
    assert 'simulated' not in (build_recipe(record()).get('display_estimate') or {})
    assert 'simulated' not in (build_recipe(record(), display_statistics={'status': 'error'}).get('display_estimate') or {})


def test_simulated_display_reports_hues_and_per_load_variety():
    # r130 squeakers redraws random values at every load: seeds give green-, blue- and pink-led palettes, all with
    # orange. The reader needs the hue shares and each load's outcome, not only a seed-averaged warm/cool.
    runs = [{'seed': 1, 'mean_luminance': .24, 'mean_saturation': .52, 'warm_cool': .14, 'coloured_share': .6,
             'hue_shares': {'green': .28, 'orange': .25, 'blue': .14}},
            {'seed': 2, 'mean_luminance': .33, 'mean_saturation': .45, 'warm_cool': -.12, 'coloured_share': .62,
             'hue_shares': {'blue': .36, 'green': .29, 'orange': .24}}]
    record_ = {'policy': 'static-prediction-facet-statistics-v1', 'status': 'predicted', 'depends_on_seed': True, 'seeds': [1, 2],
               'statistics': {'mean_luminance': .285}, 'runs': runs}
    simulated = build_recipe(record(), display_statistics=record_)['display_estimate']['simulated']
    assert simulated['hue_shares'] == {'green': .285, 'orange': .245, 'blue': .25}
    assert list(simulated['hue_shares'])[0] == 'green' and math.isclose(simulated['coloured_share'], .61)
    assert [row['top_hues'] for row in simulated['per_load']] == [['green', 'orange', 'blue'], ['blue', 'green', 'orange']]
    assert simulated['per_load'][1]['warm_cool'] == -.12


def test_strong_zoom_with_slow_trails_reads_as_radial_streaks():
    # r132: contraction of 2-10% per frame with a 1.8 s half-life smears every drawn detail into streaks toward
    # the centre (each retained copy is scaled again). The effect states the scale reached over one half-life.
    from preset_recipe import intent
    recipe=build_recipe(record())
    assert 'radial_streaks' not in [e['effect'] for e in recipe['intent']['effects']]  # 7-frame half-life
    recipe['mood']['features']['feedback.half_life_s']={'value':1.8}
    (streaks,)=[e for e in intent(recipe)['effects'] if e['effect']=='radial_streaks']
    assert streaks['direction']=='inward' and streaks['half_life_frames']==54
    assert math.isclose(streaks['radial_scale_over_half_life'],(1-.045)**54,rel_tol=1e-9)


def test_textured_shape_copying_the_previous_frame_reads_as_a_recursive_frame_copy():
    # EoS and Zylot - skylight: shape_0 is textured with the previous frame, tex_zoom .534 and tex_ang .94. Each
    # frame redraws a scaled, rotated copy inside the polygon, building a spiral tunnel with no mesh zoom or rotation.
    rec=record()
    groups=rec['facts']
    groups['construction'].append({'path':BASE+'/elements/1/material','value':{'texture':{'role':'previous_main','tex_zoom_source':.534,
                                                                                        'tex_angle_source_rad':.94}}})
    recipe=build_recipe(rec)
    layer=[l for l in recipe['render']['layers'] if l['id']=='shape_0'][0]
    assert layer['texture']=={'role':'previous_main','tex_zoom':.534,'tex_angle_rad':.94}
    (copy,)=[e for e in recipe['intent']['effects'] if e['effect']=='frame_copy']
    assert copy['layer']=='shape_0' and copy['tex_zoom']==.534 and copy['tex_angle_rad']==.94


def _mesh(sx_terms, zoom=1.):
    const = lambda v: {'status': 'described', 'uniform_across_mesh': True, 'value_range': [v, v], 'terms': [{'sign': 1, 'kind': 'constant', 'value': v}]}
    controls = {name: const(value) for name, value in (('zoom', zoom), ('zoomexp', 1.), ('rot', 0.), ('warp', 0.), ('cx', .4), ('cy', .6), ('dx', 0.), ('dy', 0.))}
    field = {'status': 'described', 'uniform_across_mesh': False, 'value_range': None, 'terms': sx_terms}
    return {'status': 'described', 'controls': {**controls, 'sx': field, 'sy': field}}


def _radius_terms(k=2.):
    # k*sqrt(sqr(x-.4)+sqr(y-.6)) as an exported expression graph
    n = lambda op, *args, **detail: {'op': op, 'dtype': 'float', 'args': list(args), 'detail': detail}
    nodes = [n('multiply', 1, 2), n('constant', value=k), n('sqrt', 3), n('add', 4, 8), n('sqr', 5), n('subtract', 6, 7),
             n('input', name='x'), n('constant', value=.4), n('sqr', 9), n('subtract', 10, 11), n('input', name='y'), n('constant', value=.6)]
    return [{'sign': 1, 'kind': 'nonlinear_coordinate_term', 'expression': {'root': 0, 'nodes': nodes}}]


def test_stretch_proportional_to_radius_samples_one_point_per_ray():
    # r162 fat cancer: sx=sy=zm*rd about (cx, cy). The engine samples c+(p-c)/s, so with s proportional to the
    # distance from c every pixel on a ray reads the same source point: each frame becomes rays converging on c.
    from preset_recipe import ray_sampling
    rays = ray_sampling(_mesh(_radius_terms()))
    assert rays['ray_constant_share'] > .9 and rays['centre_xy'] == [.4, .6]
    const = {'sign': 1, 'kind': 'constant', 'value': 1.1}
    assert ray_sampling(_mesh([const]))['ray_constant_share'] < .05     # a uniform stretch keeps radial structure
    assert ray_sampling(_mesh([{**const, 'value': 1.}], zoom=1.02))['ray_constant_share'] < .05


def _sine_channel(k, base=.25, amp=.25):
    n = lambda op, *args, **detail: {'op': op, 'args': list(args), 'detail': detail}
    return {'root': 0, 'nodes': [n('add', 1, 2), n('constant', value=base), n('multiply', 3, 4), n('constant', value=amp),
                                 n('sin', 5), n('multiply', 6, 7), n('input', name='time'), n('constant', value=k)]}


def test_shape_colour_over_time_samples_closed_form_channels():
    # r165: shape channels are .25+.25*sin(time*k) with a different k per channel, so the hue drifts over time;
    # the recipe reported the palette as unresolved although every channel is a closed-form function of time.
    from preset_recipe import shape_colour_over_time
    channels = {'centre': {'r': _sine_channel(.7679), 'g': _sine_channel(.8079), 'b': _sine_channel(.7339), 'a': _sine_channel(0, 1, 0)},
                'perimeter': {'r2': _sine_channel(.6979), 'g2': _sine_channel(.849), 'b2': _sine_channel(.8079), 'a2': _sine_channel(0, 1, 0)}}
    c = shape_colour_over_time({'channel_expressions': channels})
    assert c['centre_rgb_range'][0][0] >= 0 and c['centre_rgb_range'][0][1] <= .5 + 1e-6
    assert c['mean_saturation'] > .2 and len(c['hue_shares']) >= 3
    assert shape_colour_over_time({'channel_expressions': {'centre': {'r': None}}}) is None



def test_textured_shape_colour_over_time_is_labelled_as_a_tint():
    # r198 Wavering Flower: a textured disc with colour 0.9 copies a dark previous frame; the reader took 0.9 as
    # a light-grey fill and called the preset bright. Colours of a previous_main shape are a tint.
    from preset_recipe import _layer
    base = '/analysis/visual_description/elements/0'
    channels = {'centre': {c: _sine_channel(0, .9, 0) for c in 'rgb'}, 'perimeter': {c + '2': _sine_channel(0, .9, 0) for c in 'rgb'}}
    textured = {base + '/id': 'shape_0', base + '/material': {'channel_expressions': channels, 'texture': {'role': 'previous_main'}}}
    assert 'tint' in _layer(textured, 0)['colour_over_time']['role']
    filled = {base + '/id': 'shape_0', base + '/material': {'channel_expressions': channels, 'texture': {'role': 'untextured_vertex_gradient'}}}
    assert 'role' not in _layer(filled, 0)['colour_over_time']


def test_display_palette_pools_static_colour_sources():
    # Colour-through-feedback gap: 24% of coloured presets had no static hue cue although their wave or point
    # colours were in the recipe. display_palette pools element colours, the steady state and the composite.
    from preset_recipe import display_palette
    recipe = {'render': {'layers': [
        {'id': 'wave_0', 'point_cloud': {'colour_resolved': True, 'hue_family_shares': {'pink': .6, 'green': .3, 'grayscale': .1}, 'mean_alpha': .5}},
        {'id': 'wave_1', 'colour': {'channels': {'wave_r': {'curve_kind': 'constant', 'constant_value': .1},
                                                 'wave_g': {'curve_kind': 'constant', 'constant_value': .2},
                                                 'wave_b': {'curve_kind': 'constant', 'constant_value': .9}}, 'max_normalised': True}}],
        'feedback': {'steady_state': {'hue_family': 'grayscale'}}, 'composite': {}}}
    p = display_palette(recipe)
    assert set(p['hue_shares']) >= {'pink', 'blue'} and abs(sum(p['hue_shares'].values()) - 1) < 1e-6
    vivid = {'render': {'layers': [], 'feedback': {}, 'composite': {'detail_response': {'coloured_share': .9, 'hue_shares': {'yellow': .9, 'orange': .1}}}}}
    assert next(iter(display_palette(vivid)['hue_shares'])) == 'yellow'
    assert display_palette({'render': {'layers': [], 'feedback': {}, 'composite': {}}})['hue_shares'] == {}
