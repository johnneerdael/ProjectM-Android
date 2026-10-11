import math
from types import SimpleNamespace

from effect_families import _constant
from source_borders import border_operators

VALUES = {'ob_size': .005, 'ob_r': 1., 'ob_g': .5, 'ob_b': .5, 'ob_a': 1., 'ib_size': .5, 'ib_r': 0., 'ib_g': 0.,
          'ib_b': 0., 'ib_a': .02, 'darken_center': 1.}
CONTEXT = {'viewport': [480, 270], 'feedback_fps': 30.}


def analysis(**changes):
    return SimpleNamespace(main={k: _constant(v) for k, v in {**VALUES, **changes}.items()}, input_scenario=None)


def test_inner_black_border_band_gain_and_orbit():
    record = border_operators(analysis(), CONTEXT, {'decay_gain': .999})
    assert record['status'] == 'described'
    outer, inner = record['borders']
    assert math.isclose(inner['screen_area_fraction'], .995 ** 2 - .495 ** 2, rel_tol=1e-6)
    assert math.isclose(inner['combined_gain_with_decay'], .999 * .98, rel_tol=1e-6)
    assert inner['steady_level_rgb'] == [0., 0., 0.]
    # Round-to-nearest blending leaves a floor where 2% of the level is below half a step.
    assert 0 < inner['floor_level_from_full'] <= 25
    assert 20 < inner['steps_to_half_from_full'] < 50
    assert outer['retained_gain_per_frame'] == 0.
    assert record['darken_centre']['active']


def test_transparent_borders_are_inactive():
    record = border_operators(analysis(ob_a=0., ib_a=0., darken_center=0.), CONTEXT, {'decay_gain': .98})
    assert [row['active'] for row in record['borders']] == [False, False]
    assert record['darken_centre'] is None


def test_inverted_inner_radius_has_no_area_claim():
    record = border_operators(analysis(ib_size=1.5), CONTEXT, {'decay_gain': .98})
    inner = record['borders'][1]
    assert inner['inverted_inner_radius'] is True and inner['screen_area_fraction'] is None
