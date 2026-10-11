"""Raw affine RGBA labels are separate from continuous geometric-locus drift."""
from copy import deepcopy
from fractions import Fraction
import importlib.util
import json
import math

import pytest

from test_source_parametric_wave import control, source_record, SPIRAL
from test_source_curve_feedback_relation import inputs, ROOT


def exact(value):
    return Fraction(int(value['numerator']), int(value['denominator']))


def motion(recipe, projection=None, context=None):
    assert importlib.util.find_spec('source_material_marker_motion') is not None, 'material-marker producer is absent'
    from source_material_marker_motion import material_marker_motion
    result=material_marker_motion(recipe, projection, context)
    json.dumps(result, allow_nan=False)
    return result


def test_selected_spiral_raw_marker_rotates_faster_than_geometric_normal_drift():
    recipe, projection, _, _=inputs()
    assert recipe['source_provenance']['preset_sha256']=='02481b33b1399e5a186bc12f5f4230bb00d368edfd802857e4a2dac4831f5923'
    result=motion(recipe, projection, {'viewport':[480,270]})
    assert result['status']=='conditional_raw_material_marker'
    assert result['raw_material_status']=='sample_varying_common_label'
    assert exact(result['marker_sample_rate_exact'])==0
    assert exact(result['marker_radius_rate_exact'])==0
    assert exact(result['marker_phase_rate_exact'])==10
    assert result['maximum_marker_source_speed_per_second']==5
    assert result['nominal_marker_pixels_speed_per_second']==2400
    # Ceiling covers the float32 stored-aspect y scale 480.0000035762787.
    assert 2400.0000178<result['maximum_marker_pixels_speed_per_second']<2400.00002
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second']==.05
    assert result['visible_motion_speed'] is None
    assert result['unique_visible_particles_verified'] is False
    assert result['whole_preset_activity_credit'] is False
    assert result['uses_equation_execution'] is False
    assert result['uses_rendered_images'] is False


def test_all_rgba_ratios_agree_and_radius_phase_rates_follow_label_branch():
    recipe,_=control(SPIRAL+'r=2*sample+4*time;g=-3*sample-6*time;b=.2;a=sample+2*time;')
    result=motion(recipe)
    assert exact(result['marker_sample_rate_exact'])==-2
    assert exact(result['marker_radius_rate_exact'])==-1
    assert exact(result['marker_phase_rate_exact'])==-190
    assert result['maximum_marker_source_speed_per_second']>=math.sqrt(1+95**2)
    assert result['maximum_marker_source_speed_per_second']<math.sqrt(1+95**2)+1e-10
    assert result['maximum_marker_pixels_speed_per_second'] is None


@pytest.mark.parametrize('colour',[
    'r=sample+time;g=sample+2*time;b=.2;a=1;',
    'r=sample;g=.2+time;b=.2;a=1;',
    'r=sample;g=sample;b=sample;a=1+time;',
    'r=sample;g=sin(sample);b=.2;a=1;',
    'r=sample;g=value1;b=.2;a=1;',
])
def test_inconsistent_or_unsupported_labels_retain_independent_geometry(colour):
    recipe,_=control(SPIRAL+colour)
    result=motion(recipe)
    assert result['raw_material_status']=='unresolved_common_label'
    assert result['marker_sample_rate_exact'] is None
    assert result['maximum_marker_source_speed_per_second'] is None
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second']==.05
    assert result['channel_constraints']['r']['required_marker_sample_rate_exact'] is not None


@pytest.mark.parametrize('colour,status',[
    ('r=.1;g=.2;b=.3;a=1;', 'sample_uniform_static_raw_material'),
    ('r=.1+time;g=.2;b=.3;a=1;', 'sample_uniform_temporal_modulation'),
    ('r=.1;g=.2;b=.3;a=1+time;', 'sample_uniform_temporal_modulation'),
])
def test_uniform_full_circle_has_no_identifiable_marker_or_invented_speed(colour,status):
    recipe,_=control('p=sample*7+time*10;x=.5+.2*sin(p);y=.5+.2*cos(p);'+colour)
    result=motion(recipe)
    assert result['raw_material_status']==status
    assert result['status']=='conditional_uniform_raw_material'
    assert result['marker_sample_rate_exact'] is None
    assert result['maximum_marker_source_speed_per_second'] is None
    assert result['source_geometric_locus']['continuous_full_circle_locus_stationary'] is True
    assert result['missing_marker_proves_quietness'] is False


