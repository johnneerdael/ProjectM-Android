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


def accumulator_recurrence():
    # advance = advance + bass*0.1 (per frame), init 0; point alpha = start-of-frame advance
    state_name = 'state:wave_0_per_frame:advance'
    update = graph([name(state_name), name('bass'), constant(.1), {'op': 'multiply', 'args': [1, 2], 'detail': {}},
                    {'op': 'add', 'args': [0, 3], 'detail': {}}])
    return {'state_input_prefix': 'state:wave_0_per_frame:', 'state': {'advance': {'initial': graph([constant(0.)]), 'update': update}}}


def test_wave_recurrence_trajectory_counts_updates_per_frame():
    from source_point_colour import recurrence_trajectory, initial_state, step_state
    recurrence = accumulator_recurrence()
    # frame k renders at (k+1)/30 and reads the state after k updates
    trajectory = recurrence_trajectory(recurrence, {'bass': 1.}, (1 / 30, 1., 2.))
    assert trajectory[1 / 30]['state:wave_0_per_frame:advance'] == 0.
    assert math.isclose(trajectory[1.]['state:wave_0_per_frame:advance'], 2.9)
    assert math.isclose(trajectory[2.]['state:wave_0_per_frame:advance'], 5.9)
    state = initial_state(recurrence, {'bass': 2.})
    assert math.isclose(step_state(recurrence, state, {'bass': 2.}, 1 / 30, 0)['advance'], .2)


def test_point_colours_resolve_wave_state_through_the_recurrence():
    recurrence = accumulator_recurrence()
    alpha = graph([name('state:wave_0_per_frame:advance'), constant(.01), {'op': 'multiply', 'args': [0, 1], 'detail': {}}])
    programs = {'r': graph([constant(1.)]), 'g': graph([constant(.5)]), 'b': graph([constant(.1)]), 'a': alpha}
    blocked = point_colour_distribution(programs, 16, {'bass': [0., 2.]})
    assert blocked['status'] == 'unknown' and blocked['unresolved_inputs'] == ['state:wave_0_per_frame:advance']
    record = point_colour_distribution(programs, 16, {'bass': [0., 2.]}, recurrence=recurrence)
    assert record['status'] == 'closed_form_point_colours' and record['frame_recurrence'] is recurrence
    assert record['mean_alpha'] > 0


def test_per_point_state_alternates_point_by_point():
    from source_point_colour import point_state_series
    prefix = 'state:wave_0_per_point:'
    # flip = (flip+1) * below(flip+1, 2): alternates 1, 0, 1, ... starting from 0
    plus = [name(prefix + 'flip'), constant(1.), {'op': 'add', 'args': [0, 1], 'detail': {}}, constant(2.),
            {'op': 'less', 'args': [2, 3], 'detail': {}}, {'op': 'multiply', 'args': [2, 4], 'detail': {}}]
    recurrence = {'state_input_prefix': prefix, 'state': {'flip': {'initial': graph([constant(0.)]), 'update': graph(plus)}}}
    series, carry = point_state_series(recurrence, {'flip': 0.}, lambda j: {} if j < 4 else None)
    assert [row['flip'] for row in series] == [0., 1., 0., 1.] and carry == {'flip': 0.}
    alpha = graph([name(prefix + 'flip')])
    programs = {'r': graph([constant(1.)]), 'g': graph([constant(1.)]), 'b': graph([constant(1.)]), 'a': alpha}
    record = point_colour_distribution(programs, 4, {}, point_recurrence=recurrence)
    assert record['status'] == 'closed_form_point_colours' and abs(record['mean_alpha'] - .5) < 1e-9


def test_positions_with_main_frame_state_are_kept_with_their_frame_inputs():
    from source_point_colour import _positions
    graph = lambda name: {'root': 2, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'sample'}},
                                               {'op': 'input', 'args': [], 'detail': {'name': name}},
                                               {'op': 'add', 'args': [0, 1], 'detail': {}}]}
    result = _positions({'x': graph('mtime'), 'y': graph('beat')}, 4, {}, (0.,))
    assert result == {'positions_closed_form': True, 'position_bounds': None, 'frame_inputs': ['beat', 'mtime']}
    assert _positions({'x': graph('state:wave_9_per_frame:t'), 'y': graph('beat')}, 4, {}, (0.,)) == {}


def test_stochastic_point_series_draws_rand_from_the_given_generator():
    import numpy as np
    from source_point_colour import point_state_series
    prefix = 'state:wave_0_per_point:'
    # walk = walk + rand(2): increments uniform on [0, 2], mean 1 per point
    update = graph([name(prefix + 'walk'), constant(2.), {'op': 'rand', 'args': [1], 'detail': {}},
                    {'op': 'add', 'args': [0, 2], 'detail': {}}])
    recurrence = {'state_input_prefix': prefix, 'state': {'walk': {'initial': graph([constant(0.)]), 'update': update}}, 'stochastic': True}
    series, carry = point_state_series(recurrence, {'walk': 0.}, lambda j: {} if j < 400 else None, rng=np.random.default_rng(5))
    steps = np.diff([row['walk'] for row in series])
    assert len(series) == 400 and steps.min() >= 0. and steps.max() <= 2. and abs(steps.mean() - 1.) < .1
    again, _ = point_state_series(recurrence, {'walk': 0.}, lambda j: {} if j < 400 else None, rng=np.random.default_rng(5))
    assert again == series


def test_vectorised_point_evaluation_matches_the_per_point_scalar_path():
    # Speed (analysis budget 1 s per preset): all points of a frame in one evaluation, identical values.
    import numpy as np
    from source_point_colour import _evaluate, _evaluate_points
    program = graph([name('sample'), name('value1'), {'op': 'multiply', 'args': [0, 1], 'detail': {}}, name('state:p:flip'),
                     {'op': 'add', 'args': [2, 3], 'detail': {}}, constant(3.), {'op': 'remainder', 'args': [4, 5], 'detail': {}},
                     {'op': 'sin', 'args': [6], 'detail': {}}])
    count = 7
    wave = (np.linspace(-1, 1, count), np.zeros(count))
    flips = [float(j % 2) for j in range(count)]
    base = {'time': .5}
    vector = _evaluate_points(program, base, count, wave, {'state:p:flip': np.array(flips)}, None)
    scalar = [_evaluate(program, {**base, 'sample': j / (count - 1), 'value1': float(wave[0][j]), 'value2': 0., 'state:p:flip': flips[j]})
              for j in range(count)]
    assert np.array_equal(vector, np.array(scalar))
