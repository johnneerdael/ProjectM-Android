"""Affine polar colour labels are functions of radius: concentric ring evidence."""
from copy import deepcopy
from fractions import Fraction
import json

import pytest

from test_source_parametric_wave import control, SPIRAL
from test_source_curve_feedback_relation import inputs


def exact(value):
    return Fraction(int(value['numerator']),int(value['denominator']))


def field(recipe,projection=None,context=None):
    from source_radial_colour_field import radial_colour_field
    result=radial_colour_field(recipe,projection,context)
    json.dumps(result,allow_nan=False)
    return result


def test_zylot_colour_is_radius_locked_with_static_concentric_rings():
    recipe,projection,_,_=inputs()
    result=field(recipe,projection)
    assert result['status']=='conditional_radius_locked_colour'
    assert result['continuous_curve_colour_angle_independent'] is True
    red,green,blue=(result['channels'][name] for name in 'rgb')
    assert exact(red['radial_gradient_per_source_unit_exact'])==50
    assert exact(red['fixed_radius_rate_exact'])==0
    assert exact(red['ring_drift_source_units_per_second_exact'])==0
    assert red['radial_modulo_period_pixels']==pytest.approx(480*.02*1.003921627998352,rel=1e-9)
    assert green['radial_modulo_period_pixels']==pytest.approx(480/30*1.003921627998352,rel=1e-9)
    assert blue['radial_modulo_period_pixels']==pytest.approx(480/10*1.003921627998352,rel=1e-9)
    assert result['concentric_ring_pattern']=='static_at_fixed_radius'
    assert result['displayed_colour_angle_independent'] is None
    assert result['visible_ring_count'] is None


def test_time_terms_give_ring_drift_and_fixed_radius_rate():
    recipe,_=control('p=sample*60+time;d=.1+.4*sample+.05*time;x=.5+d*sin(p);y=.5+d*cos(p);r=2*sample+time;g=.3;b=.3;')
    assert field(recipe)['status']=='unknown'
    result=field(recipe,context={'source_time_domain':[0,10]})
    assert result['radius_branch']=='strictly_positive'
    red=result['channels']['r']
    # gradient 2/.4=5; fixed-radius rate 1-2*.05/.4=.75; ring drift .05-1*.4/2=-.15
    assert exact(red['radial_gradient_per_source_unit_exact'])==pytest.approx(5,rel=1e-6)
    assert float(exact(red['fixed_radius_rate_exact']))==pytest.approx(.75,rel=1e-6)
    assert float(exact(red['ring_drift_source_units_per_second_exact']))==pytest.approx(-.15,rel=1e-6)
    assert result['concentric_ring_pattern']=='drifting_or_cycling'
    assert result['channels']['g']['status']=='uniform_channel'


