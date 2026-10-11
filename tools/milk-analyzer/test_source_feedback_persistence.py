"""Quantized RGBA8 decay orbits under explicit arithmetic profiles."""
from fractions import Fraction
import json
import math

import numpy as np
import pytest


def transfer(gain=float(np.float32(.92)),**changes):
    row={'policy':'source-warp-colour-transfer-v1','source_model':'fixed_main_decay',
         'uniform_diagonal_gain':gain,'constant_offset_rgb':[0.0,0.0,0.0],
         'matrix_rgb':[[gain,0,0],[0,gain,0],[0,0,gain]],'coordinate_feedback_dependency':False}
    row.update(changes)
    return row


def persistence(row,context=None):
    from source_feedback_persistence import unorm8_decay_persistence
    result=unorm8_decay_persistence(row,{'output_storage':'normalized-unorm','feedback_fps':30.0}
                                    if context is None else context)
    json.dumps(result,allow_nan=False)
    return result


def brute(gain,profile):
    """Independent orbit: round-half-up is safe because tie inputs are excluded."""
    def step(k):
        if profile=='real':value=Fraction(k)*Fraction(gain)
        else:
            kind=np.float32 if profile=='float32' else np.float16
            value=Fraction(float(kind(kind(k/255)*kind(gain))))*255
        return math.floor(value+Fraction(1,2))
    orbit=[255]
    while step(orbit[-1])!=orbit[-1]:orbit.append(step(orbit[-1]))
    return orbit


def test_zylot_decay_stalls_at_a_nonzero_rgba8_floor_in_every_profile():
    result=persistence(transfer())
    assert result['status'] in {'conditional_quantized_decay_orbit','conditional_quantized_decay_orbit_profile_dependent'}
    assert result['floor_level_interval']==[6,6]
    assert result['steps_to_floor_interval']==[43,43]
    assert result['steps_to_half_interval']==[9,9]
    assert result['largest_stuck_level_interval']==[6,6]
    assert result['level_orbit_from_full']==brute(float(np.float32(.92)),'float32')
    assert result['permanent_residual_possible'] is True
    assert 'truncation' in result['conversion_rule']
    assert result['visible_trail_length'] is None


@pytest.mark.parametrize('gain',[.6,.8,.9,.95,.97,.98,.99,.995])
@pytest.mark.parametrize('profile',['real','float32','fp16_mediump'])
def test_each_profile_matches_independent_orbit(gain,profile):
    gain=float(np.float32(gain))
    result=persistence(transfer(gain))
    assert result['profiles'][profile]['level_orbit_from_full']==brute(gain,profile)


def test_near_tie_levels_make_profiles_disagree_and_widen_intervals():
    result=persistence(transfer(float(np.float32(.95))))
    assert result['status']=='conditional_quantized_decay_orbit_profile_dependent'
    assert result['profiles']['real']['floor_level_from_full']==9
    assert result['profiles']['float32']['floor_level_from_full']==10
    assert result['floor_level_interval']==[9,10]


def test_gain_close_to_one_never_decays_from_full_white():
    result=persistence(transfer(float(np.float32(.999))))
    assert result['largest_stuck_level_interval']==[255,255]
    assert result['steps_to_floor_interval']==[0,0]
    assert result['steps_to_half_interval'] is None
    assert result['quantized_decay_absent'] is True


def test_exact_tie_is_reported_as_ambiguous_branch():
    result=persistence(transfer(.5))
    assert result['status']=='conditional_quantized_decay_orbit_ambiguous_ties'
    assert result['tie_levels']
    assert result['level_orbit_from_full'] is None


@pytest.mark.parametrize('row',[
    transfer(source_model='custom_shader'),transfer(constant_offset_rgb=[.01,0,0]),
    transfer(gain=1.5),transfer(gain=0.0),transfer(gain=float('nan')),transfer(coordinate_feedback_dependency=True),
    transfer(policy='unsupported'),None])
def test_unsupported_transfer_abstains(row):
    result=persistence(row)
    assert result['status']=='unknown'
    assert result['largest_stuck_level'] is None
    assert result['unknown_reasons']


def test_unknown_storage_abstains():
    assert persistence(transfer(),{'output_storage':'unknown','feedback_fps':30.0})['status']=='unknown'


def test_missing_fps_keeps_steps_without_seconds():
    result=persistence(transfer(),{'output_storage':'normalized-unorm'})
    assert result['steps_to_floor_from_full'] is not None
    assert result['seconds_to_floor_from_full'] is None


def relation(steps,step=(1.3,1.35)):
    rows=[{'declared_steps':n,'status':'conditional_closed_form_radial_relation',
           'relative_old_minus_new_pixel_separation_interval':[step[0]*n,step[1]*n]} for n in steps]
    return {'policy':'source-curve-feedback-relation-v1','status':'conditional_local_curve_feedback_relation',
            'interturn_pitch_pixels_interval':[15.0,15.1],'relative_old_minus_new_pixel_step_interval':list(step),
            'nominal_n_step_relations':rows}


