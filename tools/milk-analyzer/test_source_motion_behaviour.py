"""Analytic movement controls; no rendered or simulated frames."""
import importlib.util
import math
import numpy as np
import pytest
from test_effect_families import read, shader


def evidence(source, context=None, scenario=None, selected_custom=False):
    assert importlib.util.find_spec('source_motion_behaviour'), 'quantified movement producer missing'
    from source_motion_behaviour import motion_evidence
    from effect_families import _Analysis
    from source_appearance import appearance_from_analysis
    compatibility = None
    if selected_custom:
        import hashlib
        compatibility = {}
        for stage, prefix in [('warp','warp_'),('composite','comp_')]:
            code = source['sections'].get(prefix, {}).get('source', '')
            if not code: continue
            compatibility[stage] = {'source_sha256': hashlib.sha256(code.encode()).hexdigest(),
                'request': {'code':code, 'stage':stage, 'profile':'gles300'},
                'translation': {'engine_archive_sha256': source['parser_inputs']['engine_archive_sha256']},
                'offline_accepted': True}
    analysis = _Analysis(source, 'gles300', compatibility)
    analysis.input_scenario = scenario
    analysis.main_equations(); analysis.primitives()
    analysis.shader('warp', 'warp_'); analysis.shader('composite', 'comp_')
    analysis.contribution_gates()
    description = appearance_from_analysis(analysis)
    return motion_evidence(analysis, description, context or {'viewport': [1000, 1000], 'feedback_fps': 30})


def native(body, context=None):
    return evidence(read('fWaveAlpha=0\nper_frame_1=zoomexp=1;warp=0;' + body + '\n'), context)


def contribution(result, kind, element_id=None):
    return next(row for row in result['contributions'] if row['kind'] == kind and
                (element_id is None or row['component_id'] == element_id))


def test_neutral_feedback_map_is_zero_with_native_gaps_retained():
    result = native('zoom=1;sx=1;sy=1;rot=0;dx=0;dy=0;')
    row = contribution(result, 'forward_content_transport')
    assert row['rms_speed_vp_per_second'] == 0
    assert row['maximum_speed_vp_per_second'] == 0
    assert result['visible_motion_speed_vp_per_second'] is None
    assert result['texel_alignment_included'] is False
    assert result['uses_rendered_images'] is False


def test_constant_translation_moves_content_every_step_with_inverse_direction():
    result = native('zoom=1;sx=1;sy=1;rot=0;dx=.03;dy=-.04;')
    row = contribution(result, 'forward_content_transport')
    assert row['mean_velocity_vp_per_second'] == pytest.approx([.9, -1.2], abs=1e-7)
    assert row['rms_speed_vp_per_second'] == pytest.approx(1.5, abs=1e-7)
    assert row['rate_kind'] == 'per_feedback_step'
    assert row['parameter_time_rate_is_motion_speed'] is False
    assert contribution(result, 'backward_sampling_displacement')['mean_velocity_vp_per_second'] == pytest.approx([-.9, 1.2], abs=1e-7)


def test_constant_zoom_transport_is_nonzero_despite_zero_temporal_derivative():
    row = contribution(native('zoom=1.1;sx=1;sy=1;rot=0;dx=0;dy=0;'), 'forward_content_transport')
    z = row['native_float32_controls']['zoom']
    assert row['rms_speed_vp_per_second'] == pytest.approx(30 * abs(z-1) / math.sqrt(6))
    assert row['maximum_speed_vp_per_second'] == pytest.approx(30 * abs(z-1) / math.sqrt(2))


@pytest.mark.parametrize('sx,sy,angle', [(1.3, .8, .3), (-1.3, .8, .3), (2., .3, 1.2)])
def test_combined_non_normal_and_orientation_reversing_transport_is_actual_matrix(sx, sy, angle):
    result = native(f'zoom=1.2;sx={sx};sy={sy};rot={angle};cx=.3;cy=.7;dx=.04;dy=-.02;')
    row = contribution(result, 'forward_content_transport')
    p = row['native_float32_controls']
    c, s = math.cos(p['rot']), math.sin(p['rot'])
    a = np.array([[c, -s], [s, c]]) @ np.diag([1/(p['zoom']*p['sx']), 1/(p['zoom']*p['sy'])])
    h = np.array([[c, -s], [s, c]]) @ np.diag([1/p['sx'], 1/p['sy']]) @ np.array([.5-p['cx'], .5-p['cy']]) + np.array([p['cx']-p['dx']-.5, p['cy']-p['dy']-.5])
    inv = np.linalg.inv(a); d = -inv @ h; delta = inv-np.eye(2)
    expected = 30*math.sqrt(d @ d + np.sum(delta*delta)/12)
    assert row['rms_speed_vp_per_second'] == pytest.approx(expected)
    assert row['mean_velocity_vp_per_second'] == pytest.approx(30*d)
    assert np.allclose(row['forward_matrix'], inv)


