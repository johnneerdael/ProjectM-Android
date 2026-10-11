"""Local brightness controls: frequency alone does not establish visible flashing."""
import math
import os
from types import SimpleNamespace

import pytest
from shader_fields import Field


def const(value):
    return Field('constant', dtype='float', detail={'value':value})


def inp(name):
    return Field('input', dtype='float', detail={'name':name})


def op(name, *args, dtype='float'):
    return Field(name, tuple(args), dtype)


def oscillator(amplitude=.5, omega=60.):
    return op('add',const(.5),op('multiply',const(amplitude),op('sin',op('multiply',const(omega),inp('time')))))


def evidence(field, *, domains=None):
    from source_flash_behaviour import flash_evidence
    analysis=SimpleNamespace(outputs={'composite':Field('construct',(field,field,field),'float3')},
                             input_scenario=None,component_controls={},source={})
    return flash_evidence(analysis,{'elements':[]},
                          {'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':domains or {}})


def shader_record(result):
    return next(r for r in result['records'] if r['component_id']=='shader_composite')


def test_smooth_fast_brightness_reports_rate_and_large_contrast_separately():
    r=shader_record(evidence(oscillator()))
    assert r['maximum_brightness_change_per_second']==pytest.approx(30.)
    assert r['brightness_delta_range']==pytest.approx([0.,1.])
    assert r['cycle_rate_hz']==pytest.approx(60/math.tau)
    assert r['event_rate_hz'] is None
    assert r['visible_flashing_verified'] is False


def test_same_fast_frequency_with_small_amplitude_has_small_delta_and_rate():
    r=shader_record(evidence(oscillator(.001)))
    assert r['brightness_delta_range'][1]==pytest.approx(.002)
    assert r['maximum_brightness_change_per_second']==pytest.approx(.06)


def test_shared_rgb_gate_schedule_is_not_three_event_frequencies():
    gate=op('greater',op('sin',op('multiply',const(60),inp('time'))),const(0),dtype='bool')
    r=shader_record(evidence(op('select',gate,const(1),const(0))))
    assert r['event_rate_hz']==pytest.approx(60/math.pi)
    assert len(r['event_schedules'])==1
    assert r['brightness_delta_range'][1]==pytest.approx(1.)
    assert r['maximum_brightness_change_per_second'] is None


def test_unreachable_sinusoid_gate_does_not_have_a_large_change_envelope():
    gate=op('greater',op('sin',inp('time')),const(2),dtype='bool')
    result=evidence(op('select',gate,const(1),const(.2)))
    r=shader_record(result)
    assert r['brightness_delta_range']==[0.,0.]
    assert r['maximum_brightness_change_per_second']==0
    assert result['rejected_predicates']


def test_missing_state_is_not_assumed_temporally_constant_or_zero():
    r=shader_record(evidence(inp('unknown_state')))
    assert r['brightness_delta_range'] is None
    assert r['total_brightness_rate_known'] is False
    assert any('state' in reason for reason in r['unknown_reasons'])


def test_independent_schedules_have_no_invented_joint_event_rate():
    first=op('greater',op('sin',inp('time')),const(0),dtype='bool')
    second=op('greater',op('sin',op('multiply',const(2),inp('time'))),const(0),dtype='bool')
    r=shader_record(evidence(op('add',op('select',first,const(.5),const(0)),
                                      op('select',second,const(.5),const(0)))))
    assert len(r['event_schedules'])==2
    assert r['event_rate_hz'] is None
    assert any('simultaneous' in reason for reason in r['unknown_reasons'])


def test_invalid_viewport_and_fps_are_rejected():
    from source_flash_behaviour import flash_evidence
    with pytest.raises(ValueError):
        flash_evidence(SimpleNamespace(outputs={}),{'elements':[]},{'viewport':[0,1080],'feedback_fps':0})


