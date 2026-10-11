"""Analytic custom-wave controls parsed by the pinned source34 native reader."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import subprocess
import tempfile

import pytest


def source_record(raw):
    import effect_families as ef
    from source_parametric_wave import parametric_wave_from_analysis

    if isinstance(raw,str):raw=raw.encode()
    reader=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'parametric-wave.milk'
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
        recipe=parametric_wave_from_analysis(analysis,'wave_0')
        families=analysis.families
    finally:
        ef._CACHE.reset(token)
    json.dumps(recipe,allow_nan=False)
    return recipe,families


def control(body, *, frame='', configuration=''):
    return source_record('MILKDROP_PRESET_VERSION=201\n[preset00]\nPSVERSION_COMP=0\nfWaveAlpha=0\n'
        'wavecode_0_enabled=1\n'+configuration+frame+
        'wave_0_per_point1='+body+'\n')


SPIRAL='p=sample*100+time*10;x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);'


def test_actual_zylot_spiral_exports_radius_phase_colour_and_source_motion():
    path=Path(__file__).resolve().parents[2]/'core/src/main/assets/presets/Zylot - Spiral.milk'
    recipe,families=source_record(path.read_bytes())
    assert recipe['curve_class']=='affine_radius_polar_spiral_candidate'
    assert recipe['centre_source_xy']==[.5,.5]
    assert recipe['radius_affine_coefficients']=={'constant':0.,'sample':.5,'time':0.}
    assert recipe['phase_affine_coefficients']=={'constant':0.,'sample':100.,'time':10.}
    assert recipe['nominal_turns_across_sample_domain']==pytest.approx(100/math.tau)
    assert recipe['nominal_phase_cycles_per_source_second']==pytest.approx(10/math.tau)
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']==5
    assert recipe['signed_native_ndc_angular_orientation']==-1
    assert recipe['waveform_independent_geometry'] is True
    assert recipe['sample_domain']['nominal_interval']==[0,1]
    assert recipe['spatial_vertex_colour']['channels']['r']['affine_coefficients']['sample']==25
    assert recipe['spatial_vertex_colour']['channels']['g']['affine_coefficients']['sample']==15
    assert recipe['spatial_vertex_colour']['channels']['b']['affine_coefficients']['sample']==5
    assert recipe['spatial_vertex_colour']['temporal_flash_frequency_hz'] is None
    family=next(row for row in families if row['mechanism']=='parametric_radial_curve')
    assert family['parameters']['source_curve_recipe']==recipe
    assert family['parameters']['exact_circle_proven'] is False
    assert recipe['visible_motion_speed'] is None
    assert recipe['uses_equation_execution'] is False
    assert recipe['source_provenance']['preset_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()


def test_joint_rgb_spatial_period_preserves_channel_correlation_without_flash_claims():
    from source_material_temporal import PERIOD
    recipe,_=control(SPIRAL+'r=.5+25*sample;g=.5+15*sample;b=.5+5*sample;')
    joint=recipe['spatial_vertex_colour']['joint_rgb_spatial_pattern']
    assert joint['status']=='nominal_rgb_modulo_congruence'
    assert joint['signed_channel_windings']=={'r':5,'g':3,'b':1}
    period=joint['nominal_joint_period_sample_exact']
    exact=Fraction(int(period['numerator']),int(period['denominator']))
    assert exact==Fraction(PERIOD)/5
    assert joint['nominal_joint_period_sample']==pytest.approx(PERIOD/5)
    assert joint['temporal_flash_frequency_hz'] is None
    assert joint['reached_palette_verified'] is False


def test_joint_rgb_period_handles_signed_fractional_slopes_and_fixed_time_offsets():
    from source_material_temporal import PERIOD
    recipe,_=control(SPIRAL+'r=.5+.125*sample+time;g=.2-.375*sample;b=.1;')
    joint=recipe['spatial_vertex_colour']['joint_rgb_spatial_pattern']
    assert joint['signed_channel_windings']=={'r':1,'g':-3,'b':0}
    assert joint['nominal_joint_period_sample']==pytest.approx(8*PERIOD)
    assert joint['fixed_source_time_required'] is True
    assert joint['native_numeric_certified'] is False
    assert joint['native_periodicity_verified'] is False
    # Euclidean congruence does not imply signed native fmod equality when
    # translating a negative channel through zero.
    assert math.fmod(-.2,PERIOD)!=pytest.approx(math.fmod(-.2+PERIOD,PERIOD))
    assert any('across zero' in rule for rule in joint['conditions'])


def test_joint_rgb_pattern_does_not_invent_a_period_for_uniform_or_unknown_channels():
    uniform,_=control(SPIRAL+'r=.1+time;g=.2;b=.3;')
    joint=uniform['spatial_vertex_colour']['joint_rgb_spatial_pattern']
    assert joint['status']=='uniform_over_source_sample'
    assert joint['nominal_joint_period_sample'] is None
    unknown,_=control(SPIRAL+'r=sin(sample);g=.2;b=.3;')
    joint=unknown['spatial_vertex_colour']['joint_rgb_spatial_pattern']
    assert joint['status']=='unknown'
    assert joint['nominal_joint_period_sample'] is None


def test_constant_nonzero_radius_is_a_nominal_circle_and_cos_sin_reverses_orientation():
    recipe,_=control('p=sample*7-time*2;x=.4+.2*cos(p);y=.6+.2*sin(p);')
    assert recipe['curve_class']=='circle_candidate'
    assert recipe['exact_nominal_constant_radius_circle'] is True
    assert recipe['radius_affine_coefficients']['constant']==.2
    assert recipe['signed_native_ndc_angular_orientation']==1
    assert recipe['phase_affine_coefficients']['time']==-2
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']>=.4
    assert recipe['complete_circle_parameter_range'] is True


@pytest.mark.parametrize('body',[
    'x=.5+.5*sample*sin(sample*100+time*10);y=.5+.5*sample*cos(sample*99+time*10);',
    'p=sample*100+time*10;x=.5+.4*sample*sin(p);y=.5+.5*sample*cos(p);',
    'p=sample*100+time*10;x=.5+.5*sample*sin(p);y=.5+.5*sample*sin(p);',
    'p=sample*100+time*10;x=.5+.5*sample*sample*sin(p);y=.5+.5*sample*sample*cos(p);',
    'p=sample*100+bass;x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);',
    'p=sample*100+time*10;x=.5+(.5*sample+value1)*sin(p);y=.5+(.5*sample+value1)*cos(p);',
    'p=sample*100+time*10;x=x+.5*sample*sin(p);y=.5+.5*sample*cos(p);',
    'p=sample*100+time*10;x=.5+.5*sample*sin(p);y=y+.5*sample*cos(p);',
    'p=sample*100+time*10;x=.5+int(sample)*sin(p);y=.5+int(sample)*cos(p);',
    'p=if(above(bass,1),sample*100,sample*101);x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);',
    'p=sample*100+time*10;x=.5+state*sin(p);y=.5+state*cos(p);',
    'p=sample*100+time*10;x=1e100+.5*sample*sin(p);y=.5+.5*sample*cos(p);',
])
def test_mutations_do_not_gain_supported_circle_or_spiral_recipe(body):
    recipe,_=control(body)
    assert recipe is None


def test_single_dot_nonfinite_sample_cannot_use_continuous_sample_recipe():
    recipe,_=control(SPIRAL,configuration='wavecode_0_samples=1\nwavecode_0_bUseDots=1\n')
    assert recipe is None


def test_negative_radius_preserves_signed_coefficients_and_domain_conditions():
    recipe,_=control('p=sample*100+time*10;x=.5-.5*sample*sin(p);y=.5-.5*sample*cos(p);')
    assert recipe['radius_affine_coefficients']['sample']==-.5
    assert recipe['nominal_radius_interval_at_source_time_zero']==[-.5,0]
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']==5
    assert recipe['radius_sign']=='nonpositive_with_possible_zero'


def test_zero_radius_has_no_nonzero_polar_curve_or_speed_evidence():
    recipe,_=control('p=sample*100+time*10;x=.5+0*sin(p);y=.5+0*cos(p);')
    assert recipe is None


def test_radial_time_growth_has_explicit_rate_and_no_unbounded_lifetime_speed():
    recipe,_=control('p=sample*100+time*10;d=.1+.3*sample+.2*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    assert recipe['signed_radial_time_rate_source_coordinates_per_second']==.2
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second'] is None
    assert recipe['fixed_sample_source_speed_formula']


def test_stationary_phase_radial_growth_has_constant_source_speed_bound():
    recipe,_=control('p=sample*100;d=.3*sample-.2*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']==.2
    assert recipe['nominal_phase_cycles_per_source_second']==0


def test_waveform_dependent_colour_does_not_grant_whole_point_program_independence():
    recipe,_=control(SPIRAL+'r=value1;g=bass;b=sample;')
    assert recipe['waveform_independent_geometry'] is True
    assert recipe['waveform_independent_point_program'] is False
    assert recipe['spatial_vertex_colour']['channels']['r']['affine_coefficients'] is None
    assert recipe['spatial_vertex_colour']['channels']['g']['affine_coefficients'] is None


def test_native_float32_sample_enclosure_uses_the_effective_constant_count():
    recipe,_=control(SPIRAL,configuration='wavecode_0_samples=42\n')
    assert recipe['sample_domain']['effective_samples']==42
    assert recipe['sample_domain']['native_float32_endpoint_interval']==[0,1]
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']>=5


def test_ordinary_wave_does_not_gain_parametric_recipe_and_keeps_existing_mechanism():
    recipe,families=control('x=sample;y=.5+value1;')
    assert recipe is None
    assert any(row['mechanism']=='custom_wave_primitive' for row in families)
    assert not any(row['mechanism']=='parametric_radial_curve' for row in families)


def test_readonly_point_clock_snapshot_precedes_wave_frame_code():
    recipe,_=control(SPIRAL,frame='wave_0_per_frame1=time=time*2;\n')
    assert recipe['phase_affine_coefficients']['time']==10


def test_point_clock_mutation_is_persistent_across_points_and_remains_unknown():
    recipe,_=control('time=time*2;'+SPIRAL)
    assert recipe is None


def test_audio_or_state_material_does_not_gain_point_program_independence():
    recipe,_=control(SPIRAL+'a=bass;')
    assert recipe['waveform_independent_geometry'] is True
    assert recipe['waveform_independent_point_program'] is False


def test_unsupported_generic_radial_wave_retains_existing_parameter_contract():
    recipe,families=control('p=sample*100+bass;x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);')
    assert recipe is None
    family=next(row for row in families if row['mechanism']=='parametric_radial_curve')
    assert family['parameters']=={'exact_circle_proven':False}


def test_divided_dynamic_radial_rate_is_rounded_outward_after_exact_algebra():
    recipe,_=control('p=sample*100;d=.1*time/3;x=.5+d*sin(p);y=.5+d*cos(p);')
    exact=Fraction(.1)/3
    assert Fraction(recipe['maximum_fixed_sample_source_coordinate_speed_per_second'])>=exact


def test_underflowing_dynamic_radial_time_coefficient_does_not_become_static():
    recipe,_=control('p=sample*100+time*10;d=.3*sample+(1e-162*time)*1e-162;'
                     'x=.5+d*sin(p);y=.5+d*cos(p);')
    assert recipe['radius_sign_is_time_invariant'] is False
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second'] is None
    coefficient=recipe['radius_affine_coefficients_exact']['time']
    assert Fraction(int(coefficient['numerator']),int(coefficient['denominator']))==Fraction(1e-162)**2
    assert recipe['radius_affine_coefficients']['time'] is None


def test_binary64_tau_phase_does_not_prove_a_complete_mathematical_circle():
    recipe,_=control('p=sample*6.283185307179586;x=.5+.2*sin(p);y=.5+.2*cos(p);')
    assert recipe['exact_nominal_constant_radius_circle'] is True
    assert recipe['complete_circle_parameter_range'] is False


def test_stored_constant_rate_stays_distinct_from_dynamic_division():
    recipe,_=control('p=sample*100;d=.03333333333333333*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    assert Fraction(recipe['maximum_fixed_sample_source_coordinate_speed_per_second'])==Fraction(.03333333333333333)


def test_underflowing_angular_rate_has_a_nonzero_outward_speed_ceiling():
    recipe,_=control('p=sample*100+(1e-162*time)*1e-162;d=.3;x=.5+d*sin(p);y=.5+d*cos(p);')
    speed=recipe['maximum_fixed_sample_source_coordinate_speed_per_second']
    assert speed>0
    assert Fraction(speed)>=Fraction(.3)*Fraction(1e-162)**2
    assert recipe['phase_affine_coefficients']['time'] is None
    assert recipe['nominal_phase_cycles_per_source_second'] is None


def test_different_underflowing_radial_rates_do_not_become_a_shared_radius():
    recipe,_=control('p=sample*100+time*10;'
        'x=.5+(.3*sample+(1e-162*time)*1e-162)*sin(p);'
        'y=.5+(.3*sample+(2e-162*time)*1e-162)*cos(p);')
    assert recipe is None


@pytest.mark.parametrize('kind', ['add','multiply'])
def test_shared_nonlinear_dag_stops_while_constructing_terms_or_factors(kind):
    from shader_fields import Field
    from source_parametric_wave import _exact_terms,_exact_product
    node=Field('sin',(Field('input',detail={'name':'sample'}),),'float')
    for _ in range(9):node=Field(kind,(node,node),'float')
    helper=_exact_terms if kind=='add' else _exact_product
    with pytest.raises(ValueError,match='wave (term|factor) budget exceeded'):
        helper(node)


def test_optional_recipe_budget_failure_preserves_existing_radial_family(monkeypatch):
    import source_parametric_wave as wave
    def fail(*args,**kwargs):raise ValueError('wave term budget exceeded')
    monkeypatch.setattr(wave,'parametric_wave_from_analysis',fail)
    # Invoke ordinary analysis without calling the optional public helper again.
    from test_effect_families import analyze,read
    result=analyze(read('wavecode_0_enabled=1\nwave_0_per_point1='+SPIRAL+'\n'))
    family=next(row for row in result['families'] if row['mechanism']=='parametric_radial_curve')
    assert family['parameters']=={'exact_circle_proven':False}


def test_zylot_fixed_angle_locus_drift_and_raw_colour_rates_are_separate_from_points():
    path=Path(__file__).resolve().parents[2]/'core/src/main/assets/presets/Zylot - Spiral.milk'
    recipe,_=source_record(path.read_bytes())
    locus=recipe['source_locus_relation']
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']==5
    assert locus['fixed_angle_branch_radial_rate_source_coordinates_per_second']==pytest.approx(-.05)
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second']>=.05
    exact=locus['fixed_angle_branch_radial_rate_exact']
    assert Fraction(int(exact['numerator']),int(exact['denominator']))==-Fraction(1,20)
    low,high=map(Fraction,locus['fixed_angle_branch_radial_rate_enclosure'])
    assert low<=-Fraction(1,20)<=high
    colours=locus['fixed_angle_colour']['channels']
    assert [colours[name]['raw_source_colour_rate_per_second'] for name in 'rgb']==[-2.5,-1.5,-.5]
    assert all(colours[name]['native_modulo_event_frequency_hz'] is None for name in 'rgb')
    assert locus['whole_curve_locus_motion_bound'] is None
    assert locus['visible_motion_speed'] is None


def test_fast_parameter_points_on_full_circle_have_stationary_continuous_locus_only():
    recipe,_=control('p=sample*7+time*1000;x=.5+.2*cos(p);y=.5+.2*sin(p);')
    locus=recipe['source_locus_relation']
    assert recipe['maximum_fixed_sample_source_coordinate_speed_per_second']>=200
    assert locus['continuous_full_circle_locus_stationary'] is True
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second']==0
    assert locus['finite_polyline_pixels_static_proved'] is False
    assert locus['fixed_sample_colours_stationary_proved'] is False


def test_arc_does_not_gain_stationary_whole_locus_or_endpoint_proof():
    recipe,_=control('p=sample*3+time*1000;x=.5+.2*cos(p);y=.5+.2*sin(p);')
    locus=recipe['source_locus_relation']
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second']==0
    assert locus['continuous_full_circle_locus_stationary'] is None
    assert locus['whole_curve_locus_motion_bound'] is None
    assert locus['finite_parameter_endpoints_motion_resolved'] is False


def test_zero_sample_phase_keeps_fixed_angle_relation_unknown():
    recipe,_=control('p=time*10;x=.5+.5*sample*sin(p);y=.5+.5*sample*cos(p);')
    locus=recipe['source_locus_relation']
    assert locus['status']=='unresolved'
    assert locus['fixed_angle_branch_radial_rate_exact'] is None
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second'] is None


@pytest.mark.parametrize('radius,expected', [('- .5*sample',Fraction(1,20)),
    ('.3*sample+.2*time',Fraction(.2)-Fraction(.3)/10)])
def test_negative_and_growing_radii_preserve_signed_locus_relation(radius,expected):
    recipe,_=control('p=sample*100+time*10;d='+radius+';x=.5+d*sin(p);y=.5+d*cos(p);')
    locus=recipe['source_locus_relation']
    exact=locus['fixed_angle_branch_radial_rate_exact']
    assert Fraction(int(exact['numerator']),int(exact['denominator']))==expected
    low,high=map(Fraction,locus['fixed_angle_branch_radial_rate_enclosure'])
    assert low<=expected<=high
    assert Fraction(locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second'])>=abs(expected)
    assert locus['radius_zero_points_excluded'] is True


def test_underflowing_locus_drift_remains_nonzero_and_outward_enclosed():
    recipe,_=control('p=sample*100+(1e-162*time)*1e-162;d=.3*sample;x=.5+d*sin(p);y=.5+d*cos(p);')
    locus=recipe['source_locus_relation']
    assert locus['fixed_angle_branch_radial_rate_source_coordinates_per_second'] is None
    exact=locus['fixed_angle_branch_radial_rate_exact']
    value=Fraction(int(exact['numerator']),int(exact['denominator']))
    assert value==-Fraction(.3)*Fraction(1e-162)**2/100
    low,high=map(Fraction,locus['fixed_angle_branch_radial_rate_enclosure'])
    assert low<=value<=high
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second']>0


def test_unknown_point_colour_is_not_replaced_by_a_fixed_angle_colour_rate():
    recipe,_=control(SPIRAL+'r=value1;g=bass;b=sample;')
    colours=recipe['source_locus_relation']['fixed_angle_colour']['channels']
    assert colours['r']['raw_source_colour_rate_exact'] is None
    assert colours['g']['raw_source_colour_rate_exact'] is None
    assert colours['b']['raw_source_colour_rate_per_second']==pytest.approx(-.1)


def test_near_cancelling_literal_radial_rates_do_not_acquire_exact_zero():
    recipe,_=control('p=sample*100+time*10;d=.5*sample+.05*time;x=.5+d*sin(p);y=.5+d*cos(p);')
    locus=recipe['source_locus_relation']
    exact=locus['fixed_angle_branch_radial_rate_exact']
    value=Fraction(int(exact['numerator']),int(exact['denominator']))
    assert value==Fraction(.05)-Fraction(1,20)>0
    assert locus['maximum_interior_geometric_normal_speed_source_coordinates_per_second']>0


def test_exactly_cancelling_colour_rates_share_geometry_reparameterization():
    recipe,_=control(SPIRAL+'r=10*sample+time;g=r;b=r;')
    channels=recipe['source_locus_relation']['fixed_angle_colour']['channels']
    assert all(channel['raw_source_colour_rate_enclosure']==[0,0] for channel in channels.values())
    assert [channels[name]['raw_source_colour_rate_per_second'] for name in 'rgb']==[0,0,0]
    assert recipe['source_locus_relation']['fixed_sample_colours_stationary_proved'] is False


def test_final_ndc_orientation_includes_the_pinned_native_orthographic_y_flip():
    engine=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/production-engine'
    projection=(engine/'src/libprojectM/MilkdropPreset/PresetState.cpp').read_text()
    assert 'orthogonalProjection = glm::ortho(-1.0f, 1.0f, 1.0f, -1.0f' in projection
    recipe,_=control(SPIRAL)
    assert recipe['signed_native_vertex_angular_orientation_before_orthographic_projection']==1
    assert recipe['signed_native_ndc_angular_orientation']==-1
