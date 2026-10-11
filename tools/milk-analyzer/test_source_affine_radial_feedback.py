"""Conditional central radial sampling facts, without frame execution."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from shader_fields import Field
from engine_profiles import CORE_2331_ENGINE, CORE_2334_ENGINE


ROOT = Path(__file__).resolve().parents[2]


def constant(value):
    return Field('constant', detail={'value': value})


def model(a=.999514, b=.01, **overrides):
    controls = {name: constant(value) for name, value in
                {'zoomexp': 1., 'rot': 0., 'warp': 0., 'cx': .5, 'cy': .5,
                 'dx': 0., 'dy': 0., 'sx': 1., 'sy': 1.}.items()}
    rad = Field('input', detail={'name': 'rad', 'native_mesh_reset_input': True})
    controls['zoom'] = Field('add', (constant(a), Field('multiply', (constant(b), rad))))
    controls.update(overrides)
    return SimpleNamespace(mesh_controls=controls, values={}, unknowns=[],
                           source={'parser_inputs': {'engine': deepcopy(CORE_2334_ENGINE)}},
                           stages={'warp': {'kind': 'fixed_warp'}})


def report(analysis=None, context=None, **kwargs):
    import importlib.util
    assert importlib.util.find_spec('source_affine_radial_feedback'), 'affine radial sampler producer is missing'
    from source_affine_radial_feedback import affine_radial_feedback
    result = affine_radial_feedback(model() if analysis is None else analysis,
                                   {'viewport': [1920, 1080]} if context is None else context, **kwargs)
    json.dumps(result, allow_nan=False)
    return result


def exact(value):
    return Fraction(int(value['numerator']), int(value['denominator']))


def test_zylot_coefficients_crossover_and_inverse_are_exact_source_math():
    result = report(context={'viewport': [1920, 1080], 'source_radius_domain': [1., 1.]})
    assert result['status'] == 'conditional_affine_radial_sampler'
    coefficients = result['zoom_affine_coefficients_exact']
    assert exact(coefficients['a']) == Fraction(.999514)
    assert exact(coefficients['b']) == Fraction(.01)
    assert result['neutral_radius_crossover'] == pytest.approx(.0486)
    projection = result['fixed_feature_projection']
    expected = Fraction(.999514)/(1-Fraction(.01))
    assert projection['output_radius_interval'][0] <= expected <= projection['output_radius_interval'][1]
    assert float(expected) == pytest.approx(1.009610101010101)
    assert projection['maximum_absolute_displacement_radius_per_step'] >= float(expected-1)
    assert projection['maximum_absolute_displacement_pixels_per_second'] is None
    assert result['native_numeric_certified'] is False
    assert result['visible_motion_speed'] is None
    assert result['uses_equation_execution'] is False


@pytest.mark.parametrize('a,b', [(1.2, .05), (.8, -.05), (1., 0.), (.95, .2), (1.05, -.2)])
def test_positive_affine_parameters_sampling_derivative_and_inverse_enclosures(a, b):
    result = report(model(a, b), {'viewport': [1000, 1000], 'source_radius_domain': [.1, .7]})
    assert result['status'] == 'conditional_affine_radial_sampler'
    low, high = result['radial_sampling_derivative_range']
    projection = result['fixed_feature_projection']
    displacement = projection['output_minus_source_radius_interval']
    for radius in (0., .1, .5, 1., math.sqrt(2)):
        assert low <= Fraction(a)/(Fraction(a)+Fraction(b)*Fraction(radius))**2 <= high
    for radius in (.1, .25, .7):
        output = Fraction(a)*Fraction(radius)/(1-Fraction(b)*Fraction(radius))
        assert projection['output_radius_interval'][0] <= output <= projection['output_radius_interval'][1]
        assert displacement[0] <= output-Fraction(radius) <= displacement[1]


def test_sampling_direction_is_distinct_from_feature_motion_across_crossover():
    result = report(model(.9, .2), {'viewport': [1000, 1000]})
    assert result['neutral_radius_crossover'] == pytest.approx(.5)
    assert result['direction_regions'][0]['feature_direction'] == 'inward'
    assert result['direction_regions'][0]['sampling_direction'] == 'outward'
    assert result['direction_regions'][1]['feature_direction'] == 'outward'
    assert result['direction_regions'][1]['sampling_direction'] == 'inward'
    reverse = report(model(1.1, -.2), {'viewport': [1000, 1000]})
    assert [row['feature_direction'] for row in reverse['direction_regions']] == ['outward', 'inward']


def test_zero_slope_neutral_has_no_unique_crossover_and_zero_step_displacement():
    result = report(model(1., 0.), {'viewport': [1920, 1080], 'source_radius_domain': [.1, 1.]})
    assert result['neutral_radius_crossover'] is None
    assert result['all_radii_neutral'] is True
    assert result['fixed_feature_projection']['maximum_absolute_displacement_radius_per_step'] == 0


def test_declared_fps_only_scales_one_step_conditional_displacement():
    context = {'viewport': [1920, 1080], 'source_radius_domain': [1., 1.], 'feedback_fps': 30.}
    result = report(context=context)
    projection = result['fixed_feature_projection']
    assert projection['maximum_absolute_displacement_pixels_per_second'] >= 30*960*.009610101010101
    assert projection['fps_is_observed'] is False
    assert result['actual_feedback_lifetime'] is None


@pytest.mark.parametrize('a,b', [(0., .1), (-1., .1), (1., -1.), (1e40, 0.), (1e-50, 0.)])
def test_nonpositive_or_unusable_native_zoom_domains_abstain(a, b):
    result = report(model(a, b), {'viewport': [1000, 1000]})
    assert result['status'] == 'unknown'
    assert result['unknown_reasons']


@pytest.mark.parametrize('name,value', [('rot', .1), ('warp', .1), ('zoomexp', 1.1),
                                        ('sx', 2.), ('sy', .5), ('cx', .3), ('dy', .01)])
def test_noncentral_nonneutral_controls_are_not_radial_map(name, value):
    assert report(model(**{name: constant(value)}))['status'] == 'unknown'


@pytest.mark.parametrize('name', ['bass', 'time', 'x', 'y', 'state:per_pixel_:k', 'shared:reg00'])
def test_unknown_or_changing_inputs_cannot_acquire_const_affine_proof(name):
    zoom = Field('add', (constant(1.), Field('input', detail={'name': name, 'native_mesh_reset_input': True})))
    assert report(model(zoom=zoom))['status'] == 'unknown'
    assert report(model(rot=Field('input', detail={'name': name})))['status'] == 'unknown'


def test_name_only_rad_and_dynamic_cast_are_not_native_reset_affine_radius():
    rad = Field('input', detail={'name': 'rad'})
    assert report(model(zoom=Field('add', (constant(1.), rad))))['status'] == 'unknown'
    rad = Field('input', detail={'name': 'rad', 'native_mesh_reset_input': True})
    assert report(model(zoom=Field('narrow', (rad,), detail={'numeric_domain': 'shader-float32'})))['status'] == 'unknown'


def test_exact_affine_coefficients_do_not_erase_subnormal_product():
    rad = Field('input', detail={'name': 'rad', 'native_mesh_reset_input': True})
    slope = Field('multiply', (constant(1e-200), constant(1e-200)))
    result = report(model(zoom=Field('add', (constant(1.), Field('multiply', (rad, slope))))))
    assert exact(result['zoom_affine_coefficients_exact']['b']) == Fraction(1e-200)**2
    assert result['all_radii_neutral'] is False


def test_invalid_original_domain_and_effect_guards_survive_cancellation():
    singular = Field('divide', (constant(1.), constant(0.)))
    zero = Field('multiply', (constant(0.), singular))
    assert report(model(zoom=Field('add', (constant(1.), zero))))['status'] == 'unknown'
    assert report(model(_domain=Field('unknown', detail={'reason': 'invalid original domain'})))['status'] == 'unknown'
    assert report(model(zoom=Field('add', (constant(1.), Field('rand', (constant(1.),))))))['status'] == 'unknown'
    analysis = model()
    analysis.unknowns = [{'section': 'per_pixel_', 'reason': 'stateful EEL mem'}]
    assert report(analysis)['status'] == 'unknown'


def test_inverse_pole_and_outside_output_viewport_abstain():
    for radius in ([100., 100.], [50., 150.], [-1., 1.], [2., 2.]):
        result = report(context={'viewport': [1920, 1080], 'source_radius_domain': radius})
        assert result['status'] == 'unknown'
        assert result['fixed_feature_projection'] is None


@pytest.mark.parametrize('context', [{}, {'viewport': [0, 10]}, {'viewport': [1920, 1080], 'feedback_fps': 0.}])
def test_missing_or_invalid_declared_domain_is_not_defaulted(context):
    assert report(context=context)['status'] == 'unknown'


@pytest.mark.parametrize('viewport', [[1920, 1080], [1080, 1920], [1000, 1000]])
def test_radius_domain_uses_declared_native_aspects(viewport):
    result = report(context={'viewport': viewport})
    assert result['output_radius_domain'][1] >= math.hypot(*result['native_aspect_xy'])
    assert result['output_radius_domain'][1] == pytest.approx(math.hypot(1., min(viewport)/max(viewport)), rel=1e-6)


def test_actual_frozen_zylot_source34_parser_provenance_and_radial_basis():
    import effect_families as ef
    path = ROOT/'core/src/main/assets/presets/Zylot - Spiral.milk'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '02481b33b1399e5a186bc12f5f4230bb00d368edfd802857e4a2dac4831f5923'
    reader = ROOT/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        preset = Path(directory)/'radial.milk'
        preset.write_bytes(raw)
        source = json.loads(subprocess.check_output([str(reader), str(preset)]))
    source['preset_sha256'] = hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy'] = 'native-case-insensitive-v1'
    source['numbered_source'] = raw.decode()
    token = ef._CACHE.set({})
    try:
        analysis = ef._Analysis(source, 'gles300', None)
        analysis.main_equations()
        result = report(analysis, {'viewport': [3840, 2160], 'source_radius_domain': [1., 1.]})
    finally:
        ef._CACHE.reset(token)
    assert result['status'] == 'conditional_affine_radial_sampler'
    assert result['source_provenance']['preset_sha256'] == source['preset_sha256']
    assert result['source_provenance']['parser_inputs'] == source['parser_inputs']
    assert result['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] is True
    from source_native_warp import _f32
    coefficients = result['zoom_affine_coefficients_exact']
    assert exact(coefficients['a']) == Fraction(_f32(.999514))
    assert exact(coefficients['b']) == Fraction(.01)
    assert result['neutral_radius_crossover'] == float((1-Fraction(_f32(.999514)))/Fraction(.01))
    assert result['neutral_radius_crossover'] == pytest.approx(.0486, abs=2e-6)


def test_disconnected_mesh_returns_no_radial_sampler():
    result = report(context={'viewport': [1920, 1080]}, consumed=False)
    assert result['status'] == 'not_contributing'
    assert result['zoom_affine_coefficients_exact'] is None


def test_native_aspect_casts_dimensions_before_division():
    from source_native_warp import _f32
    result = report(context={'viewport': [16777217, 10000001]})
    assert result['native_aspect_xy'] == [1., _f32(_f32(10000001)/_f32(16777217))]


@pytest.mark.parametrize('context', [5, [], 'invalid', True])
def test_nonmapping_context_abstains(context):
    assert report(context=context)['status'] == 'unknown'


def test_affine_graph_budget_and_canceled_overflow_do_not_supply_bounds():
    zoom = constant(1.)
    for unused in range(70):
        zoom = Field('add', (zoom, constant(.01)))
    assert report(model(zoom=zoom))['status'] == 'unknown'
    rad = Field('input', detail={'name': 'rad', 'native_mesh_reset_input': True})
    overflow = Field('multiply', (constant(1.7e308), rad))
    canceled = Field('subtract', (overflow, overflow))
    assert report(model(zoom=Field('add', (constant(1.), canceled))))['status'] == 'unknown'


def test_zero_warp_does_not_hide_bad_original_scale_reciprocal():
    analysis = model()
    analysis.values = {'fWarpScale': 0.}
    result = report(analysis)
    assert result['status'] == 'unknown'
    assert 'scale reciprocal' in result['unknown_reasons'][0]


@pytest.mark.parametrize('engine', [None, {}, CORE_2331_ENGINE,
                                    {**CORE_2334_ENGINE, 'patches_sha256': '0'*64},
                                    {**CORE_2334_ENGINE, 'commit': '0'*40}])
def test_missing_or_stale_direct_api_source_identity_has_no_native_radius_evidence(engine):
    analysis = model()
    analysis.source['parser_inputs']['engine'] = engine
    result = report(analysis)
    assert result['status'] == 'unknown'
    assert result['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] is False
    assert result['zoom_affine_coefficients_exact'] is None
    assert 'source34 engine' in result['unknown_reasons'][0]


@pytest.mark.parametrize('stage', [None, {}, {'kind': 'custom_warp'}, {'kind': 'unknown'}])
def test_custom_unknown_or_missing_selected_warp_stage_cannot_claim_full_sampler(stage):
    analysis = model()
    analysis.stages = {'warp': stage}
    result = report(analysis)
    assert result['status'] == 'unknown'
    assert result['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] is False
    assert result['zoom_affine_coefficients_exact'] is None
    assert 'fixed/default warp' in result['unknown_reasons'][0]


def test_direct_api_with_no_source_or_stages_abstains_but_disconnected_result_survives():
    analysis = model()
    analysis.source = {}
    del analysis.stages
    result = report(analysis)
    assert result['status'] == 'unknown'
    assert result['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] is False
    disconnected = report(analysis, consumed=False)
    assert disconnected['status'] == 'not_contributing'
    assert disconnected['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] is False