def test_viewport_aspect_and_explicit_fps_change_transport_units():
    a = contribution(native('zoom=1;sx=1;sy=1;rot=0;dx=0;dy=.03;', {'viewport':[1920,1080], 'feedback_fps':30}), 'forward_content_transport')
    b = contribution(native('zoom=1;sx=1;sy=1;rot=0;dx=0;dy=.03;', {'viewport':[1920,1080], 'feedback_fps':60}), 'forward_content_transport')
    assert a['rms_speed_vp_per_second'] == pytest.approx(.03*30/(1080/1920), abs=1e-7)
    assert b['rms_speed_vp_per_second'] == 2*a['rms_speed_vp_per_second']


@pytest.mark.parametrize('body', ['zoom=0;', 'zoom=bass;', 'sx=0;', 'rot=rand(10);'])
def test_unknown_or_singular_maps_keep_forward_speed_unresolved(body):
    row = contribution(native(body), 'forward_content_transport')
    assert row['speed_interval_vp_per_second'][1] is None
    assert row['unknown_reasons']


def test_known_spatial_sampling_bound_does_not_claim_invertible_content_flow():
    result = evidence(read('fWaveAlpha=0\nper_frame_1=zoomexp=1;warp=0;zoom=1;sx=1;sy=1;rot=0;\nper_pixel_1=dx=.01*x;\n'))
    assert contribution(result, 'backward_sampling_displacement')['rms_speed_vp_per_second_upper_bound'] > 0
    assert contribution(result, 'forward_content_transport')['speed_interval_vp_per_second'][1] is None


def test_disconnected_uniform_composite_cannot_inherit_native_motion():
    result = evidence(read('PSVERSION_COMP=2\nper_frame_1=zoom=2;rot=1;\ncomp_1=`shader_body {ret=.5;}\n'), selected_custom=True)
    assert result['visible_motion_speed_vp_per_second'] == 0
    assert not result['contributions']


def test_geometry_author_units_convert_to_uv_without_extra_ndc_factor():
    result = evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.5+.3*time;y=.5-.4*time;rad=.2;ang=0;sides=4;\n'))
    row = contribution(result, 'geometry_trajectory', 'shape_0')
    assert row['maximum_speed_vp_per_second'] == pytest.approx(.5)
    assert row['centre_velocity_vp_per_second'] == pytest.approx([.3, -.4])


def test_shape_radius_is_half_ndc_in_viewport_units_and_aspect_scales_x():
    result = evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.5;y=.5;rad=.2;ang=3*time;sides=4;\n'), {'viewport':[1920,1080], 'feedback_fps':30})
    row = contribution(result, 'geometry_trajectory', 'shape_0')
    assert row['local_speed_vp_per_second_upper_bound'] == pytest.approx(.3)
    assert row['native_shape_aspect_y'] == pytest.approx(1080/1920)


def test_audio_response_is_partial_not_speed_without_declared_audio_slopes():
    result = evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.5+.1*bass;y=.5;rad=.2;ang=0;sides=4;\n'))
    row = contribution(result, 'geometry_audio_partial', 'shape_0')
    assert row['maximum_response_vp_per_audio_unit'] == pytest.approx(.1)
    assert row['speed_interval_vp_per_second'][1] is None
    assert result['unresolved_contributors']


def test_declared_independent_audio_rates_compose_geometry_speed_without_execution():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2],'mid':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':3,'mid':4}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass;y=.5+.2*mid;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second']==pytest.approx(math.hypot(.3,.8))
    assert row['declared_input_rates_per_second']=={'bass':3,'mid':4}
    assert not any(r['component_id']=='shape_0' for r in result['unresolved_contributors'])
    assert result['uses_equation_execution'] is False


def test_independent_audio_changes_do_not_cancel_for_opposite_coefficients():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2],'mid':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':3,'mid':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=bass-mid;y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second']==pytest.approx(6)


def test_positive_response_rate_product_cannot_underflow_to_stationary():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':5e-324}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass;y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None or row['maximum_speed_vp_per_second']>0


def test_positive_radius_times_angular_rate_cannot_underflow_to_stationary():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':5e-324}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5;y=.5;rad=1e-10;ang=bass;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None or row['maximum_speed_vp_per_second']>0


