import math

from mirror_symmetry import mirror_operators, sentence

STATIC = '/analysis/visual_description/static_behaviour'


def mesh(sx=1., sy=1.):
    def row(value):
        return {'status': 'described', 'uniform_across_mesh': True, 'value_range': [value, value]}
    return {STATIC + '/mesh_field': {'controls': {'sx': row(sx), 'sy': row(sy), 'cx': row(.5), 'cy': row(.5)}}}


def test_negative_stretch_is_a_feedback_mirror_weighted_by_decay():
    facts = {**mesh(sy=-1.), STATIC + '/feedback_persistence': {'decay_gain': .9}}
    record = mirror_operators(facts)
    (row,) = record['operators']
    assert row['flip'] == 'top-bottom' and row['control'] == 'sy'
    assert math.isclose(row['symmetry_score'], 2 * .9 / (1 + .81))
    assert record['fold'] == 2


def test_mirrored_echo_and_feedback_mirror_give_four_fold():
    facts = {**mesh(sy=-1.), STATIC + '/feedback_persistence': {'decay_gain': .999},
             '/x/legacy_response': {'echo_selection': 'active or possible native echo',
                                    'native_control_ranges': {'echo_alpha': [.5, .5], 'echo_orient': [1, 1], 'echo_zoom': [1., 1.]}}}
    record = mirror_operators(facts)
    assert record['fold'] == 4
    assert record['flip_directions'] == ['left-right', 'top-bottom']
    assert 'four-fold' in sentence(record)


def test_positive_stretch_and_unmirrored_echo_have_no_mirror():
    facts = {**mesh(sx=1.2), '/x/legacy_response': {'echo_selection': 'active or possible native echo',
                                                    'native_control_ranges': {'echo_alpha': [.5, .5], 'echo_orient': [0, 0]}}}
    record = mirror_operators(facts)
    assert record['operators'] == [] and record['symmetry_score'] == 0. and sentence(record) == ''
