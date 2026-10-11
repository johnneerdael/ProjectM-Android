"""Scalar palettes and flat-field states come from projected source graphs."""
import pytest

from test_effect_families import read
from test_source_appearance import appearance


def nonlinear(warp=None,comp=None):
    text='PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
    if warp:text+='warp_1=`'+warp+'\n'
    if comp:text+='comp_1=`'+comp+'\n'
    return appearance(read(text))['nonlinear_texture_colour_bounds']


def test_single_scalar_palette_with_black_and_white_anchors():
    result=nonlinear(comp='shader_body {float s=tex2D(sampler_main,uv).x*.5+GetBlur1(uv).y*.5; ret=float3(s,1-s,.5);}')
    palette=result['stages']['composite']['scalar_palette']
    assert palette['status']=='conditional_scalar_palette'
    assert palette['scalar_range']==[pytest.approx(0),pytest.approx(1)]
    assert palette['black_content_scalar']==[pytest.approx(0)]*2
    assert palette['samples'][0]['clamped_rgb']==[pytest.approx(0),pytest.approx(1),pytest.approx(.5)]
    assert palette['samples'][-1]['clamped_rgb']==[pytest.approx(1),pytest.approx(0),pytest.approx(.5)]
    assert palette['other_inputs_change_palette'] is False


def test_independent_channels_are_not_a_scalar_palette():
    palette=nonlinear(comp='shader_body {ret=tex2D(sampler_main,uv).xyz;}')['stages']['composite']['scalar_palette']
    assert palette['status']=='multiple_independent_sample_paths'


@pytest.mark.parametrize('warp,behaviour,expected',[
    ('shader_body {ret=tex2D(sampler_main,uv).xyz*.9+.05;}','settles_on_colour',.5),
    ('shader_body {ret=tex2D(sampler_main,uv).xyz+.01;}','saturates_to_white',1.),
    ('shader_body {ret=tex2D(sampler_main,uv).xyz*.5;}','decays_to_black',0.),
])
def test_flat_field_fixed_points(warp,behaviour,expected):
    flat=nonlinear(warp=warp)['flat_field']
    assert flat['status']=='conditional_flat_field_state'
    assert flat['flat_region_behaviour']==behaviour
    # RGBA8 rounding stalls within |(1-gain)k - bias| < 1/2 of the real fixed point.
    assert flat['state_rgb'][0]==pytest.approx(expected,abs=6/255)


def test_flat_field_with_non_feedback_texture_abstains():
    flat=nonlinear(warp='shader_body {ret=tex2D(sampler_noise_lq,uv).xyz;}')['flat_field']
    assert flat['status']=='unknown'
    assert flat['unknown_reasons']