def test_radial_growth_needs_time_domain_only_when_marker_has_angular_rate():
    body='p=sample*100+time*10;d=.5*sample+.25*time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;'
    recipe,_=control(body)
    assert motion(recipe)['maximum_marker_source_speed_per_second'] is None
    bounded=motion(recipe, context={'source_time_domain':[0,2]})
    assert bounded['radius_source_interval']==[0,1]
    assert bounded['maximum_marker_source_speed_per_second']>=math.hypot(.25,10)
    # Holding the phase as well as a raw label removes the angular term.
    recipe,_=control(body.replace('r=sample;', 'r=sample+.1*time;'))
    result=motion(recipe)
    assert exact(result['marker_phase_rate_exact'])!=0  # binary source .1 is not exactly 1/10
    recipe,_=control(body.replace('r=sample;', 'r=10*sample+time;'))
    result=motion(recipe)
    assert exact(result['marker_phase_rate_exact'])==0
    assert result['maximum_marker_source_speed_per_second'] is not None


@pytest.mark.parametrize('field',['hash','engine','point_section','viewport','policy','status','scale','defaulted'])
def test_projection_failures_do_not_erase_source_marker_or_locus(field):
    recipe,projection,_,_=inputs()
    projection=deepcopy(projection)
    if field=='hash':projection['source_curve_provenance']['preset_sha256']='f'*64
    elif field=='engine':projection['source_curve_provenance']['parser_inputs']['engine']['commit']='unsupported'
    elif field=='point_section':projection['source_curve_provenance']['point_section']='wave_1_per_point'
    elif field=='viewport':projection['viewport']=[1920,1080]
    elif field=='policy':projection['policy']='unsupported'
    elif field=='status':projection['status']='unresolved'
    elif field=='scale':projection['nominal_source_to_pixel_scale_xy']=[100,100]
    elif field=='defaulted':projection['viewport_was_defaulted']=True
    result=motion(recipe,projection,{'viewport':[480,270]})
    assert result['maximum_marker_source_speed_per_second']==5
    assert result['maximum_marker_pixels_speed_per_second'] is None
    assert result['projection_unknown_reasons']
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second']==.05