def test_random_material_exports_independent_difference_without_total_flash_credit():
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1='
        'r=rand(100)/100;g=r;b=r;r2=r;g2=r;b2=r;a=.5;a2=.5;border_a=0;\n')
    row=next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    partial=row['stochastic_material_partial']
    assert .49<partial['maximum_rng_induced_frame_rgb_infinity_norm_difference']<.51
    assert partial['maximum_frame_refresh_opportunities_per_second']==30
    assert row['total_brightness_rate_known'] is False
    assert row['event_rate_hz'] is None
    assert row['visible_flashing_verified'] is False


def test_init_random_colour_zero_refresh_does_not_make_changing_alpha_constant():
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_init1=shade=rand(100)/100;\n'
        'shape_0_per_frame1=r=shade;g=r;b=r;r2=r;g2=r;b2=r;a=.5+.4*sin(time);a2=a;border_a=0;\n')
    row=next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    partial=row['stochastic_material_partial']
    assert partial['maximum_frame_refresh_opportunities_per_second']==0
    assert partial['maximum_rng_induced_frame_rgb_infinity_norm_difference']==0
    assert partial['maximum_local_rgb_infinity_norm_difference']>.7
    assert row['total_brightness_rate_known'] is False


def test_sympy_cancellation_changes_the_actual_derivative_bound():
    from source_symbolic import SymbolicSession
    python=os.environ.get('MILK_SYMBOLIC_PYTHON')
    if not python:pytest.skip('pinned SymPy worker required')
    wave=op('sin',op('multiply',const(60),inp('time')))
    with SymbolicSession(python):
        r=shader_record(evidence(op('subtract',wave,wave)))
    assert r['maximum_brightness_change_per_second']==0
    assert any(c.get('symbolic_refinement',{}).get('status')=='bounded' for c in r['source_evidence']['channel_responses'])


def test_z3_rejects_relationally_impossible_nominal_branch_with_native_caveat():
    from source_proofs import ProofSession
    python=os.environ.get('MILK_PROOF_PYTHON')
    if not python:pytest.skip('pinned Z3 worker required')
    x=inp('bass');gate=op('less',op('multiply',x,x),const(0),dtype='bool')
    with ProofSession(python):result=evidence(op('select',gate,const(1),const(.2)),domains={'bass':[-2,2]})
    assert shader_record(result)['brightness_delta_range']==[0.,0.]
    proof=result['rejected_predicates'][0]['nominal_proof']
    assert proof['truth_value'] is False and proof['backend']['z3_version']=='5.1.0.0'
    assert result['rejected_predicates'][0]['native_numeric_certified'] is False


def source_evidence(raw):
    from test_effect_families import read
    from effect_families import _Analysis
    from source_appearance import appearance_from_analysis
    from source_flash_behaviour import flash_evidence
    a=_Analysis(read(raw),'gles300',{})
    a.input_scenario=None
    a.main_equations();a.primitives();a.shader('warp','warp_');a.shader('composite','comp_');a.contribution_gates()
    return flash_evidence(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30})


def test_fully_transparent_shape_cannot_have_brightness_modulation():
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=.5+.4*sin(60*time);r2=r;a=0;a2=0;border_a=0;\n')
    shape=[r for r in result['records'] if r['component_id']=='shape_0']
    assert not result['source_hazards']
    assert all(r['brightness_delta_range']==[0.,0.] and r['maximum_brightness_change_per_second']==0 for r in shape)


def test_real_shape_high_frequency_modulation_preserves_alpha_weighting():
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=.5+.4*sin(60*time);r2=r;g=0;g2=0;b=0;b2=0;a=.5;a2=.5;border_a=0;additive=1;\n')
    r=next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    assert r['maximum_brightness_change_per_second']==pytest.approx(12,abs=1e-6)
    assert r['brightness_delta_range'][1]>=.4
    assert r['cycle_rate_hz']==pytest.approx(60/math.tau)


def test_pure_uniform_shader_reports_attainable_nominal_periodic_contrast():
    r=shader_record(evidence(oscillator(.4)))
    assert r['periodic_contrast_range']==pytest.approx([.8,.8])
    assert r['brightness_value_range']==pytest.approx([.1,.9])


