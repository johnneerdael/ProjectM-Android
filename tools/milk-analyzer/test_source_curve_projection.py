"""Declared projection and smoothing bounds; no source/frame evaluation."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

import pytest

from test_source_parametric_wave import control,source_record,SPIRAL


def projected(recipe,context=None):
    from source_curve_projection import curve_projection
    result=curve_projection(recipe,context)
    json.dumps(result,allow_nan=False)
    return result


@pytest.mark.parametrize('viewport', [[1080,1080],[1920,1080],[1080,1920]])
def test_radius_projects_to_long_panel_dimension_in_pixel_basis(viewport):
    recipe,_=control(SPIRAL)
    result=projected(recipe,{'viewport':viewport,'wave_use_dots':True})
    assert result['nominal_radius_pixels_upper_bound']==max(viewport)*.5
    assert result['maximum_nominal_fixed_sample_point_speed_pixels_per_second']>=max(viewport)*5
    assert result['maximum_nominal_interior_locus_normal_speed_pixels_per_second']>=max(viewport)*.05
    assert result['native_numeric_certified'] is False
    assert result['raster_coverage_fraction'] is None


def test_actual_zylot_has_potential_vertical_clipping_and_separate_smoothing_envelope():
    path=Path(__file__).resolve().parents[2]/'core/src/main/assets/presets/Zylot - Spiral.milk'
    recipe,_=source_record(path.read_bytes())
    result=projected(recipe)
    assert result['viewport']==[1920,1080]
    assert result['viewport_was_defaulted'] is True
    assert result['unsmoothed_bbox_screen_fraction'][1][0]<0
    assert result['unsmoothed_bbox_screen_fraction'][1][1]>1
    assert result['possible_coordinate_clipping'] is True
    assert result['prepared_centerline_bbox_screen_fraction'][1][0]<result['unsmoothed_bbox_screen_fraction'][1][0]
    assert result['prepared_centerline_bbox_screen_fraction'][1][1]>result['unsmoothed_bbox_screen_fraction'][1][1]
    assert result['visible_outside_points_verified'] is False


def test_noncentral_projection_includes_orthographic_y_flip_in_top_left_basis():
    recipe,_=control('p=sample*7;x=.25+.1*cos(p);y=.75+.1*sin(p);')
    result=projected(recipe,{'viewport':[1920,1080],'wave_use_dots':True})
    assert result['nominal_centre_screen_fraction']==pytest.approx([.25,.5-.25*1920/1080])
    assert result['nominal_centre_pixels']==pytest.approx([480,60])
    assert result['signed_final_clip_ndc_angular_orientation']==1


def test_time_growing_radius_keeps_bbox_unknown_without_time_domain():
    recipe,_=control('p=sample*100+time*10;d=.3*sample+.2*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    result=projected(recipe)
    assert result['unsmoothed_bbox_screen_fraction'] is None
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['maximum_nominal_fixed_sample_point_speed_pixels_per_second'] is None
    assert result['maximum_nominal_interior_locus_normal_speed_pixels_per_second'] is not None
    assert result['possible_coordinate_clipping'] is None
    assert result['unknown_reasons']


def test_declared_time_domain_bounds_growth_without_inventing_lifetime_domain():
    recipe,_=control('p=sample*100+time*10;d=.3*sample+.2*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    result=projected(recipe,{'viewport':[1000,1000],'source_time_domain':[0,2]})
    assert result['nominal_radius_pixels_upper_bound']>=700
    assert result['source_time_domain']==[0,2]
    assert result['unsmoothed_bbox_screen_fraction'] is not None
    assert result['maximum_nominal_fixed_sample_point_speed_pixels_per_second']>=7000
    assert result['time_domain_is_observed'] is False


def test_negative_radius_is_not_clipped_to_zero_or_mirrored_without_conditions():
    recipe,_=control('p=sample*100+time*10;x=.5-.5*sample*sin(p);y=.5-.5*sample*cos(p);')
    result=projected(recipe,{'viewport':[1920,1080],'wave_use_dots':True})
    assert result['nominal_radius_pixels_upper_bound']==960
    assert result['unsmoothed_bbox_screen_fraction'][1][0]<0
    assert result['radius_source_interval']==[-.5,0]


@pytest.mark.parametrize('viewport', [[0,1080],[-1,1080],[1920,float('inf')],[True,1080],[1920],None])
def test_invalid_declared_viewport_retains_unknown_projection(viewport):
    recipe,_=control(SPIRAL)
    result=projected(recipe,{'viewport':viewport})
    assert result['status']=='unresolved'
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['maximum_nominal_fixed_sample_point_speed_pixels_per_second'] is None


def test_single_point_nonfinite_sample_hazard_blocks_geometry_bounds():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    recipe['sample_domain']['effective_samples']=1
    recipe['sample_domain']['single_dot_nonfinite_sample_excluded']=False
    result=projected(recipe)
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['maximum_nominal_fixed_sample_point_speed_pixels_per_second'] is None


def test_nonfinite_or_missing_exact_coefficient_does_not_become_zero():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    del recipe['radius_affine_coefficients_exact']
    recipe['radius_affine_coefficients']['sample']=float('inf')
    result=projected(recipe)
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']


def test_smoothing_operator_allows_overshoot_without_evaluating_a_waveform():
    recipe,_=control('p=sample*7;x=.5+.2*cos(p);y=.5+.2*sin(p);')
    result=projected(recipe,{'viewport':[1000,1000],'wave_use_dots':False})
    smooth=result['smoothing_operator']
    assert smooth['negative_weights_present'] is True
    expected=sum(abs(Fraction(value))*Fraction(smooth['native_float32_inverse_sum']) for value in smooth['native_float32_constants'])
    assert Fraction(smooth['nominal_l1_gain_upper_bound'])>=expected
    assert smooth['nominal_l1_gain_upper_bound']>1.29
    assert result['prepared_centerline_bbox_screen_fraction'][0][0]<.3
    assert result['prepared_centerline_bbox_screen_fraction'][0][1]>.7
    assert result['unsmoothed_bbox_screen_fraction'][0]==pytest.approx([.3,.7],abs=1e-7)


def test_dots_do_not_acquire_line_smoothing_vertices():
    recipe,_=control(SPIRAL)
    result=projected(recipe,{'wave_use_dots':True})
    assert result['prepared_centerline_bbox_screen_fraction']==result['unsmoothed_bbox_screen_fraction']
    assert result['smoothing_operator']['applied'] is False


def test_explicit_coefficient_enclosures_can_supply_conditional_geometry_bounds():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    del recipe['radius_affine_coefficients_exact']
    recipe['radius_affine_coefficient_enclosures']={'constant':[0,0],'sample':[.49,.51],'time':[0,0]}
    result=projected(recipe,{'wave_use_dots':True})
    assert result['nominal_radius_pixels_upper_bound']>=.51*1920
    assert result['maximum_nominal_interior_locus_normal_speed_pixels_per_second']>=.051*1920
    assert result['coefficient_domain_basis']=='declared_exact_or_enclosed_source_coefficients'


def test_phase_sample_enclosure_crossing_zero_keeps_locus_conversion_unknown():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    del recipe['phase_affine_coefficients_exact']
    recipe['phase_affine_coefficient_enclosures']={'constant':[0,0],'sample':[-1,1],'time':[10,10]}
    result=projected(recipe)
    assert result['prepared_centerline_bbox_screen_fraction'] is not None
    assert result['maximum_nominal_interior_locus_normal_speed_pixels_per_second'] is None


def test_nonfinite_projection_conversion_does_not_leave_infinite_metadata():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    recipe['centre_source_xy_exact'][0]={'numerator':str(10**307),'denominator':'1'}
    result=projected(recipe)
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']


def test_malformed_exact_coefficient_remains_unresolved():
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    recipe['radius_affine_coefficients_exact']['sample']['numerator']=None
    result=projected(recipe)
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']


@pytest.mark.parametrize('time', [[2,0],[0,float('inf')],[0,True]])
def test_invalid_declared_time_domain_does_not_fabricate_growth_bounds(time):
    recipe,_=control('p=sample*100+time*10;d=.3*sample+.2*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    result=projected(recipe,{'source_time_domain':time})
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']


@pytest.mark.parametrize('context', [5,[],'invalid',True])
def test_unsupported_json_context_containers_return_unresolved_evidence(context):
    recipe,_=control(SPIRAL)
    result=projected(recipe,context)
    assert result['status']=='unresolved'
    assert result['viewport'] is None
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']


@pytest.mark.parametrize('domain', [None,[],5,'invalid',True])
def test_unsupported_json_sample_domain_containers_return_unresolved_evidence(domain):
    recipe,_=control(SPIRAL)
    recipe=deepcopy(recipe)
    recipe['sample_domain']=domain
    result=projected(recipe)
    assert result['status']=='unresolved'
    assert result['prepared_centerline_bbox_screen_fraction'] is None
    assert result['unknown_reasons']
