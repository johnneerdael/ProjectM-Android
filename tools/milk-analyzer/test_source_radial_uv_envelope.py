"""Conditional coordinate and GL_LINEAR footprint envelopes; no images."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

import pytest

from engine_profiles import CORE_2331_ENGINE
from test_source_affine_radial_feedback import model, report


ROOT = Path(__file__).resolve().parents[2]


def envelope(recipe=None, context=None):
    assert importlib.util.find_spec('source_radial_uv_envelope'), 'radial UV envelope producer is missing'
    from source_radial_uv_envelope import radial_uv_envelope
    result = radial_uv_envelope(report() if recipe is None else recipe,
                               {'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.]} if context is None else context)
    json.dumps(result, allow_nan=False)
    return result


def exact(value):
    return Fraction(int(value['numerator']), int(value['denominator']))


def test_zero_offset_zylot_coordinates_are_inside_without_inventing_texture_size():
    result = envelope()
    assert result['status'] == 'conditional_radial_uv_envelope'
    assert result['coordinate_wrap_possible'] is False
    assert result['coordinate_range_within_unit_window_xy'] == [True, True]
    assert result['linear_filter_footprint_edge_crossing_possible'] is None
    assert result['texture_size'] is None
    assert result['native_numeric_certified'] is False
    assert result['wrap_vs_clamp_visual_difference'] is None
    assert result['uses_rendered_images'] is False
    assert result['uses_equation_execution'] is False


@pytest.mark.parametrize('a,b,viewport', [(1.2, .1, [1920, 1080]), (.99, .02, [1080, 1920]),
                                        (1., 0., [1000, 1000]), (1., -.2, [1920, 1080])])
def test_analytic_envelope_contains_independent_nominal_rectangle_control_positions(a, b, viewport):
    recipe = report(model(a, b), {'viewport': viewport})
    result = envelope(recipe, {'viewport': viewport, 'texel_offset_pixels': [.5, -.25]})
    assert result['status'] == 'conditional_radial_uv_envelope'
    ax, ay = recipe['native_aspect_xy']
    for x in (-1., -.2, 0., .7, 1.):
        for y in (-1., -.4, 0., .8, 1.):
            radius = (ax*ax*x*x+ay*ay*y*y)**.5
            zoom = a+b*radius
            uv = [.5+.5*x/zoom+.5/viewport[0], .5+.5*y/zoom-.25/viewport[1]]
            for lane, coordinate in enumerate(uv):
                low, high = result['nominal_uv_rectangle'][lane]
                assert low-1e-15 <= coordinate <= high+1e-15
    expected_basis = 'axis_boundary_extrema' if b >= 0 else 'conservative_corner_radius_denominator'
    assert result['envelope_basis'] == expected_basis


def test_positive_slope_axis_extrema_use_axis_radius_and_exact_coefficients():
    recipe = report(model(.999514, .01), {'viewport': [1920, 1080]})
    result = envelope(recipe)
    a = exact(recipe['zoom_affine_coefficients_exact']['a'])
    b = exact(recipe['zoom_affine_coefficients_exact']['b'])
    for aspect, interval in zip(recipe['native_aspect_xy'], result['nominal_uv_rectangle']):
        half_span = Fraction(1, 2)/(a+b*Fraction(aspect))
        assert interval[0] <= Fraction(1, 2)-half_span <= interval[1]
        assert interval[0] <= Fraction(1, 2)+half_span <= interval[1]
    assert result['nominal_uv_rectangle'][0][0] > result['nominal_uv_rectangle'][1][0]


def test_negative_slope_has_safe_corner_radius_envelope():
    recipe = report(model(1.1, -.1), {'viewport': [1920, 1080]})
    result = envelope(recipe)
    a = exact(recipe['zoom_affine_coefficients_exact']['a'])
    b = exact(recipe['zoom_affine_coefficients_exact']['b'])
    radius = Fraction(recipe['output_radius_domain'][1])
    width = Fraction(1, 2)/(a+b*radius)
    for interval in result['nominal_uv_rectangle']:
        assert interval[0] <= Fraction(1, 2)-width
        assert interval[1] >= Fraction(1, 2)+width
    assert result['coordinate_wrap_possible'] is True


def test_zero_offset_identity_is_coordinate_safe_but_linear_footprint_can_cross_edges():
    recipe = report(model(1., 0.))
    result = envelope(recipe, {'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.], 'texture_size': [480, 270]})
    assert result['nominal_uv_rectangle'] == [[0., 1.], [0., 1.]]
    assert result['coordinate_wrap_possible'] is False
    assert result['linear_filter_footprint_edge_crossing_possible'] is True
    assert result['linear_filter_footprint_within_texture_window_xy'] == [False, False]


def test_texture_dimensions_are_separate_from_viewport_and_change_footprint_condition():
    recipe = report(context={'viewport': [480, 270]})
    context = {'viewport': [480, 270], 'texel_offset_pixels': [0., 0.], 'texture_size': [480, 270]}
    result = envelope(recipe, context)
    assert result['linear_filter_footprint_edge_crossing_possible'] is False
    context['texture_size'] = [16, 16]
    result = envelope(recipe, context)
    assert result['coordinate_wrap_possible'] is False
    assert result['linear_filter_footprint_edge_crossing_possible'] is True


def test_explicit_offset_shift_can_reach_outside_even_with_positive_zoom():
    recipe = report(context={'viewport': [480, 270]})
    result = envelope(recipe, {'viewport': [480, 270], 'texel_offset_pixels': [4., 0.]})
    assert result['coordinate_wrap_possible'] is True
    assert result['coordinate_range_within_unit_window_xy'] == [False, True]


@pytest.mark.parametrize('offset', [None, [], [0.], [0., 0., 0.], [float('inf'), 0.], [True, 0.], ['0', 0.]])
def test_offset_must_be_an_explicit_finite_pixel_pair(offset):
    assert envelope(context={'viewport': [1920, 1080], 'texel_offset_pixels': offset})['status'] == 'unknown'


def test_offset_missing_is_not_silently_zero_or_half_a_texel():
    assert envelope(context={'viewport': [1920, 1080]})['status'] == 'unknown'


@pytest.mark.parametrize('context', [None, {}, 5, [], True, {'viewport': [1080, 1920], 'texel_offset_pixels': [0., 0.]},
                                    {'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.], 'texture_size': [0, 270]},
                                    {'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.], 'texture_size': [480., 270]}])
def test_bad_or_mismatched_context_abstains(context):
    from source_radial_uv_envelope import radial_uv_envelope
    assert radial_uv_envelope(report(), context)['status'] == 'unknown'


@pytest.mark.parametrize('change', ['status', 'policy', 'engine', 'radius_evidence', 'aspects', 'radius_domain', 'coefficients', 'a', 'singular'])
def test_unqualified_mismatched_or_singular_source_record_abstains(change):
    recipe = deepcopy(report())
    if change == 'status': recipe['status'] = 'unknown'
    elif change == 'policy': recipe['policy'] = 'arbitrary-custom-shader'
    elif change == 'engine': recipe['source_provenance']['parser_inputs']['engine'] = CORE_2331_ENGINE
    elif change == 'radius_evidence': recipe['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] = False
    elif change == 'aspects': recipe['native_aspect_xy'] = [1., 1.]
    elif change == 'radius_domain': recipe['output_radius_domain'] = [0., 10.]
    elif change == 'coefficients': recipe['zoom_affine_coefficients_exact'] = None
    elif change == 'a': recipe['zoom_affine_coefficients_exact']['a'] = {'numerator': '0', 'denominator': '1'}
    elif change == 'singular': recipe['zoom_affine_coefficients_exact']['b'] = {'numerator': '-1', 'denominator': '1'}
    result = envelope(recipe)
    assert result['status'] == 'unknown'
    assert result['nominal_uv_rectangle'] is None


@pytest.mark.parametrize('recipe', [None, 5, [], True])
def test_malformed_record_abstains(recipe):
    from source_radial_uv_envelope import radial_uv_envelope
    result = radial_uv_envelope(recipe, {'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.]})
    assert result['status'] == 'unknown'


def test_actual_frozen_source34_spiral_zero_offset_at_480x270():
    import effect_families as ef
    raw = (ROOT/'core/src/main/assets/presets/Zylot - Spiral.milk').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == '02481b33b1399e5a186bc12f5f4230bb00d368edfd802857e4a2dac4831f5923'
    reader = ROOT/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'radial.milk'
        path.write_bytes(raw)
        source = json.loads(subprocess.check_output([str(reader), str(path)]))
    source['preset_sha256'] = digest
    source['parser_inputs']['setting_lookup_policy'] = 'native-case-insensitive-v1'
    token = ef._CACHE.set({})
    try:
        analysis = ef._Analysis(source, 'gles300', None)
        analysis.main_equations()
        recipe = report(analysis, {'viewport': [480, 270]})
    finally:
        ef._CACHE.reset(token)
    result = envelope(recipe, {'viewport': [480, 270], 'texel_offset_pixels': [0., 0.], 'texture_size': [480, 270]})
    assert result['status'] == 'conditional_radial_uv_envelope'
    assert result['source_provenance']['preset_sha256'] == digest
    assert result['coordinate_wrap_possible'] is False
    assert result['linear_filter_footprint_edge_crossing_possible'] is False
    assert result['finite_vertex_interpolation_preserves_convex_envelope_conditionally'] is True


def test_custom_branch_and_noncentral_controls_cannot_supply_qualified_input():
    analysis = model()
    analysis.stages['warp']['kind'] = 'custom_warp'
    assert envelope(report(analysis))['status'] == 'unknown'
    from test_source_affine_radial_feedback import constant
    assert envelope(report(model(rot=constant(.1))))['status'] == 'unknown'


def test_unknown_context_assumptions_are_not_silently_ignored():
    result = envelope(context={'viewport': [1920, 1080], 'texel_offset_pixels': [0., 0.], 'rot': .1})
    assert result['status'] == 'unknown'