@pytest.mark.parametrize('domain', [None,[1,0],[0,float('inf')],[True,1],[],5])
def test_invalid_or_absent_growth_domain_never_supplies_lifetime_angular_speed(domain):
    recipe,_=control('p=sample*100+time*10;d=.5*sample+.25*time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    result=motion(recipe,context={'source_time_domain':domain})
    assert result['maximum_marker_source_speed_per_second'] is None


@pytest.mark.parametrize('field', ['policy','waveform','count','single_dot','sample_interval','radius','phase','centre'])
def test_malformed_or_unqualified_geometry_abstains(field):
    recipe,_=control(SPIRAL+'r=sample;')
    if field=='policy':recipe['policy']='unsupported'
    elif field=='waveform':recipe['waveform_independent_geometry']=False
    elif field=='count':recipe['sample_domain']['effective_samples']=1
    elif field=='single_dot':recipe['sample_domain']['single_dot_nonfinite_sample_excluded']=False
    elif field=='sample_interval':recipe['sample_domain']['native_float32_endpoint_interval']=[1,0]
    elif field=='radius':recipe['radius_affine_coefficients_exact']['time']['denominator']='0'
    elif field=='phase':recipe['phase_affine_coefficients_exact']['sample']['numerator']=True
    elif field=='centre':recipe['centre_source_xy_exact']=None
    result=motion(recipe)
    assert result['status']=='unknown'
    assert result['maximum_marker_source_speed_per_second'] is None


@pytest.mark.parametrize('coefficient',[None,{'numerator':'1','denominator':'0'},
    {'numerator':True,'denominator':'1'}, {'numerator':str(2**8193),'denominator':'1'}])
def test_malformed_colour_coefficients_preserve_valid_locus(coefficient):
    recipe,_=control(SPIRAL+'r=sample;')
    recipe['spatial_vertex_colour']['channels']['r']['affine_coefficients_exact']['sample']=coefficient
    result=motion(recipe)
    assert result['raw_material_status']=='unresolved_common_label'
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second']==.05


def test_exact_small_label_ratio_is_not_erased_by_display_underflow():
    recipe,_=control(SPIRAL+'r=sample;')
    tiny={'numerator':'1','denominator':str(2**2200)}
    recipe['spatial_vertex_colour']['channels']['r']['affine_coefficients_exact']['time']=tiny
    result=motion(recipe)
    assert exact(result['marker_sample_rate_exact'])==-Fraction(1,2**2200)
    assert result['marker_sample_rate_per_second'] is None
    assert result['maximum_marker_source_speed_per_second']>=5


def test_unproved_native_colour_domain_cannot_supply_raw_marker():
    recipe,_=control(SPIRAL+'r=sample;')
    recipe['spatial_vertex_colour']['channels']['r']['native_float32_domain_at_source_time_zero_finite']=False
    result=motion(recipe)
    assert result['raw_material_status']=='unresolved_common_label'
    assert result['maximum_marker_source_speed_per_second'] is None
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second']==.05


def test_growth_domain_that_overflows_native_coordinates_cannot_supply_speed_ceiling():
    recipe,_=control('p=sample*100+time*10;d=.5*sample+time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;')
    result=motion(recipe,context={'source_time_domain':[0,1e40]})
    assert result['maximum_marker_source_speed_per_second'] is None
    assert exact(result['marker_phase_rate_exact'])==10
    assert result['unknown_reasons']


def test_underflowing_nonzero_speed_rounds_up_instead_of_inventing_zero():
    recipe,_=control(SPIRAL+'r=sample;')
    recipe['phase_affine_coefficients_exact']['time']={'numerator':'1','denominator':str(2**2200)}
    result=motion(recipe)
    assert exact(result['marker_phase_rate_exact'])==Fraction(1,2**2200)
    assert result['marker_phase_rate_radians_per_second'] is None
    assert result['maximum_marker_source_speed_per_second']==math.ulp(0.)


def test_approximate_numeric_display_cannot_override_exact_label_coefficients():
    recipe,_=control(SPIRAL+'r=sample;')
    recipe['spatial_vertex_colour']['channels']['r']['affine_coefficients']={'sample':0,'time':100,'constant':0}
    assert exact(motion(recipe)['marker_sample_rate_exact'])==0


def test_negative_radius_and_phase_sample_zero_keep_material_rate_without_fixed_angle_relation():
    recipe,_=control('p=time*10;x=.5-.5*sample*sin(p);y=.5-.5*sample*cos(p);r=sample;')
    result=motion(recipe)
    assert result['maximum_marker_source_speed_per_second']==5
    assert result['source_geometric_locus']['maximum_interior_normal_source_speed_per_second'] is None


def test_raw_local_scope_does_not_certify_fmod_alpha_or_visible_particle_tracking():
    recipe,_=source_record((ROOT/'core/src/main/assets/presets/Zylot - Spiral.milk').read_bytes())
    result=motion(recipe)
    text=' '.join(result['conditions']).lower()
    for phrase in ['across zero','alpha saturation','repeated labels','finite sample','feedback','local branch']:
        assert phrase in text
    assert result['native_numeric_certified'] is False
    assert result['actual_visible_contrast'] is None


@pytest.mark.parametrize('context',[True,[],5,'bad'])
def test_invalid_context_abstains_without_raising(context):
    recipe,_=control(SPIRAL+'r=sample;')
    assert motion(recipe,context=context)['status']=='unknown'


def test_failed_speed_bound_does_not_report_bounded_marker_status():
    body='p=sample*100+time*10;d=.5*sample+.25*time;x=.5+d*sin(p);y=.5+d*cos(p);r=sample;'
    recipe,_=control(body)
    result=motion(recipe)
    assert result['marker_phase_rate_exact'] is not None
    assert result['maximum_marker_source_speed_per_second'] is None
    assert result['status']=='conditional_marker_rates_speed_unresolved'


def test_missing_stored_aspect_scale_withholds_pixel_ceiling_only():
    recipe,projection,_,_=inputs()
    projection=deepcopy(projection);projection.pop('native_stored_aspect_source_to_pixel_scale_xy')
    result=motion(recipe,projection,{'viewport':[480,270]})
    assert result['maximum_marker_source_speed_per_second']==5
    assert result['maximum_marker_pixels_speed_per_second'] is None
    assert any('stored-aspect' in reason for reason in result['projection_unknown_reasons'])