def test_missing_one_audio_rate_keeps_combined_geometry_unknown():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2],'mid':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass;y=.5+.2*mid;rad=.2;ang=0;sides=4;\n'),context)
    assert not any(r['kind']=='geometry_declared_input_transport' for r in result['contributions'])
    assert any(r['component_id']=='shape_0' for r in result['unresolved_contributors'])


def test_rate_without_amplitude_domain_is_not_complete_geometry_transport():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_maximum_rates_per_second':{'bass':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass;y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None
    assert any('amplitude' in reason for reason in row['unknown_reasons'])


def test_zero_rate_does_not_remove_discontinuous_source_seam():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':0}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=above(bass,1);y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None


def test_finite_audio_domain_can_still_overflow_native_position_conversion():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2e38]},
        'scalar_input_maximum_rates_per_second':{'bass':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=bass;y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None
    assert any('float32' in reason for reason in row['unknown_reasons'])


def test_individually_finite_controls_do_not_prove_finite_perimeter_addition():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,1e38]},
        'scalar_input_maximum_rates_per_second':{'bass':0}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=bass;y=.5;rad=3e38;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None
    assert any('perimeter' in reason for reason in row['unknown_reasons'])


@pytest.mark.parametrize('factor,finite',[('1e308',False),('10',True)])
def test_original_zero_product_arguments_retain_their_domain_obligations(factor,finite):
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass+0*('+factor+'*bass);y=.5;rad=.2;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert (row['maximum_speed_vp_per_second'] is not None)==finite
    if finite:assert row['maximum_speed_vp_per_second']==pytest.approx(.3)
    else:
        assert any('original' in reason for reason in row['unknown_reasons'])
        assert any(r['component_id']=='shape_0' for r in result['unresolved_contributors'])


def test_declared_rate_does_not_remove_native_invalid_geometry_guard():
    context={'viewport':[1000,1000],'feedback_fps':30,
        'scalar_input_domains':{'bass':[0,2]},
        'scalar_input_maximum_rates_per_second':{'bass':3}}
    result=evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.1*bass;y=.5;rad=1e100;ang=0;sides=4;\n'),context)
    row=contribution(result,'geometry_declared_input_transport','shape_0')
    assert row['maximum_speed_vp_per_second'] is None
    assert result['unresolved_contributors']


@pytest.mark.parametrize('rates',[{'bass':-1},{'bass':float('nan')},{'bass':True},{'time':0},[]])
def test_invalid_or_redefined_clock_rate_rejected(rates):
    from source_motion_behaviour import motion_evidence
    with pytest.raises(ValueError):
        motion_evidence(None,{}, {'viewport':[1000,1000],'feedback_fps':30,
            'scalar_input_maximum_rates_per_second':rates})


def test_sympy_correlated_shape_time_derivative_reduces_real_rate_bound():
    import os
    from pathlib import Path
    from source_symbolic import SymbolicSession
    python = os.environ.get('MILK_SYMBOLIC_PYTHON')
    if python is None: pytest.skip('prepared SymPy Python required')
    source = read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.5+.1*sin(time)*sin(time);y=.5;rad=.2;ang=0;sides=4;\n')
    with SymbolicSession(Path(python)):
        row = contribution(evidence(source), 'geometry_trajectory', 'shape_0')
    assert row['maximum_speed_vp_per_second'] <= .100001
    assert row['derivative_reports']['x']['symbolic_refinement']['status'] == 'bounded'


@pytest.mark.parametrize('context', [{'viewport':[0,1080],'feedback_fps':30}, {'viewport':[1920,1080]}, {'viewport':[1920,1080],'feedback_fps':0}])
def test_missing_or_invalid_context_does_not_silently_supply_fps(context):
    assert importlib.util.find_spec('source_motion_behaviour'), 'quantified movement producer missing'
    with pytest.raises(ValueError):
        evidence(read('fWaveAlpha=0\n'), context)


def test_uniform_dynamic_affine_controls_have_joint_transport_bound_without_frames():
    result = native('zoom=1.1+.02*sin(time);sx=1.2+.1*cos(time);sy=-.9;rot=.2*sin(time);cx=.3+.1*sin(time);cy=.6;dx=.03*cos(time);dy=-.02;')
    row = contribution(result, 'forward_content_transport')
    assert row['estimate_kind'] == 'maximum_upper_bound'
    assert row['speed_interval_vp_per_second'][1] is not None
    assert row['rms_speed_vp_per_second_upper_bound'] is not None
    assert row.get('rms_speed_vp_per_second') is None
    assert row['complete_native_sampling_map_proved'] is True