def test_radius_sign_change_breaks_unique_radius_branch():
    recipe,_=control('p=sample*60;d=sample-.5;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    result=field(recipe)
    assert result['status']=='unknown'
    assert result['continuous_curve_colour_angle_independent'] is None


def test_constant_radius_circle_has_no_radius_function():
    recipe,_=control('p=sample*7;x=.5+.2*sin(p);y=.5+.2*cos(p);r=sample;')
    result=field(recipe)
    assert result['status']=='unknown'
    assert any('radius' in reason for reason in result['unknown_reasons'])


@pytest.mark.parametrize('colour',['r=sin(sample);g=.2;b=.2;','r=sample;g=value1;b=.2;'])
def test_unsupported_channel_does_not_erase_supported_ones(colour):
    recipe,_=control(SPIRAL+colour)
    result=field(recipe)
    assert result['channels']['r']['status']!='unknown' or result['status']=='unknown'
    assert result['concentric_ring_pattern'] is None or result['status']!='unknown'


def test_projection_mismatch_withholds_pixels_only():
    recipe,projection,_,_=inputs()
    projection=deepcopy(projection);projection['source_curve_provenance']['preset_sha256']='f'*64
    result=field(recipe,projection)
    assert result['status']=='conditional_radius_locked_colour'
    assert result['channels']['r']['radial_modulo_period_pixels'] is None
    assert result['projection_unknown_reasons']


def orbit_persistence():
    import numpy as np
    from source_feedback_persistence import unorm8_decay_persistence
    return unorm8_decay_persistence({'policy':'source-warp-colour-transfer-v1','source_model':'fixed_main_decay',
        'uniform_diagonal_gain':float(np.float32(.92)),'constant_offset_rgb':[0,0,0],
        'coordinate_feedback_dependency':False},{'output_storage':'normalized-unorm','feedback_fps':30.0})


def test_zylot_sweep_front_revisits_each_radius_at_phase_rate_cadence():
    recipe,projection,_,_=inputs()
    from source_radial_colour_field import radial_colour_field
    result=radial_colour_field(recipe,projection,{'feedback_fps':30.0},persistence=orbit_persistence())
    sweep=result['sweep_front']
    assert sweep['status']=='conditional_rotating_refresh_front'
    assert exact(sweep['fixed_radius_angular_rate_exact'])==10
    assert sweep['revisit_cadence_hz']==pytest.approx(10/(2*3.141592653589793))
    assert sweep['revisit_frames_interval']==[18,19]
    orbit=orbit_persistence()['level_orbit_from_full']
    assert sweep['stored_level_from_full_before_next_crossing_interval']==[orbit[19],orbit[18]]
    assert sweep['whole_screen_flash'] is False
    assert sweep['visible_flash_frequency_hz'] is None


def test_zero_fixed_radius_rate_has_no_sweep():
    from source_radial_colour_field import radial_colour_field
    # Phi'_R = Pt - Ps*Rt/Rs = 30 - 60*.2/.4 = 0.
    recipe,_=control('p=sample*60+30*time;d=.1+.4*sample+.2*time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    result=radial_colour_field(recipe,None,{'source_time_domain':[0,5]})
    assert result['sweep_front']['status']=='stationary_curve_at_fixed_radius'
    assert result['sweep_front']['revisit_cadence_hz'] is None


def test_sweep_without_persistence_keeps_cadence_only():
    recipe,projection,_,_=inputs()
    from source_radial_colour_field import radial_colour_field
    sweep=radial_colour_field(recipe,projection)['sweep_front']
    assert sweep['revisit_cadence_hz'] is not None
    assert sweep['revisit_frames_interval'] is None
    assert sweep['stored_level_from_full_before_next_crossing_interval'] is None


def test_negative_raw_labels_are_flagged_for_signed_modulo():
    recipe,_=control(SPIRAL+'r=sample-.5;g=sample;b=.2;')
    result=field(recipe)
    assert result['channels']['r']['negative_raw_label_possible'] is True
    assert result['channels']['g']['negative_raw_label_possible'] is False
    assert any('signed fmod' in condition for condition in result['conditions'])


def test_static_radius_with_time_varying_label_uses_declared_domain():
    recipe,_=control('p=sample*60;d=.1+.4*sample;x=.5+d*sin(p);y=.5+d*cos(p);r=2*sample+time;g=.3;b=.3;')
    result=field(recipe,context={'source_time_domain':[0,10]})
    assert result['status']=='conditional_radius_locked_colour'
    assert result['channels']['r']['raw_label_range']==[0.0,12.0]


def test_drifting_radius_coverage_limits_revisits():
    from source_radial_colour_field import radial_colour_field
    # Phi'_R = 60.5 - 6*.1/.01 = .5 rad/s (period ~12.6 s); coverage |Rs/Rt| = .1 s.
    recipe,_=control('p=sample*6+60.5*time;d=.1+.01*sample+.1*time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    sweep=radial_colour_field(recipe,None,{'source_time_domain':[0,1]})['sweep_front']
    assert sweep['radius_coverage_seconds']==pytest.approx(.1)
    assert sweep['revisit_within_radius_coverage'] is False


def test_more_than_one_revisit_per_frame_withholds_levels():
    from source_radial_colour_field import radial_colour_field
    recipe,_=control('p=sample*60+400*time;d=.1+.4*sample;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    sweep=radial_colour_field(recipe,None,{'feedback_fps':30.0},persistence=orbit_persistence())['sweep_front']
    assert sweep['multiple_revisits_per_frame'] is True
    assert sweep['stored_level_from_full_before_next_crossing_interval'] is None
