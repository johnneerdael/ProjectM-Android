"""Projected source curves enrich descriptions without raster/mood credit."""
import json
from types import SimpleNamespace
import pytest

from test_source_shape_state_export import read,report,PRESETS


def test_spiral_projection_exports_declared_aspect_clipping_and_actual_y_chain():
    value=report(read(PRESETS/'Zylot - Spiral.milk'))
    curve=value['curve_projection']['by_component']['wave_0']
    assert curve['nominal_radius_pixels_upper_bound']>=960
    assert curve['nominal_radius_pixels_upper_bound']<961
    assert curve['possible_coordinate_clipping'] is True
    assert curve['signed_final_clip_ndc_angular_orientation']==-1
    assert curve['raster_coverage_fraction'] is None
    assert curve['visible_motion_speed'] is None
    assert value['classification']['eligible_bands']==[]
    json.dumps(value,allow_nan=False)


@pytest.mark.parametrize('branch,engine',[
    ('custom','pinned'),('unknown','pinned'),('legacy','unmatched')])
def test_radial_sampler_export_requires_qualified_branch_and_engine(branch,engine):
    from source_static_behaviour import _affine_radial_feedback
    from engine_profiles import CORE_2334_ENGINE
    source={'parser_inputs':{'engine':CORE_2334_ENGINE if engine=='pinned' else {}}}
    value=_affine_radial_feedback(SimpleNamespace(source=source),
        {'native_warp_recipe':{'contribution':'consumed','shader_branch':branch}},
        {'viewport':[480,270]})
    assert value['status']=='unknown'
    assert value['visible_motion_speed'] is None
    assert value['unknown_reasons']


def test_spiral_exports_turn_spacing_and_reference_layer_relation_without_density_credit():
    value=report(read(PRESETS/'Zylot - Spiral.milk'),{'viewport':[480,270],'feedback_fps':30})
    relation=value['curve_feedback_relation']['by_component']['wave_0']
    assert relation['status']=='conditional_local_curve_feedback_relation'
    assert relation['reference_selection']['source_sample']==.5
    assert relation['reference_selection']['is_typical_or_observed'] is False
    assert [r['declared_steps'] for r in relation['nominal_n_step_relations']]==[1,4,16]
    assert relation['nominal_n_step_relations'][-1]['status']=='conditional_closed_form_radial_relation'
    low,high=relation['interturn_pitch_pixels_interval']
    assert low<15.07965 and high>15.07964
    assert relation['new_source_pixel_step_interval'][0]<=-.8<=relation['new_source_pixel_step_interval'][1]
    assert relation['actual_trail_thickness_pixels'] is None
    assert relation['final_visible_density'] is None
    assert value['classification']['eligible_bands']==[]
    assert 'source_curve_feedback_relation.py' in value['model_sources']
    json.dumps(value,allow_nan=False)


def test_radial_uv_export_requires_explicit_offsets_and_independent_texture_dimensions():
    source=read(PRESETS/'Zylot - Spiral.milk')
    unknown=report(source,{'viewport':[480,270],'feedback_fps':30})['radial_uv_envelope']
    assert unknown['status']=='unknown'
    declared=report(source,{'viewport':[480,270],'feedback_fps':30,
        'texel_offset_pixels':[0,0],'main_texture_size':[480,270]})['radial_uv_envelope']
    assert declared['status']=='conditional_radial_uv_envelope'
    assert declared['coordinate_wrap_possible'] is False
    assert declared['linear_filter_footprint_edge_crossing_possible'] is False
    assert declared['actual_wrap_sample_observed'] is False
    no_texture=report(source,{'viewport':[480,270],'feedback_fps':30,
        'texel_offset_pixels':[0,0]})['radial_uv_envelope']
    assert no_texture['coordinate_wrap_possible'] is False
    assert no_texture['linear_filter_footprint_edge_crossing_possible'] is None


def test_declared_viewport_changes_projection_without_adding_visibility():
    source=read(PRESETS/'Zylot - Spiral.milk')
    value=report(source,{'viewport':[480,270],'feedback_fps':30})
    curve=value['curve_projection']['by_component']['wave_0']
    assert 240<=curve['nominal_radius_pixels_upper_bound']<241
    assert curve['viewport']==[480,270]
    assert curve['native_numeric_certified'] is False


def test_spiral_exports_radial_feedback_with_opposing_sampler_and_feature_directions():
    value=report(read(PRESETS/'Zylot - Spiral.milk'))
    radial=value['affine_radial_feedback']
    assert radial['status']=='conditional_affine_radial_sampler'
    assert abs(radial['neutral_radius_crossover']-.048601627349853516)<1e-12
    assert radial['direction_regions'][-1]['feature_direction']=='outward'
    assert radial['direction_regions'][-1]['sampling_direction']=='inward'
    assert radial['visible_motion_speed'] is None
    assert value['classification']['eligible_bands']==[]
    assert 'source_affine_radial_feedback.py' in value['model_sources']
    json.dumps(value,allow_nan=False)