def test_custom_warp_reusing_mesh_uv_cannot_claim_native_map_is_complete():
    result = evidence(read('PSVERSION_WARP=2\nper_frame_1=zoom=1.1;zoomexp=1;warp=0;\nwarp_1=`shader_body {ret=GetPixel(frac(uv*3));}\n'))
    assert contribution(result, 'forward_content_transport')['speed_interval_vp_per_second'][1] is None
    assert contribution(result, 'native_affine_component_transport')['maximum_speed_vp_per_second'] > 0


def test_persistent_geometry_state_is_not_stationary_when_time_partial_zero():
    result = evidence(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=phase=phase+.01;x=.5+phase;y=.5;rad=.2;ang=0;sides=4;\n'))
    assert result['maximum_potential_speed_interval_vp_per_second'][1] is None
    assert any('state' in ' '.join(row['unknown_reasons']) for row in result['unresolved_contributors'])


def test_procedural_spatial_time_pattern_cannot_be_stationary_by_disconnected_feedback():
    result = evidence(shader('shader_body {ret=.5+.5*cos(10*uv.x+time);}'))
    assert result['visible_motion_speed_vp_per_second'] is None
    assert result['maximum_potential_speed_interval_vp_per_second'][1] is None
    assert any(row['kind'] == 'procedural_shader_motion' for row in result['unresolved_contributors'])


def test_uniform_time_colour_has_no_coordinate_motion_contribution():
    result = evidence(shader('shader_body {ret=.5+.5*cos(time);}'), selected_custom=True)
    assert result['visible_motion_speed_vp_per_second'] == 0
    assert not result['contributions']


def test_declared_audio_domains_bound_per_step_map_without_inventing_audio_speed():
    from source_input_scenario import validate_scenario
    scenario = validate_scenario({'schema_version':1,'name':'motion test','audio_band_ranges':{'bass':[0,2]}})
    result = evidence(read('fWaveAlpha=0\nper_frame_1=zoom=1+.01*bass;zoomexp=1;warp=0;sx=1;sy=1;rot=0;dx=0;dy=0;\n'), scenario=scenario)
    row = contribution(result, 'forward_content_transport')
    assert row['maximum_speed_vp_per_second'] > 0
    assert row['input_scenario_sha256'] == scenario['record_sha256']
    assert row['rate_kind'] == 'per_feedback_step'


def test_native_procedural_warp_strict_lipschitz_margin_bounds_retained_branch_transport():
    result = native('zoom=1;sx=1;sy=1;rot=0;dx=0;dy=0;warp=.2;')
    row = contribution(result, 'forward_content_transport')
    assert row['maximum_speed_vp_per_second'] > 0
    proof = row['inverse_stability_proof']
    assert proof['procedural_jacobian_operator_upper_bound'] < proof['affine_minimum_singular_value']
    assert proof['scope'] == 'inverse branches retained within normalized viewport'
    assert row['estimate_kind'] == 'maximum_upper_bound'


def test_large_native_procedural_warp_without_positive_inverse_margin_stays_unknown():
    result = native('zoom=1;sx=1;sy=1;rot=0;dx=0;dy=0;warp=100;')
    assert contribution(result, 'forward_content_transport')['speed_interval_vp_per_second'][1] is None


def test_small_warp_proof_does_not_hide_custom_shader_fold():
    result = evidence(read('PSVERSION_WARP=2\nper_frame_1=zoom=1;zoomexp=1;warp=.01;\nwarp_1=`shader_body {ret=GetPixel(frac(uv*3));}\n'))
    assert contribution(result, 'forward_content_transport')['speed_interval_vp_per_second'][1] is None


def test_bounded_spatial_noninjective_map_has_sampling_relation_without_trajectory():
    result = evidence(read('fWaveAlpha=0\nper_frame_1=zoom=1;zoomexp=1;warp=0;sx=1;sy=1;rot=0;\nper_pixel_1=dx=x;\n'))
    row = contribution(result, 'sampled_content_displacement_relation')
    assert row['maximum_speed_vp_per_second'] >= 30
    assert row['is_trajectory_speed'] is False
    assert row['inverse_uniqueness_required'] is False
    assert contribution(result, 'forward_content_transport')['speed_interval_vp_per_second'][1] is None


def test_native_sampling_relation_does_not_promote_uniform_contents_to_visible_motion():
    result = native('zoom=1;sx=1;sy=1;rot=0;warp=100;')
    row = contribution(result, 'sampled_content_displacement_relation')
    assert row['maximum_speed_vp_per_second'] > 0
    assert row['visible_motion_speed_vp_per_second'] is None
    assert result['visible_motion_speed_vp_per_second'] is None


def test_authored_affine_lookup_feature_speed_uses_inverse_matrix_without_extra_feedback_fps():
    result = evidence(shader('shader_body {ret=GetPixel(2*uv+float2(.1*time,0));}'))
    row = contribution(result, 'affine_lookup_feature_time_partial')
    assert row['maximum_speed_vp_per_second'] == pytest.approx(.05, abs=1e-7)
    assert row['feature_velocity_vp_per_second'] == pytest.approx([-.05,0], abs=1e-7)
    assert row['fixed_texture_content_required'] is True
    assert row['rate_kind'] == 'source_time_partial'


def test_warp_lookup_time_partial_with_unknown_mesh_does_not_claim_viewport_speed():
    result = evidence(shader('shader_body {ret=GetPixel(2*uv+float2(.1*time,0));}', 'warp'))
    rows = [row for row in result['contributions'] if row['kind'] == 'affine_lookup_feature_time_partial']
    assert not rows


def test_unknown_native_composite_selection_cannot_assert_disconnected_zero_motion():
    result = evidence(read('PSVERSION_COMP=2\nper_frame_1=zoom=2;rot=1;\ncomp_1=`shader_body {ret=.5;}\n'))
    assert result['visible_motion_speed_vp_per_second'] is None
    assert result['maximum_potential_speed_interval_vp_per_second'][1] is None
    assert contribution(result, 'native_stage_selection')['component_id'] == 'shader_composite'


def test_declared_context_audio_domain_bounds_shape_time_partial_and_identity():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.5;y=.5;rad=bass;ang=time;sides=4;\n')
    context={'viewport':[1920,1080],'feedback_fps':30,'reference_profile':'domain control','scalar_input_domains':{'bass':[.1,.1]}}
    result=evidence(source,context)
    row=contribution(result,'geometry_trajectory','shape_0')
    assert row['radius_value_range']==pytest.approx([.1,.1])
    assert row['maximum_speed_vp_per_second']==pytest.approx(.05)
    assert result['context']['scalar_input_domains']=={'bass':[.1,.1]}
    assert result['context']['reference_profile']=='domain control'
    changed=evidence(source,{**context,'scalar_input_domains':{'bass':[.2,.2]}})
    assert result['context_sha256']!=changed['context_sha256']
    assert result['record_sha256']!=changed['record_sha256']
    assert contribution(result,'geometry_audio_partial')['speed_interval_vp_per_second'][1] is None


def test_context_domains_bound_uniform_per_feedback_transport_without_scenario():
    context={'viewport':[1000,1000],'feedback_fps':30,'scalar_input_domains':{'bass':[0,2]}}
    result=native('zoom=1+.01*bass;zoomexp=1;warp=0;sx=1;sy=1;rot=0;dx=0;dy=0;',context)
    row=contribution(result,'forward_content_transport')
    assert row['maximum_speed_vp_per_second']>0
    assert row['native_float32_control_domains']['zoom']==pytest.approx([1,1.02],abs=1e-7)
    assert row['rate_kind']=='per_feedback_step'


def test_conflicting_scenario_and_context_domain_is_rejected_consistently():
    from source_input_scenario import validate_scenario
    scenario=validate_scenario({'schema_version':1,'name':'domain conflict','audio_band_ranges':{'bass':[0,2]}})
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=rad=bass;ang=time;sides=4;\n')
    with pytest.raises(ValueError,match='conflicting scenario/context scalar input domain: bass'):
        evidence(source,{'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'bass':[.1,.1]}},scenario=scenario)


def test_compatible_context_and_scenario_domains_merge_without_losing_either():
    from source_input_scenario import validate_scenario
    scenario=validate_scenario({'schema_version':1,'name':'combined domains','audio_band_ranges':{'bass':[.1,.1]}})
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=rad=bass+mid;ang=time;sides=4;\n')
    result=evidence(source,{'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'mid':[.2,.2]}},scenario=scenario)
    assert contribution(result,'geometry_trajectory','shape_0')['radius_value_range']==pytest.approx([.3,.3])
    assert result['effective_scalar_input_domains']['bass']==[.1,.1]
    assert result['effective_scalar_input_domains']['mid']==[.2,.2]
    assert result['input_scenario_sha256']==scenario['record_sha256']
