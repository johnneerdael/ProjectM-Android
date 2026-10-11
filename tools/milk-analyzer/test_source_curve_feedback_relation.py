"""Source-only local polar/feedback relations; no points, frames or shaders run."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

import pytest


ROOT=Path(__file__).resolve().parents[2]
SPIRAL='p=sample*100+time*10;x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);'


def inputs(body=None, *, a=1,b=.01,viewport=(480,270),radius=(1,1),fps=30,time=None):
    import effect_families as ef
    from source_parametric_wave import parametric_wave_from_analysis
    from source_curve_projection import curve_projection
    from source_affine_radial_feedback import affine_radial_feedback
    from source_feedback_envelopes import feedback_envelope

    raw=(ROOT/'core/src/main/assets/presets/Zylot - Spiral.milk').read_bytes() if body is None else (
        'MILKDROP_PRESET_VERSION=201\n[preset00]\nPSVERSION_COMP=0\nPSVERSION_WARP=0\n'
        'fWaveAlpha=0\nfZoomExponent=1\nwavecode_0_enabled=1\nwavecode_0_samples=512\n'
        'per_frame_1=warp=0;rot=0;decay=.92;\nper_pixel_1=zoom='+str(a)+'+rad*'+str(b)+';\n'
        'wave_0_per_point1='+body+'\n').encode()
    reader=ROOT/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'curve-feedback.milk'
        path.write_bytes(raw)
        source=json.loads(subprocess.check_output([str(reader),str(path)]))
    source['preset_sha256']=hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    context={'viewport':list(viewport),'source_radius_domain':list(radius),'feedback_fps':fps,'wave_use_dots':False}
    if time is not None:context['source_time_domain']=time
    token=ef._CACHE.set({})
    try:
        analysis=ef._Analysis(source,'gles300',None)
        analysis.input_scenario=None
        analysis.main_equations();analysis.primitives()
        curve=parametric_wave_from_analysis(analysis,'wave_0')
        projection=curve_projection(curve,context)
        radial=affine_radial_feedback(analysis,context)
        colour=feedback_envelope(analysis)
    finally:ef._CACHE.reset(token)
    return curve,projection,radial,colour


def relation(values=None,context=None):
    from source_curve_feedback_relation import curve_feedback_relation
    result=curve_feedback_relation(*(inputs() if values is None else values),context=context)
    json.dumps(result,allow_nan=False)
    return result


def exact(value):return Fraction(int(value['numerator']),int(value['denominator']))


def test_actual_zylot_local_feedback_source_shift_and_turn_pitch_are_scoped():
    values=inputs()
    result=relation(values)
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['viewport']==[480,270]
    assert result['declared_feedback_fps']==30
    a=exact(values[2]['zoom_affine_coefficients_exact']['a'])
    b=exact(values[2]['zoom_affine_coefficients_exact']['b'])
    delta=a/(1-b)-1
    low,high=map(Fraction,result['feedback_inverse_pixel_step_interval'])
    assert low<=240*delta<=high
    assert float(240*delta)==pytest.approx(2.306420297333688)
    low,high=map(Fraction,result['new_source_pixel_step_interval'])
    assert low<=-Fraction(4,5)<=high
    low,high=map(Fraction,result['relative_old_minus_new_pixel_step_interval'])
    assert low<=240*delta+Fraction(4,5)<=high
    low,high=result['interturn_pitch_pixels_interval']
    assert low<=480*math.pi/100<=high
    assert high==pytest.approx(15.079644737231009,abs=1e-5)
    assert result['local_nominal_step_spacing_less_than_interturn_pitch'] is True
    assert result['colour_difference_gain_upper_bound']==pytest.approx(.92,abs=1e-7)
    assert result['actual_trail_thickness_pixels'] is None
    assert result['final_visible_density'] is None
    assert result['whole_preset_activity_credit'] is False
    assert result['uses_equation_execution'] is False


def test_exact_native_radial_rate_and_one_step_relative_difference():
    result=relation(inputs(SPIRAL,a=1,b=0))
    assert exact(result['signed_native_fixed_angle_radial_rate_exact'])==-Fraction(1,10)
    assert result['feedback_inverse_radius_step_interval']==[0,0]
    low,high=map(Fraction,result['relative_old_minus_new_pixel_step_interval'])
    assert low<=Fraction(4,5)<=high


@pytest.mark.parametrize('viewport', [(480,270),(270,480),(480,480)])
def test_pixel_pitch_uses_the_declared_long_dimension(viewport):
    result=relation(inputs(viewport=viewport))
    assert result['status']=='conditional_local_curve_feedback_relation'
    low,high=result['interturn_pitch_pixels_interval']
    assert low<=480*math.pi/100<=high
    assert result['nominal_native_radius_to_pixel_scale']==240


def test_noncentral_source_curve_cannot_borrow_central_feedback_relation():
    values=inputs(SPIRAL.replace('x=.5','x=.4'))
    assert relation(values)['status']=='unknown'


def test_phase_sample_zero_does_not_invent_interturn_pitch_or_radial_relation():
    values=inputs(SPIRAL.replace('sample*100+time*10','time*10'))
    result=relation(values)
    assert result['status']=='unknown'
    assert result['relative_old_minus_new_pixel_step_interval'] is None


def test_negative_sample_radius_preserves_positive_local_radius_branch_when_regular():
    values=inputs('p=sample*100+time*10;d=.5-.5*sample;x=.5+d*sin(p);y=.5+d*cos(p);',a=1,b=0,radius=(.5,.5))
    result=relation(values)
    assert exact(result['signed_native_fixed_angle_radial_rate_exact'])==Fraction(1,10)
    low,high=map(Fraction,result['relative_old_minus_new_pixel_step_interval'])
    assert low<=-Fraction(4,5)<=high


def test_negative_physical_radius_and_no_adjacent_turn_abstain():
    negative=inputs('p=sample*100+time*10;x=.5-.5*sample*sin(p);y=.5-.5*sample*cos(p);')
    assert relation(negative)['status']=='unknown'
    arc=inputs(SPIRAL.replace('sample*100','sample*3'),radius=(.5,.5))
    assert relation(arc)['status']=='unknown'


@pytest.mark.parametrize('fps', [None,0,-1,float('inf'),True,[]])
def test_invalid_or_absent_cadence_abstains(fps):
    result=relation(context={'feedback_fps':fps})
    assert result['status']=='unknown'
    assert result['relative_old_minus_new_pixel_step_interval'] is None


@pytest.mark.parametrize('radius', [[0,0],[-1,1],[100,100],[2,2],[.001,.001]])
def test_zero_inverse_pole_outside_or_future_branch_invalid_domains_abstain(radius):
    result=relation(context={'source_radius_domain':radius})
    assert result['status']=='unknown'
    assert result['relative_old_minus_new_pixel_step_interval'] is None


def test_time_growth_needs_a_declared_domain_covering_the_comparison_step():
    body='p=sample*100+time*10;d=.5*sample+.05*time;x=.5+d*sin(p);y=.5+d*cos(p);'
    assert relation(inputs(body))['status']=='unknown'
    result=relation(inputs(body,time=[0,2]),{'local_source_time_domain':[0,1]})
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert exact(result['signed_native_fixed_angle_radial_rate_exact'])!=0


@pytest.mark.parametrize('field', ['curve_hash','projection_hash','engine','viewport','radial_status'])
def test_mismatched_unqualified_reference_inputs_abstain(field):
    values=list(deepcopy(inputs()))
    if field=='curve_hash':values[0]['source_provenance']['preset_sha256']='f'*64
    elif field=='projection_hash':values[1]['source_curve_provenance']['preset_sha256']='f'*64
    elif field=='engine':values[2]['source_provenance']['parser_inputs']['engine']['commit']='unsupported'
    elif field=='viewport':values[1]['viewport']=[1920,1080]
    elif field=='radial_status':values[2]['status']='unknown'
    result=relation(tuple(values))
    assert result['status']=='unknown'
    assert result['unknown_reasons']


def test_unknown_colour_envelope_does_not_erase_independent_geometry_or_fill_gain():
    values=list(inputs())
    values[3]={'policy':'source-varying-affine-feedback-colour-envelope-v1','source_model':'unknown','conditions':['unknown colour']}
    result=relation(tuple(values))
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['colour_difference_gain_upper_bound'] is None
    assert result['final_visible_density'] is None


def test_unsupported_colour_model_cannot_supply_a_stale_half_life_reference():
    values=list(inputs())
    values[3]={'policy':'unsupported','source_model':'unknown',
               'ideal_perturbation_half_life_upper_bound_evaluations':10}
    result=relation(tuple(values))
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['ideal_colour_half_life_evaluations_reference'] is None


@pytest.mark.parametrize('context', [5,[],'invalid',True])
def test_unsupported_context_containers_return_unknown(context):
    assert relation(context=context)['status']=='unknown'


def test_enclosing_radial_disk_is_not_rectangular_ray_or_wrapping_proof():
    result=relation(inputs(radius=(.8,.8)))
    assert result['directional_rectangular_clipping_may_intervene'] is True
    assert result['feedback_history_or_wrapping_verified'] is False
    assert result['actual_overlap_verified'] is False


def test_finite_adjacent_sample_with_negative_radius_is_not_same_angle_branch():
    body='p=sample*7;d=.01-sample;x=.5+d*sin(p);y=.5+d*cos(p);'
    result=relation(inputs(body,radius=(.0198,.0198)))
    assert result['status']=='unknown'
    assert result['interturn_pitch_pixels_interval'] is None


def test_adjacent_positive_radius_must_survive_the_comparison_time_step():
    body='p=sample*7;d=.01+.5*sample-time;x=.5+d*sin(p);y=.5+d*cos(p);'
    result=relation(inputs(body,radius=(.92,.92),time=[0,1]),{'local_source_time_domain':[0,0]})
    assert result['status']=='unknown'
    assert result['interturn_pitch_pixels_interval'] is None


def test_declared_n_steps_use_closed_form_not_half_life_times_displacement():
    values=inputs(radius=(.8,.8))
    result=relation(values,{'feedback_step_counts':[5,8]})
    rows=result['nominal_n_step_relations']
    assert [row['declared_steps'] for row in rows]==[5,8]
    a=exact(values[2]['zoom_affine_coefficients_exact']['a'])
    b=exact(values[2]['zoom_affine_coefficients_exact']['b'])
    r=Fraction(.8)
    for row,n in zip(rows,(5,8)):
        assert row['status']=='conditional_closed_form_radial_relation'
        power=a**n
        series=(power-1)/(a-1)
        retained=power*r/(1-b*r*series)
        fresh=r-Fraction(n,300)
        low,high=map(Fraction,row['relative_old_minus_new_pixel_separation_interval'])
        assert low<=240*(retained-fresh)<=high
        assert row['directional_rectangular_clipping_may_intervene'] is True
        assert row['actual_trail_thickness_pixels'] is None
        assert row['ideal_colour_difference_gain_power_upper_bound'] is not None
    assert rows[0]['relative_old_minus_new_pixel_separation_interval'][1]<result['interturn_pitch_pixels_interval'][0]
    assert rows[1]['relative_old_minus_new_pixel_separation_interval'][0]>result['interturn_pitch_pixels_interval'][1]
    assert rows[1]['relative_old_minus_new_pixel_separation_interval'][1]==pytest.approx(18.70825501470104,abs=1e-10)
    assert result['uses_iterated_frame_updates'] is False


def test_a_equal_one_closed_form_series_is_n_without_near_zero_division():
    values=inputs(SPIRAL,a=1,b=.01,radius=(.8,.8))
    result=relation(values,{'feedback_step_counts':[8]})
    row=result['nominal_n_step_relations'][0]
    retained=Fraction(.8)/(1-Fraction(.01)*Fraction(.8)*8)
    low,high=map(Fraction,row['retained_native_radius_interval'])
    assert low<=retained<=high


def test_n_step_domain_failure_retains_valid_one_step_relation():
    result=relation(context={'feedback_step_counts':[16]})
    assert result['status']=='conditional_local_curve_feedback_relation'
    row=result['nominal_n_step_relations'][0]
    assert row['status']=='unknown'
    assert row['relative_old_minus_new_pixel_separation_interval'] is None
    assert row['unknown_reasons']


@pytest.mark.parametrize('counts', [[0],[129],[True],5,list(range(1,18))])
def test_optional_step_counts_have_explicit_small_integer_budgets(counts):
    result=relation(context={'feedback_step_counts':counts})
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['nominal_n_step_relations']==[]
    assert result['unknown_reasons']


def test_clipping_comparison_includes_fresh_radius_outside_vertical_disk():
    body='p=sample*100-50;d=.5*sample+time;x=.5+d*sin(p);y=.5+d*cos(p);'
    values=inputs(body,a=1,b=0,radius=(.5,.5),time=[0,1])
    result=relation(values,{'local_source_time_domain':[0,0],'feedback_step_counts':[4]})
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['directional_rectangular_clipping_may_intervene'] is True
    assert result['nominal_old_layer_directional_clipping_may_intervene'] is False
    assert result['nominal_fresh_branch_directional_clipping_may_intervene'] is True
    row=result['nominal_n_step_relations'][0]
    assert row['status']=='conditional_closed_form_radial_relation'
    assert row['directional_rectangular_clipping_may_intervene'] is True
    assert row['nominal_old_layer_directional_clipping_may_intervene'] is False
    assert row['nominal_fresh_branch_directional_clipping_may_intervene'] is True


def test_clipping_comparison_includes_adjacent_positive_radius_branch():
    # Current/fresh radius .02 lies inside the viewport, but the only admissible
    # neighbour is at a larger radius (~1.815 native units).
    body='p=sample*7;x=.5+(.01+sample)*sin(p);y=.5+(.01+sample)*cos(p);'
    values=inputs(body,a=1,b=0,radius=(.02,.02))
    result=relation(values,{'feedback_step_counts':[4]})
    assert result['status']=='conditional_local_curve_feedback_relation'
    assert result['directional_rectangular_clipping_may_intervene'] is True
    assert result['nominal_old_layer_directional_clipping_may_intervene'] is False
    assert result['nominal_fresh_branch_directional_clipping_may_intervene'] is False
    assert result['nominal_adjacent_branch_directional_clipping_may_intervene'] is True
    row=result['nominal_n_step_relations'][0]
    assert row['directional_rectangular_clipping_may_intervene'] is True
    assert row['nominal_adjacent_branch_directional_clipping_may_intervene'] is True