def test_impossible_bool_multiplier_is_zero_without_a_phantom_event():
    gate=op('greater',op('sin',inp('time')),const(2),dtype='bool')
    r=shader_record(evidence(op('multiply',const(.9),Field('cast',(gate,),'float'))))
    assert r['brightness_delta_range']==[0.,0.]
    assert r['maximum_brightness_change_per_second']==0
    assert not r['event_schedules']


def test_native_expression_counterexample_does_not_prune_a_nominal_gate():
    from source_proofs import ProofSession
    python=os.environ.get('MILK_PROOF_PYTHON')
    if not python:pytest.skip('pinned Z3 worker required')
    x=inp('bass')
    gate=op('equal',op('subtract',op('add',const(1),x),x),const(1),dtype='bool')
    with ProofSession(python):result=evidence(op('select',gate,const(1),const(.2)),domains={'bass':[16777216,16777216]})
    r=shader_record(result)
    assert r['brightness_delta_range'][1]>.79
    assert result['rejected_predicates'][0]['rejection_applied'] is False
    assert result['rejected_predicates'][0]['native_expression_proof']['truth_value'] is False


def test_known_invalid_contributing_brightness_does_not_become_zero():
    r=shader_record(evidence(op('multiply',oscillator(),op('divide',const(1),const(0)))))
    assert r['maximum_brightness_change_per_second'] is None
    assert r['brightness_delta_range'] is None
    assert r['unknown_reasons']


def test_modulo_shape_retains_boundary_mechanism_with_unknown_visible_cadence():
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=1+.1*sin(60*time);r2=r;a=.5;a2=.5;border_a=0;\n')
    r=next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    assert r['source_evidence']['nominal_modulo_schedules']
    assert r['event_rate_hz'] is None
    assert r['maximum_brightness_change_per_second'] is None
    assert any(h['kind']=='shape_channel_modulo_crossing' for h in result['source_hazards'])


def test_real_sample_multiplier_has_smooth_cycle_but_no_attained_contrast_claim():
    result=source_evidence('PSVERSION_COMP=2\ncomp_1=`shader_body {ret=GetPixel(uv)*(.5+.4*sin(time*60));}\n')
    r=shader_record(result)
    assert r['maximum_brightness_change_per_second']==pytest.approx(24.)
    assert r['cycle_rate_hz']==pytest.approx(60/math.tau)
    assert r['periodic_contrast_range'] is None
    assert r['total_brightness_rate_known'] is False


def test_sample_coordinate_gate_is_not_direct_colour_event_schedule():
    field=Field('sample',(Field('construct',(op('select',op('greater',op('sin',inp('time')),const(0),dtype='bool'),const(1),const(0)),const(.5)),'float2'),),'float',{'canonical_texture':'main'})
    r=shader_record(evidence(field))
    assert not r['event_schedules']
    assert r['event_rate_hz'] is None
    assert r['brightness_delta_range'] is None


def test_declared_audio_domains_bound_brightness_but_do_not_supply_audio_rate():
    r=shader_record(evidence(op('multiply',inp('bass'),oscillator()),domains={'bass':[0,2]}))
    assert r['maximum_brightness_change_per_second']==pytest.approx(60)
    assert r['total_brightness_rate_known'] is False
    assert any('audio/state' in reason for reason in r['unknown_reasons'])


def test_native_shader_numeric_marker_remains_a_symbolic_guard():
    from source_symbolic import SymbolicSession
    python=os.environ.get('MILK_SYMBOLIC_PYTHON')
    if not python:pytest.skip('pinned SymPy worker required')
    with SymbolicSession(python):
        r=shader_record(source_evidence('PSVERSION_COMP=2\ncomp_1=`shader_body {ret=sin(time*60)-sin(time*60);}\n'))
    assert r['maximum_brightness_change_per_second']>=120
    assert any(c.get('symbolic_refinement',{}).get('status')=='unsupported' for c in r['source_evidence']['channel_responses'])


