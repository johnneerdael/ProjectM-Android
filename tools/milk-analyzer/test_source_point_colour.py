import math

from source_point_colour import point_colour_distribution
from time_expression import evaluate_inputs, input_names


def graph(nodes, root=None):
    return {'root': len(nodes) - 1 if root is None else root, 'nodes': nodes}


def constant(value):
    return {'op': 'constant', 'args': [], 'detail': {'value': value}}


def name(value):
    return {'op': 'input', 'args': [], 'detail': {'name': value}}


def hashed(multiplier, scale):
    # ((sample*multiplier)%100)*scale
    return graph([name('sample'), constant(multiplier), {'op': 'multiply', 'args': [0, 1], 'detail': {}},
                  constant(100), {'op': 'remainder', 'args': [2, 3], 'detail': {}}, constant(scale),
                  {'op': 'multiply', 'args': [4, 5], 'detail': {}}])


def test_remainder_matches_projectm_eval_truncated_c_semantics():
    program = graph([name('a'), name('b'), {'op': 'remainder', 'args': [0, 1], 'detail': {}}])
    assert evaluate_inputs(program, {'a': 7.9, 'b': 3.2}) == 1.0
    assert evaluate_inputs(program, {'a': -7.9, 'b': 3.0}) == -1.0
    assert evaluate_inputs(program, {'a': 5.0, 'b': 0.4}) == 0.0  # truncated divisor 0
    assert input_names(program) == {'a', 'b'}


def test_hashed_sample_colour_spreads_over_the_grid():
    programs = {'r': hashed(5454, .01), 'g': hashed(9954, .01), 'b': graph([constant(1.)]), 'a': graph([constant(1.)])}
    record = point_colour_distribution(programs, 512, {})
    assert record['status'] == 'closed_form_point_colours'
    assert record['depends_on_sample'] and not record['depends_on_time']
    assert record['times_s'] == [0.]
    assert 0.4 < record['mean_rgb'][0] < 0.6 and record['mean_rgb'][2] == 1.0
    assert record['hue_family_shares']['blue'] > .5
    assert record['mean_saturation'] > .6


def test_native_modulo_wraps_values_above_one():
    programs = {'r': graph([constant(2.)]), 'g': graph([constant(0.)]), 'b': graph([constant(0.)]), 'a': graph([constant(1.)])}
    record = point_colour_distribution(programs, 4, {})
    assert math.isclose(record['mean_rgb'][0], 2 - 256 / 255)


def test_unresolved_inputs_block_the_distribution():
    programs = {'r': graph([name('state:x')]), 'g': graph([constant(0.)]), 'b': graph([constant(0.)]), 'a': graph([constant(1.)])}
    record = point_colour_distribution(programs, 16, {})
    assert record['status'] == 'unknown'
    assert record['unresolved_inputs'] == ['state:x']


def test_closed_form_positions_are_kept_with_bounds():
    programs = {c: graph([constant(1.)]) for c in 'rgba'}
    positions = {'x': graph([name('sample')]), 'y': graph([name('time'), constant(.1), {'op': 'multiply', 'args': [0, 1], 'detail': {}}])}
    record = point_colour_distribution(programs, 8, {}, positions=positions)
    assert record['positions_closed_form']
    assert record['position_bounds']['x'] == [0.0, 1.0]
    assert set(record['programs']) == set('rgbaxy')


def test_seeded_rand_in_stdlib_evaluator():
    import random
    import pytest
    program = graph([constant(3.9), {'op': 'rand', 'args': [0], 'detail': {}}])
    with pytest.raises(ValueError):
        evaluate_inputs(program, {})  # no rng: rand is not a closed-form value
    rng = random.Random(1)
    values = [evaluate_inputs(program, {}, rng) for _ in range(100)]
    assert 0 <= min(values) and max(values) < 3
