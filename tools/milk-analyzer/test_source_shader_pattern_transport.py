"""Whole generated-pattern translation controls; no images or source execution."""
import hashlib
import json
import math

import pytest
from test_effect_families import read


def analysis_for(body, stage='composite', selected=True, controls=''):
    from effect_families import _Analysis
    prefix = 'comp_' if stage == 'composite' else 'warp_'
    version = 'COMP' if stage == 'composite' else 'WARP'
    source = read(f'PSVERSION_{version}=2\nfWaveAlpha=0\n{controls}\n'
                  f'{prefix}1=`shader_body {{{body}}}\n')
    code = source['sections'][prefix]['source']
    compatibility = {stage: {'source_sha256': hashlib.sha256(code.encode()).hexdigest(),
        'request': {'code': code, 'stage': stage, 'profile': 'gles300'},
        'translation': {'engine_archive_sha256': source['parser_inputs']['engine_archive_sha256']},
        'offline_accepted': True}} if selected else None
    analysis = _Analysis(source, 'gles300', compatibility)
    analysis.main_equations()
    analysis.primitives()
    analysis.shader(stage, prefix)
    return analysis


def transport(body, stage='composite', selected=True, controls='', context=None):
    from source_shader_pattern_transport import rigid_shader_pattern_transport
    return rigid_shader_pattern_transport(analysis_for(body, stage, selected, controls), stage, context)


def test_single_phase_has_inverse_velocity_and_no_feedback_fps_multiplier():
    result = transport('ret=.5+.5*cos(10*uv.x+time);')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-.1, 0])
    assert result['maximum_pattern_speed_vp_per_second'] == pytest.approx(.1)
    assert result['constraint_rank'] == 1
    assert result['velocity_unique'] is False
    assert result['visible_motion_speed_vp_per_second'] is None
    assert result['uses_shader_execution'] is False
    json.dumps(result, allow_nan=False)


def test_independent_phases_share_one_unique_velocity():
    result = transport('ret=float3(sin(2*uv.x+4*time),cos(3*uv.y-3*time),'
                       'abs(sin(2*uv.x+3*uv.y+time)));')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-2, 1])
    assert result['constraint_rank'] == 2
    assert result['velocity_unique'] is True
    assert result['maximum_pattern_speed_vp_per_second'] == pytest.approx(math.sqrt(5))


@pytest.mark.parametrize('body', [
    'ret=sin(uv.x+time)+sin(2*uv.x+time);',
    'ret=float3(sin(uv.x+time),cos(time),0);',
    'ret=sin(uv.x+time)*sin(time);',
    'ret=sin(uv.x+time)+uv.x;',
    'ret=GetPixel(uv)+sin(uv.x+time);',
    'ret=sin(uv.x+bass*time);',
    'ret=sin(uv.x+int(time));',
    'ret=sin(uv.x+time)+1/0;',
    'ret=sin(uv.x+time);clip(uv.y-.5);',
])
def test_conflicting_modulated_sampled_discrete_or_invalid_pattern_stays_unknown(body):
    result = transport(body)
    assert result['status'] == 'unresolved'
    assert result['maximum_pattern_speed_vp_per_second'] is None
    assert result['unknown_reasons']


def test_unselected_custom_cannot_supply_motion_proof():
    assert transport('ret=sin(uv.x+time);', selected=False)['status'] == 'unresolved'


def test_nonlinear_folds_preserve_the_same_translation():
    result = transport('ret=saturate(abs(sin(3*uv.x+6*time)))*cos(6*uv.x+12*time);')
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-2, 0])


def test_composite_native_original_and_shader_uv_are_aliased():
    result = transport('ret=sin(uv.x+time)+cos(uv_orig.x+time);')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-1, 0])
    assert result['coordinate_basis'] == 'normalized_viewport_uv'


def test_warp_original_uv_bypasses_dynamic_native_mesh():
    result = transport('ret=sin(uv_orig.x+time);', stage='warp',
                       controls='per_frame_1=zoom=bass;warp=1;')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-1, 0])


def test_warp_shader_uv_requires_fixed_native_coordinate_recipe():
    result = transport('ret=sin(uv.x+time);', stage='warp',
                       controls='per_frame_1=zoom=bass;warp=0;')
    assert result['status'] == 'unresolved'


def test_fixed_native_mesh_pulls_back_shader_pattern_velocity():
    result = transport('ret=sin(uv.x+time);', stage='warp',
                       controls='per_frame_1=zoom=2;zoomexp=1;warp=0;sx=1;sy=1;rot=0;',
                       context={'viewport':[1920,1080],
                                'scalar_input_domains':{'_uv.x':[-1,2], '_uv.y':[-1,2]}})
    assert result['status'] == 'conditional_rigid_translation'
    assert result['signed_velocity_vp_per_second'] == pytest.approx([-2, 0])
    assert result['native_coordinate_recipe']['model_kind'] == 'uniform_affine'


