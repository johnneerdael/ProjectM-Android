"""Pinned source34 material controls; no RNG, frames, audio or rendering."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import pytest


def records(body, *, configuration='', initialization='', main='', fps=30):
    import effect_families as ef
    from source_fill_envelopes import shape_fill_envelope
    from source_geometry import shape_geometry
    from source_material import shape_material
    from source_material_temporal import shape_material_temporal
    from source_stochastic_brightness import stochastic_material_brightness

    raw=('MILKDROP_PRESET_VERSION=201\n[preset00]\nPSVERSION_COMP=0\nfWaveAlpha=0\n'
         'shapecode_0_enabled=1\n'+configuration+initialization+main+
         'shape_0_per_frame1='+body+'\n').encode()
    reader=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'random-colour.milk'
        path.write_bytes(raw)
        source=json.loads(subprocess.check_output([str(reader),str(path)]))
    source['preset_sha256']=hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    token=ef._CACHE.set({})
    try:
        analysis=ef._Analysis(source,'gles300',None)
        analysis.input_scenario=None
        analysis.main_equations()
        analysis.primitives()
        controls=analysis.component_controls['shape_0']
        from scene_equations import _scalar
        geometry=shape_geometry(controls,_scalar(analysis.values,'shapecode_0_num_inst',1,'int'))
        material=shape_material(controls,'')
        temporal=shape_material_temporal(controls)
        element={'id':'shape_0','geometry':geometry,'material':material,'material_temporal':temporal,
                 'fill_envelope':shape_fill_envelope(controls,geometry,material,temporal)}
        result=stochastic_material_brightness(analysis,element,{'feedback_fps':fps})
    finally:
        ef._CACHE.reset(token)
    json.dumps(result,allow_nan=False)
    return {record['part']:record for record in result}


RGB='r=int(rand(100))/100;g=int(rand(100))/100;b=int(rand(100))/100;r2=r;g2=g;b2=b;'
GRAY='r=rand(100)/100;g=r;b=r;r2=r;g2=r;b2=r;'


@pytest.mark.parametrize('additive', [0,1])
def test_independent_random_channels_have_alpha_weighted_local_ceiling(additive):
    result=records(RGB+'a=.5;a2=.5;additive='+str(additive)+';')['fill']
    assert result['maximum_blended_rgb_difference']==pytest.approx([.5]*3,abs=1e-6)
    assert result['maximum_local_rgb_infinity_norm_difference']==max(result['maximum_blended_rgb_difference'])
    assert result['groups']['centre']['random_recipe']['shared_random_draw'] is False
    assert len(result['groups']['centre']['random_recipe']['distinct_source_sites'])==3
    assert result['maximum_frame_refresh_opportunities_per_second']==30
    assert result['event_frequency_hz'] is None
    assert result['maximum_continuous_rgb_rate_per_second'] is None
    assert result['visible_flash_strength'] is None
    assert result['native_numeric_certified'] is False


def test_copied_draw_keeps_source_identity_and_gray_correlation():
    result=records(GRAY+'a=1;a2=1;')['fill']
    recipe=result['groups']['centre']['random_recipe']
    assert recipe['shared_random_draw'] is True
    assert len(recipe['distinct_source_sites'])==1
    assert result['groups']['perimeter']['random_recipe']['distinct_source_sites']==recipe['distinct_source_sites']
    assert result['rng_distribution_assumed'] is False
    assert result['independent_draws_assumed'] is False


def test_transparent_center_random_colour_still_crosses_into_edge_alpha():
    result=records('r=rand(100)/100;g=r;b=r;r2=.2;g2=.2;b2=.2;a=0;a2=.5;')['fill']
    assert result['maximum_blended_rgb_difference']==pytest.approx([.125]*3,abs=1e-6)
    assert result['groups']['perimeter']['status']=='native_endpoint_envelope'


@pytest.mark.parametrize('border,known', [('border_r=1;border_g=0;border_b=0;',True),
                                        ('border_r=bass;border_g=0;border_b=0;',False)])
def test_live_constant_or_unknown_border_is_preserved(border,known):
    result=records(RGB+'a=1;a2=1;border_a=1;'+border)
    assert result['fill']['maximum_local_rgb_infinity_norm_difference'] is not None
    record=result['border']
    assert record['groups']['border']['random_recipe'] is None
    if known:
        assert record['maximum_blended_rgb_difference']==[0,0,0]
        assert record['maximum_rng_induced_frame_rgb_difference']==[0,0,0]
    else:
        assert record['maximum_blended_rgb_difference'][0] is None
        assert record['maximum_local_rgb_infinity_norm_difference'] is None
        assert record['unknown_reasons']


def test_unknown_live_perimeter_keeps_fill_unknown():
    result=records('r=rand(100)/100;g=r;b=r;r2=bass;g2=0;b2=0;a=1;a2=1;')['fill']
    assert result['groups']['centre']['random_recipe'] is not None
    assert result['groups']['perimeter']['status']=='unresolved'
    assert result['maximum_local_rgb_infinity_norm_difference'] is None


@pytest.mark.parametrize('alpha', ['a=bass;a2=a;', 'a=rand(100)/100;a2=a;'])
def test_unknown_alpha_never_acquires_a_random_rgb_jump_ceiling(alpha):
    result=records(RGB+alpha)['fill']
    assert result['maximum_blended_rgb_difference']==[None]*3
    assert result['maximum_rng_induced_frame_rgb_difference']==[None]*3


def test_zero_alpha_can_zero_finite_random_partial_but_invalid_rgb_is_not_erased():
    finite=records(RGB+'a=0;a2=0;border_a=1;')['fill']
    assert finite['maximum_blended_rgb_difference']==[0,0,0]
    invalid=records('r=rand(100)/100;g=r;b=r;r2=1e100;g2=0;b2=0;a=0;a2=0;border_a=1;')['fill']
    assert invalid['known_invalid_native_domain'] is True
    assert invalid['maximum_blended_rgb_difference'][0] is None
    assert invalid['maximum_local_rgb_infinity_norm_difference'] is None


@pytest.mark.parametrize('expression', ['sin(rand(100))', 'rand(100)/-100', 'rand(100)'])
def test_unsupported_random_expressions_remain_unknown(expression):
    result=records('r='+expression+';g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;')['fill']
    assert result['groups']['centre']['random_recipe'] is None
    assert result['maximum_blended_rgb_difference']==[None]*3
    assert result['maximum_frame_refresh_opportunities_per_second'] is None


def test_init_copied_random_values_have_zero_rng_frame_partial_only():
    result=records('r=shade/100;g=r;b=r;r2=r;g2=r;b2=r;a=.5+.1*sin(time);a2=a;',
                   initialization='shape_0_init1=shade=rand(100);\n')['fill']
    assert result['refresh_scopes']==['preset_initialization']
    assert result['maximum_frame_refresh_opportunities_per_second']==0
    assert result['maximum_rng_induced_frame_rgb_difference']==[0,0,0]
    assert result['maximum_local_rgb_infinity_norm_difference']>0
    assert result['maximum_continuous_rgb_rate_per_second'] is None
    assert result['other_material_inputs_temporally_fixed_proved'] is False


def test_main_frame_draws_and_shape_instances_have_same_frame_opportunity_upper():
    main=records('r=q1;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;',
                 main='per_frame_1=q1=rand(100)/100;\n',configuration='shapecode_0_num_inst=16\n')['fill']
    shape=records(GRAY+'a=1;a2=1;',configuration='shapecode_0_num_inst=16\n')['fill']
    assert main['refresh_scopes']==['main_frame_invocation']
    assert shape['refresh_scopes']==['shape_instance_invocation']
    assert main['maximum_frame_refresh_opportunities_per_second']==shape['maximum_frame_refresh_opportunities_per_second']==30
    assert main['configured_instances']==shape['configured_instances']==16
    assert main['event_frequency_hz'] is shape['event_frequency_hz'] is None


@pytest.mark.parametrize('fps', [None,0,-1,float('inf'),True])
def test_missing_or_invalid_fps_does_not_invent_refresh_opportunities(fps):
    result=records(GRAY+'a=1;a2=1;',fps=fps)['fill']
    assert result['maximum_frame_refresh_opportunities_per_second'] is None


def test_textured_fill_has_only_separate_fixed_unit_texture_partial():
    result=records(RGB+'a=.5;a2=.5;textured=1;')['fill']
    assert result['maximum_blended_rgb_difference']==[None]*3
    assert result['maximum_local_rgb_infinity_norm_difference'] is None
    partial=result['fixed_unit_texture_partial']
    assert partial['maximum_blended_rgb_difference']==pytest.approx([.5]*3,abs=1e-6)
    assert partial['sample_rgba_domain']==[0,1]
    assert result['unknown_reasons']


def test_small_random_endpoints_are_outward_enclosed():
    result=records('r=rand(10)/100;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;')['fill']
    recipe=result['groups']['centre']['random_recipe']
    assert result['groups']['centre']['native_rgb_component_envelopes'][0][1]>=recipe['encoded_rgb_component_intervals'][0][1]
    assert result['maximum_local_rgb_infinity_norm_difference']>=.1


def test_static_shapes_do_not_gain_stochastic_evidence():
    assert records('r=1;g=0;b=0;r2=r;g2=g;b2=b;a=1;a2=1;')=={}


def test_native_zero_denominator_lowering_does_not_fabricate_random_activity():
    assert records('r=rand(100)/0;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;')=={}


def test_two_state_bound_covers_random_colour_and_nonrandom_alpha_change():
    result=records(GRAY+'a=.5+.1*sin(time);a2=.2+.1*sin(time);')['fill']
    ceiling=result['maximum_local_rgb_infinity_norm_difference']
    groups=[result['groups'][name] for name in ('centre','perimeter')]
    for weight in (0,.2,.5,.9,1):
        for destination in (0,.5,1):
            # Algebraic endpoint witnesses; no source program or time sequence
            # is executed and simultaneous attainability is not assumed.
            low_alpha=weight*groups[0]['native_alpha_envelope'][0]+(1-weight)*groups[1]['native_alpha_envelope'][0]
            high_alpha=weight*groups[0]['native_alpha_envelope'][1]+(1-weight)*groups[1]['native_alpha_envelope'][1]
            low_colour=weight*groups[0]['native_rgb_component_envelopes'][0][0]+(1-weight)*groups[1]['native_rgb_component_envelopes'][0][0]
            high_colour=weight*groups[0]['native_rgb_component_envelopes'][0][1]+(1-weight)*groups[1]['native_rgb_component_envelopes'][0][1]
            before=low_alpha*low_colour+(1-low_alpha)*destination
            after=high_alpha*high_colour+(1-high_alpha)*destination
            assert abs(after-before)<=ceiling