def test_packed_shader_predicate_does_not_erase_native_arithmetic_to_force_proof():
    from source_proofs import ProofSession
    from source_input_scenario import validate_scenario
    from source_appearance import appearance_from_analysis
    from source_flash_behaviour import flash_evidence
    from effect_families import _Analysis
    from test_effect_families import shader
    python=os.environ.get('MILK_PROOF_PYTHON')
    if not python:pytest.skip('pinned Z3 worker required')
    a=_Analysis(shader('shader_body {ret=(bass*bass<0) ? 1 : .2;}'),'gles300',{})
    a.input_scenario=validate_scenario({'schema_version':1,'name':'declared-bass','audio_band_ranges':{'bass':[0,2]}})
    a.main_equations();a.primitives();a.shader('warp','warp_');a.shader('composite','comp_');a.contribution_gates()
    with ProofSession(python):
        result=flash_evidence(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30})
    assert shader_record(result)['brightness_delta_range'][1]>.79
    assert not result['rejected_predicates']


def test_real_eel_shape_uses_sympy_to_tighten_nominal_material_rate():
    from source_symbolic import SymbolicSession
    python=os.environ.get('MILK_SYMBOLIC_PYTHON')
    if not python:pytest.skip('pinned SymPy worker required')
    raw='fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=r=.5+.2*(sin(60*time)-sin(60*time));r2=r;g=0;g2=0;b=0;b2=0;a=.5;a2=.5;border_a=0;additive=1;\n'
    baseline=source_evidence(raw)
    with SymbolicSession(python):refined=source_evidence(raw)
    a=next(r for r in baseline['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    b=next(r for r in refined['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    assert a['maximum_brightness_change_per_second']>=12
    assert b['maximum_brightness_change_per_second']==0
    assert b['source_evidence']['symbolic_channel_responses']['r']['symbolic_refinement']['status']=='bounded'


def test_real_eel_shape_uses_z3_to_reject_impossible_brightness_branch():
    from source_proofs import ProofSession
    from source_flash_behaviour import flash_evidence
    from source_appearance import appearance_from_analysis
    from effect_families import _Analysis
    from test_effect_families import read
    python=os.environ.get('MILK_PROOF_PYTHON')
    if not python:pytest.skip('pinned Z3 worker required')
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=r=if(below(bass*bass,0),.9,.2);r2=r;g=0;g2=0;b=0;b2=0;a=.5;a2=.5;border_a=0;additive=1;\n')
    a=_Analysis(source,'gles300',{});a.input_scenario=None;a.main_equations();a.primitives();a.contribution_gates()
    description=appearance_from_analysis(a)
    with ProofSession(python):
        result=flash_evidence(a,description,{'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'bass':[0,2]}})
    r=next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')
    assert r['brightness_delta_range']==[0.,0.]
    assert result['rejected_predicates'][0]['nominal_proof']['truth_value'] is False
    assert result['rejected_predicates'][0]['native_numeric_certified'] is False


def test_pruned_shape_does_not_retain_an_unreachable_modulo_hazard():
    from source_proofs import ProofSession
    from source_flash_behaviour import flash_evidence
    from source_appearance import appearance_from_analysis
    from effect_families import _Analysis
    from test_effect_families import read
    python=os.environ.get('MILK_PROOF_PYTHON')
    if not python:pytest.skip('pinned Z3 worker required')
    a=_Analysis(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=r=if(below(bass*bass,0),1+.1*sin(time),.2);r2=r;a=.5;a2=.5;border_a=0;\n'),'gles300',{})
    a.input_scenario=None;a.main_equations();a.primitives();a.contribution_gates()
    with ProofSession(python):
        result=flash_evidence(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'bass':[0,2]}})
    assert not any(h['kind']=='shape_channel_modulo_crossing' for h in result['source_hazards'])


def textured_fill(body, config=''):
    result=source_evidence('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_textured=1\n'+config+
        'shape_0_per_frame1='+body+'\n')
    return next(r for r in result['records'] if r['component_id']=='shape_0' and r['part']=='fill')


def test_fixed_unit_texture_material_partial_recovers_rate_without_total_flash_claim():
    r=textured_fill('r=.5+.4*sin(60*time);r2=r;g=0;g2=0;b=0;b2=0;a=.5;a2=.5;border_a=0;additive=1;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second']==pytest.approx(12,abs=1e-6)
    assert p['brightness_delta_range'][1]>=.4
    assert p['total_brightness_rate_known'] is False
    assert p['texture_history_change_rate'] is None
    assert r['maximum_brightness_change_per_second'] is None
    assert r['total_brightness_rate_known'] is False


def test_moving_texture_keeps_total_unknown_when_material_partial_is_zero():
    r=textured_fill('r=.5;r2=.5;a=.5;a2=.5;tex_ang=time;border_a=0;additive=1;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second']==0
    assert p['sampling_coordinate_response_included'] is False
    assert p['total_brightness_rate_known'] is False
    assert r['maximum_brightness_change_per_second'] is None
    assert r['unknown_reasons']


def test_missing_texture_asset_binding_is_an_assumption_not_visible_flashing():
    r=textured_fill('r=.5+.4*sin(60*time);r2=r;a=.5;a2=.5;border_a=0;additive=1;',
                    'shapecode_0_image=absent-texture.png\n')
    p=r['fixed_unit_texture_material_partial']
    assert p['texture_binding_verified'] is False
    assert p['visible_flashing_verified'] is False
    assert p['brightness_delta_range'][0]==0
    assert p['declared_texture_rgba_domain']==[[0.,1.]]*4
    assert any('fixed' in x and 'RGBA' in x for x in p['premises'])


def test_texture_alpha_change_over_blend_accounts_for_destination_contrast():
    r=textured_fill('r=.8;r2=.8;g=.8;g2=.8;b=.8;b2=.8;a=.5+.1*sin(2*time);a2=a;border_a=0;additive=0;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second']==pytest.approx(.36,abs=1e-6)
    # Fixed texture RGB0/alpha1 and destination1 produce a .2 two-state
    # brightness difference from alpha alone. Untextured colour contrast.8
    # must not reduce that ceiling to.16.
    assert p['brightness_delta_range'][1]>=.2
    assert p['texture_history_change_rate'] is None


def test_fixed_texture_partial_retains_known_invalid_native_rgb_domain():
    r=textured_fill('r=1e100;r2=1e100;a=.5;a2=.5;border_a=0;additive=1;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second'] is None
    assert p['brightness_delta_range'] is None
    assert any('native' in x and 'domain' in x for x in p['unknown_reasons'])


def test_fixed_texture_partial_does_not_make_modulo_crossing_continuous():
    r=textured_fill('r=1+.1*sin(60*time);r2=r;a=.5;a2=.5;border_a=0;additive=1;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second'] is None
    assert p['brightness_delta_range'] is not None
    assert p['nominal_continuity']=='unknown'
    assert r['source_evidence']['nominal_modulo_schedules']


def test_unknown_blend_mode_has_no_fixed_texture_rate_or_difference_bound():
    r=textured_fill('r=.5+.4*sin(60*time);r2=r;a=.5;a2=.5;border_a=0;additive=bass;')
    p=r['fixed_unit_texture_material_partial']
    assert p['maximum_brightness_change_per_second'] is None
    assert p['brightness_delta_range'] is None
    assert any('blend' in reason for reason in p['unknown_reasons'])


def test_fixed_black_texture_over_rate_retains_full_destination_alpha_term():
    r=textured_fill('r=.9;r2=.9;g=.9;g2=.9;b=.9;b2=.9;a=.5+.1*sin(time);a2=a;border_a=0;additive=0;')
    p=r['fixed_unit_texture_material_partial']
    # At fixed T_rgb0,T_a1,D1, output=1-alpha and its nominal rate ceiling is.1.
    # The untextured positive-colour contrast ceiling.09 would be invalid.
    assert p['maximum_brightness_change_per_second']==pytest.approx(.19,abs=1e-6)
    assert p['maximum_brightness_change_per_second']>=.1
    assert p['source_evidence']['maximum_incoming_rgb_rate_per_second'][0]==pytest.approx(.09,abs=1e-6)
    assert p['source_evidence']['maximum_blended_rgb_rate_per_second'][0]>=.1
