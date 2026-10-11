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
