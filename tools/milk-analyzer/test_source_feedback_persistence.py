"""Quantized RGBA8 decay orbits are exact integer facts under stated premises."""
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


def brute(gain):
    orbit=[255]
    while True:
        value=orbit[-1]*gain
        following=int(math.floor(value+.5))
        if following==orbit[-1]:return orbit
        orbit.append(following)


def test_zylot_decay_stalls_at_a_nonzero_rgba8_floor():
    result=persistence(transfer())
    assert result['status']=='conditional_quantized_decay_orbit'
    assert result['largest_stuck_level']==6
    assert result['floor_level_from_full']==6
    assert result['level_orbit_from_full']==brute(float(np.float32(.92)))
    assert result['steps_to_floor_from_full']==len(result['level_orbit_from_full'])-1
    assert result['steps_to_half_from_full']==9
    assert result['permanent_residual_possible'] is True
    assert result['seconds_to_floor_from_full']==pytest.approx(result['steps_to_floor_from_full']/30)
    assert result['visible_trail_length'] is None
    assert result['uses_rendered_images'] is False


@pytest.mark.parametrize('gain',[.6,.8,.9,.95,.97,.98,.99,.995])
def test_orbit_matches_independent_rounding_for_any_gain(gain):
    gain=float(np.float32(gain))
    result=persistence(transfer(gain))
    orbit=brute(gain)
    assert result['level_orbit_from_full']==orbit
    stuck=max(k for k in range(256) if math.floor(k*gain+.5)==k)
    assert result['largest_stuck_level']==stuck
    assert all(math.floor(k*gain+.5)==k for k in range(stuck+1))


def test_gain_close_to_one_never_decays_from_full_white():
    gain=float(np.float32(.999))
    result=persistence(transfer(gain))
    assert result['largest_stuck_level']==255
    assert result['steps_to_floor_from_full']==0
    assert result['steps_to_half_from_full'] is None
    assert result['quantized_decay_absent'] is True


def test_exact_tie_is_reported_as_ambiguous_branch():
    # 0.5 * 1 = 0.5 is an exact half-level tie; GLES does not fix tie direction.
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
    result=persistence(transfer(),{'output_storage':'unknown','feedback_fps':30.0})
    assert result['status']=='unknown'


def test_missing_fps_keeps_steps_without_seconds():
    result=persistence(transfer(),{'output_storage':'normalized-unorm'})
    assert result['steps_to_floor_from_full'] is not None
    assert result['seconds_to_floor_from_full'] is None


def relation(steps):
    rows=[{'declared_steps':n,'status':'conditional_closed_form_radial_relation',
           'relative_old_minus_new_pixel_separation_interval':[1.3*n,1.35*n]} for n in steps]
    return {'policy':'source-curve-feedback-relation-v1','status':'conditional_local_curve_feedback_relation',
            'interturn_pitch_pixels_interval':[15.0,15.1],'nominal_n_step_relations':rows}


def sweep(rel,per):
    from source_feedback_persistence import persistence_layer_sweep
    result=persistence_layer_sweep(rel,per)
    json.dumps(result,allow_nan=False)
    return result


def test_floor_horizon_crosses_gap_while_half_horizon_does_not():
    per=persistence(transfer())
    result=sweep(relation([1,4,9,16,43]),per)
    assert result['status']=='conditional_persistence_layer_sweep'
    half,floor=result['horizons']
    assert (half['horizon'],half['steps'])==('half_level',9)
    assert half['separation_exceeds_pitch'] is False
    assert (floor['horizon'],floor['steps'])==('floor_level',43)
    assert floor['separation_exceeds_pitch'] is True
    assert floor['gap_crossings_lower_bound']==3
    assert result['interturn_gap_crossed_by_retained_layers_above_floor'] is True
    assert result['final_visible_density'] is None
    assert result['actual_overlap_verified'] is False


def test_overlapping_interval_gives_unknown_comparison():
    rel=relation([9,43]);rel['nominal_n_step_relations'][0]['relative_old_minus_new_pixel_separation_interval']=[14.9,15.2]
    result=sweep(rel,persistence(transfer()))
    assert result['horizons'][0]['separation_exceeds_pitch'] is None


@pytest.mark.parametrize('broken',['relation','missing_step','persistence'])
def test_missing_inputs_abstain_without_density_claims(broken):
    rel=relation([9,43]);per=persistence(transfer())
    if broken=='relation':rel['status']='unknown'
    elif broken=='missing_step':rel['nominal_n_step_relations']=rel['nominal_n_step_relations'][:1]
    else:per=persistence(None)
    result=sweep(rel,per)
    assert result['interturn_gap_crossed_by_retained_layers_above_floor'] is None
    if broken!='missing_step':assert result['status']=='unknown'


def spread(rel,per,context=None):
    from source_feedback_persistence import bilinear_diffusion_spread
    result=bilinear_diffusion_spread(rel,per,context)
    json.dumps(result,allow_nan=False)
    return result


def test_diffusion_spread_bounds_and_layer_merge_possibility():
    rel=relation([1,9,43]);rel['relative_old_minus_new_pixel_step_interval']=[1.3,1.35]
    result=spread(rel,persistence(transfer()))
    assert result['status']=='conditional_bilinear_spread_bound'
    half,floor=result['horizons']
    assert half['steps']==9 and half['sigma_upper_pixels']==pytest.approx(1.5)
    assert half['sigma_uniform_offset_reference_pixels']==pytest.approx(math.sqrt(9/6))
    assert floor['sigma_upper_pixels']==pytest.approx(math.sqrt(43)/2)
    assert result['adjacent_layer_merge_possible'] is True
    assert result['adjacent_layer_merge_guaranteed'] is None
    assert result['extra_diffusion_pass_excluded'] is None
    assert result['actual_trail_thickness_pixels'] is None


def test_declared_scale_above_reference_withholds_bound():
    rel=relation([9,43]);rel['relative_old_minus_new_pixel_step_interval']=[1.3,1.35]
    result=spread(rel,persistence(transfer()),{'feedback_diffusion_scale':2.0})
    assert result['status']=='unknown'
    ok=spread(rel,persistence(transfer()),{'feedback_diffusion_scale':1.0})
    assert ok['extra_diffusion_pass_excluded'] is True


def test_large_layer_separation_keeps_merge_false():
    rel=relation([9,43]);rel['relative_old_minus_new_pixel_step_interval']=[20.0,21.0]
    result=spread(rel,persistence(transfer()))
    assert result['adjacent_layer_merge_possible'] is False
