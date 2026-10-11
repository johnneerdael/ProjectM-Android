"""Conditional source colour envelopes, never a complete feedback certificate."""
import math

import numpy as np
import pytest

from test_effect_families import read,shader
from test_source_appearance import appearance


def bounds(source):
    feedback=appearance(source)['feedback_transfer']
    assert 'colour_bounds' in feedback,'source colour envelopes are missing'
    return feedback['colour_bounds']


def test_fixed_decay_has_conditional_unit_interval_envelope():
    b=bounds(read('fDecay=.9\nfWaveAlpha=0\n'))
    assert np.array(b['raw_rgb_bounds_if_samples_unit_interval'])==pytest.approx(np.array([[0,.9]]*3),abs=1e-7)
    assert b['maximum_colour_difference_gain']==pytest.approx(.9,abs=1e-7)
    assert b['sufficient_contraction_bound'] is True
    assert b['actual_feedback_stability'] is None


def test_two_samples_have_general_colour_perturbation_decay_bound():
    b=bounds(shader('shader_body{ret=GetPixel(uv)*.4+GetPixel(uv*.5)*.4;}',stage='warp'))
    assert b['maximum_colour_difference_gain']==pytest.approx(.8,abs=1e-7)
    assert b['ideal_colour_perturbation_half_life_upper_bound_warp_evaluations']==pytest.approx(math.log(.5)/math.log(.8),rel=1e-6)
    assert b['sufficient_contraction_bound'] is True


def test_signed_samples_keep_independent_bounds_instead_of_net_gain():
    b=bounds(shader('shader_body{ret=.1+GetPixel(uv)*.6-GetPixel(uv*.5)*.2;}',stage='warp'))
    assert np.array(b['raw_rgb_bounds_if_samples_unit_interval'])==pytest.approx(np.array([[-.1,.7]]*3),abs=2e-7)
    assert b['maximum_colour_difference_gain']==pytest.approx(.8,abs=2e-7)


def test_large_gain_has_no_contraction_or_instability_certificate():
    b=bounds(shader('shader_body{ret=GetPixel(uv)*1.2;}',stage='warp'))
    assert b['maximum_colour_difference_gain']==pytest.approx(1.2,abs=2e-7)
    assert b['sufficient_contraction_bound'] is False
    assert b['ideal_colour_perturbation_half_life_upper_bound_warp_evaluations'] is None
    assert b['actual_feedback_stability'] is None


def test_negative_gain_bounds_are_not_positive_palette_values():
    b=bounds(shader('shader_body{ret=GetPixel(uv)*-.8;}',stage='warp'))
    assert np.array(b['raw_rgb_bounds_if_samples_unit_interval'])==pytest.approx(np.array([[-.8,0]]*3),abs=1e-7)
    assert b['sufficient_contraction_bound'] is True


def test_image_driven_coordinates_keep_whole_response_unknown():
    b=bounds(shader('shader_body{ret=GetPixel(uv+GetPixel(uv).rg*.1)*.5;}',stage='warp'))
    assert b['raw_rgb_bounds_if_samples_unit_interval'] is not None
    assert b['maximum_colour_difference_gain']==pytest.approx(.5)
    assert b['sufficient_contraction_bound'] is None
    assert b['ideal_colour_perturbation_half_life_upper_bound_warp_evaluations'] is None


def test_nonlinear_colour_does_not_receive_linear_bounds():
    b=bounds(shader('shader_body{ret=GetPixel(uv)*GetPixel(uv);}',stage='warp'))
    assert b['raw_rgb_bounds_if_samples_unit_interval'] is None
    assert b['maximum_colour_difference_gain'] is None


def test_nonnegative_channel_mix_keeps_each_rgb_row_separate():
    b=bounds(shader('shader_body{ret=GetPixel(uv).bgr*float3(.2,.4,.8)+float3(.1,.2,.3);}',stage='warp'))
    assert np.array(b['raw_rgb_bounds_if_samples_unit_interval'])==pytest.approx(np.array([[.1,.3],[.2,.6],[.3,1.1]]),abs=2e-7)
    assert b['maximum_colour_difference_gain']==pytest.approx(.8,abs=1e-7)


def test_constant_colour_has_zero_perturbation_gain_and_no_fake_half_life():
    b=bounds(shader('shader_body{ret=float3(.1,.2,.3);}',stage='warp'))
    assert b['maximum_colour_difference_gain']==0
    assert b['sufficient_contraction_bound'] is True
    assert b['ideal_colour_perturbation_half_life_upper_bound_warp_evaluations'] is None


def test_difference_bound_controls_independent_sample_perturbations():
    b=bounds(shader('shader_body{ret=GetPixel(uv).bgr*.4-GetPixel(uv*.5).rgb*.3;}',stage='warp'))
    # Perturb distinct sites with opposite signs, yielding the sum of absolute
    # gains. The aggregate matrix alone would wrongly suggest a small bound.
    delta=.01;actual=.4*delta- .3*(-delta)
    assert actual<=b['maximum_colour_difference_gain']*delta+1e-9
    assert b['maximum_colour_difference_gain']==pytest.approx(.7,abs=1e-7)


def test_image_free_spatial_injection_keeps_content_gain_without_full_bounds():
    feedback=appearance(shader('shader_body{ret=GetPixel(uv)*.9+.1/length(uv-.5);}',stage='warp'))['feedback_transfer']
    assert feedback['source_model']=='affine_previous_main_samples'
    assert feedback['uniform_content_gain']==pytest.approx(.9,abs=1e-7)
    assert feedback['image_independent_injection']['present'] is True
    assert feedback['constant_offset_rgb'] is None  # the injected field is not a constant offset
    assert all(lane is not None for lane in feedback['image_independent_injection']['lane_expressions_rgb'])


def test_blur_sites_join_the_previous_image_transfer():
    feedback=appearance(shader('shader_body{ret=GetPixel(uv)*.99-GetBlur2(uv)*.02;}',stage='warp'))['feedback_transfer']
    assert feedback['source_model']=='affine_previous_image_samples'
    assert feedback['uniform_content_gain']==pytest.approx(.97,abs=1e-6)
    assert sorted(c['texture'] for c in feedback['sample_contributions'])==['blur2','main']
    assert feedback['matrix_rgb'] is None and feedback['unknown_reasons']  # no strict certificate from blur sites