def test_no_spatial_or_temporal_pattern_is_not_positive_motion():
    assert transport('ret=sin(time);')['status'] == 'unresolved'
    static = transport('ret=sin(uv.x);')
    assert static['maximum_pattern_speed_vp_per_second'] == 0


def test_exact_original_coefficients_preserve_cancelled_binary64_increment():
    result = transport('ret=sin((1e20*uv.x+uv.x)-1e20*uv.x+time);')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['exact_signed_velocity_vp_per_second'] == ['-1', '0']


def test_near_inconsistent_phases_cannot_use_rounded_rank_or_tolerance():
    result = transport('ret=sin((1e20*uv.x+uv.x)+1e20*time)+sin(1e20*uv.x+1e20*time);')
    assert result['status'] == 'unresolved'
    assert 'consistent' in result['unknown_reasons'][0]


def test_native_hlsl_sqrt_abs_policy_is_preserved():
    result = transport('ret=sin(uv.x+time)+sqrt(-1);')
    assert result['status'] == 'conditional_rigid_translation'


def test_warp_shader_uv_does_not_invent_native_coordinate_bounds():
    result = transport('ret=sin(uv.x+time);', stage='warp',
                       controls='per_frame_1=zoom=2;zoomexp=1;warp=0;sx=1;sy=1;rot=0;')
    assert result['status'] == 'unresolved'
    assert any('coordinate domain' in r for r in result['unknown_reasons'])


def test_unreachable_effects_cannot_be_hidden_by_rgb_lane_projection():
    result = transport('float vals[1]={1};vals[int(time)]=1;ret=sin(uv.x+time);')
    assert result['status'] == 'unresolved'


def test_domain_of_original_intermediate_is_checked_before_bounded_trig():
    result = transport('ret=sin(1e38*(uv.x+10*time));')
    assert result['status'] == 'unresolved'
    assert 'intermediate' in result['unknown_reasons'][0]


def test_typed_dot_phase_reuses_vector_lane_algebra():
    result = transport('ret=sin(dot(uv,float2(2,3))+time);')
    assert result['status'] == 'conditional_rigid_translation'
    assert result['exact_signed_velocity_vp_per_second'] == ['-2/13', '-3/13']


def test_nonlinear_spatial_time_product_cannot_supply_rigid_motion():
    result = transport('ret=sin(uv.x*time);')
    assert result['status'] == 'unresolved'


def test_outer_spatial_switch_support_must_translate_with_the_pattern():
    result = transport('ret=uv.x>.5 ? sin(uv.x+time) : 0;')
    assert result['status'] == 'unresolved'


def partials(body):
    from source_shader_pattern_transport import generated_shader_pattern_transport
    return generated_shader_pattern_transport(analysis_for(body),'composite')


def test_live_generated_partial_survives_sampled_colour_parent_without_completing_stage():
    result = partials('ret=GetPixel(uv)*(.5+.5*cos(10*uv.x+time));')
    assert result['full_pattern'] is None
    assert result['full_pattern_report']['status'] == 'unresolved'
    assert len(result['partial_patterns']) == 1
    partial = result['partial_patterns'][0]
    assert partial['signed_velocity_vp_per_second'] == pytest.approx([-.1,0])
    assert partial['source_graph_path'].startswith('output/')
    assert partial['role'] == 'live_generated_colour_subfield'
    assert partial['included_in_total_motion'] is False
    assert partial['parent_colour_context_held_fixed'] is True


@pytest.mark.parametrize('body',[
    'ret=GetPixel(float2(sin(uv.x+time),uv.y));',
    'ret=GetPixel(uv)+0*sin(uv.x+time);',
    'ret=GetPixel(uv)*saturate(2+sin(uv.x+time));',
    'ret=GetPixel(uv);float unused=sin(uv.x+time);',
])
def test_dead_clipped_unused_or_sampling_coordinate_pattern_is_not_live_colour_partial(body):
    assert partials(body)['partial_patterns'] == []


def test_conflicting_partial_patterns_never_get_one_stage_velocity():
    result = partials('ret=GetPixel(uv)+sin(uv.x+time)+sin(2*uv.x+time);')
    assert result['full_pattern'] is None
    assert len(result['partial_patterns']) == 2
    assert all(r['included_in_total_motion'] is False for r in result['partial_patterns'])


def test_nested_valid_generator_uses_maximal_subfield_and_preserves_parent_obligations():
    result = partials('ret=GetPixel(uv)*abs(sin(uv.x+time));')
    assert len(result['partial_patterns']) == 1
    assert result['partial_patterns'][0]['generator_op'] == 'abs'
    assert result['partial_patterns'][0]['parent_conditions']