def sweep(rel,per):
    from source_feedback_persistence import persistence_layer_sweep
    result=persistence_layer_sweep(rel,per)
    json.dumps(result,allow_nan=False)
    return result


def test_floor_horizon_crosses_gap_while_half_horizon_does_not():
    result=sweep(relation([1,4,9,16,43]),persistence(transfer()))
    assert result['status']=='conditional_persistence_layer_sweep'
    half,floor=result['horizons']
    assert (half['horizon'],half['steps'],half['separation_exceeds_pitch'])==('half_level',9,False)
    assert (floor['horizon'],floor['steps'],floor['separation_exceeds_pitch'])==('floor_level',43,True)
    assert floor['gap_crossings_lower_bound']==3
    assert result['interturn_gap_crossed_before_floor'] is True
    assert result['final_visible_density'] is None


def test_profile_dependent_floor_horizons_must_all_cross():
    per=persistence(transfer(float(np.float32(.99))))
    floors=sorted(set(per['steps_to_floor_interval']))
    assert len(floors)==2
    halves=sorted(set(per['steps_to_half_interval']))
    # Separation per step large enough that both floor horizons cross the pitch.
    result=sweep(relation([*halves,*floors],step=(1.0,1.0)),per)
    assert result['interturn_gap_crossed_before_floor'] is True
    # If only the longer floor horizon crosses, the profiles disagree: unknown.
    rel=relation([*halves,*floors],step=(1.0,1.0))
    for row in rel['nominal_n_step_relations']:
        if row['declared_steps']==floors[0]:row['relative_old_minus_new_pixel_separation_interval']=[1.0,1.0]
    assert sweep(rel,per)['interturn_gap_crossed_before_floor'] is None


def test_overlapping_interval_gives_unknown_comparison():
    rel=relation([9,43]);rel['nominal_n_step_relations'][0]['relative_old_minus_new_pixel_separation_interval']=[14.9,15.2]
    assert sweep(rel,persistence(transfer()))['horizons'][0]['separation_exceeds_pitch'] is None


@pytest.mark.parametrize('broken',['relation','missing_step','persistence'])
def test_missing_inputs_abstain_without_density_claims(broken):
    rel=relation([9,43]);per=persistence(transfer())
    if broken=='relation':rel['status']='unknown'
    elif broken=='missing_step':rel['nominal_n_step_relations']=rel['nominal_n_step_relations'][:1]
    else:per=persistence(None)
    result=sweep(rel,per)
    assert result['interturn_gap_crossed_before_floor'] is None
    if broken!='missing_step':assert result['status']=='unknown'


RADIAL={'status':'conditional_affine_radial_sampler','radial_sampling_derivative_range':[0.9779065121243907,1.0004862526001754],
        'nominal_zoom_range':[0.9995139837265015,1.0109874585706802]}


def spread(rel,per,context=None,radial=RADIAL):
    from source_feedback_persistence import bilinear_diffusion_spread
    result=bilinear_diffusion_spread(rel,per,context,radial=radial)
    json.dumps(result,allow_nan=False)
    return result


def test_spread_bound_includes_feature_map_stretch():
    result=spread(relation([9,43]),persistence(transfer()))
    assert result['status']=='conditional_bilinear_spread_bound'
    stretch=1/RADIAL['radial_sampling_derivative_range'][0]
    assert result['feature_map_stretch_upper']==pytest.approx(stretch)
    half,floor=result['horizons']
    expected=lambda n:math.sqrt(stretch**2*(stretch**(2*n)-1)/(stretch**2-1)/4)
    assert half['sigma_upper_pixels']==pytest.approx(expected(9))
    assert floor['sigma_upper_pixels']==pytest.approx(expected(43))
    assert floor['sigma_upper_pixels']>math.sqrt(43/4)
    assert result['adjacent_layer_merge_possible'] is True


def test_merge_uses_largest_horizon_and_never_asserts_false():
    assert spread(relation([9,43],step=(5,6)),persistence(transfer()))['adjacent_layer_merge_possible'] is True
    assert spread(relation([9,43],step=(50,60)),persistence(transfer()))['adjacent_layer_merge_possible'] is None


def test_spread_requires_qualified_radial_stretch():
    result=spread(relation([9,43]),persistence(transfer()),radial=None)
    assert result['status']=='unknown'
    assert result['adjacent_layer_merge_possible'] is None


def test_declared_scale_only_records_extra_pass_exclusion():
    rel=relation([9,43])
    assert spread(rel,persistence(transfer()),{'feedback_diffusion_scale':2.0})['extra_diffusion_pass_excluded'] is False
    assert spread(rel,persistence(transfer()),{'feedback_diffusion_scale':1.0})['extra_diffusion_pass_excluded'] is True


def test_horizons_include_every_profile_value():
    from source_feedback_persistence import persistence_horizon_steps
    per=persistence(transfer(float(np.float32(.99))))
    counts={count for name,count in persistence_horizon_steps(per) if name=='floor_level'}
    assert counts=={row['steps_to_floor_from_full'] for row in per['profiles'].values()}
