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


def composite_program(flip_u):
    # ret = lerp(tex2D(main, uv).xyz, tex2D(main, float2(1-uv.x, uv.y) or uv).xyz, .5)
    nodes = [{'op': 'lerp', 'dtype': 'float3', 'args': [1, 4, 9], 'detail': {}},
             {'op': 'member', 'dtype': 'float3', 'args': [2], 'detail': {'field': 'xyz', 'swizzle': True}},
             {'op': 'sample', 'dtype': 'float4', 'args': [3], 'detail': {'sampler': 'sampler_main', 'canonical_texture': 'main', 'site_index': 0, 'intrinsic': 'tex2D'}},
             {'op': 'input', 'dtype': 'float2', 'args': [], 'detail': {'name': '_uv'}},
             {'op': 'member', 'dtype': 'float3', 'args': [5], 'detail': {'field': 'xyz', 'swizzle': True}},
             {'op': 'sample', 'dtype': 'float4', 'args': [6 if flip_u else 3], 'detail': {'sampler': 'sampler_main', 'canonical_texture': 'main', 'site_index': 1, 'intrinsic': 'tex2D'}},
             {'op': 'components', 'dtype': 'float2', 'args': [7, 11], 'detail': {}},
             {'op': 'subtract', 'dtype': 'float', 'args': [8, 10], 'detail': {}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 1.}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': .5}},
             {'op': 'member', 'dtype': 'float', 'args': [3], 'detail': {'field': 'x', 'swizzle': True}},
             {'op': 'member', 'dtype': 'float', 'args': [3], 'detail': {'field': 'y', 'swizzle': True}}]
    return {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': {'root': 0, 'nodes': nodes, 'plans': []}}}}}


def test_composite_shader_blending_a_flipped_sample_is_a_mirror():
    # suksma kcigam spoo: lerp(tex2D(main, uv), tex2D(main, (uv-.5)*float2(-1,1)+.5), .5) mirrors left-right.
    record = mirror_operators(composite_program(flip_u=True))
    (row,) = record['operators']
    assert row['operator'] == 'composite_shader_mirror' and row['flip'] == 'left-right'
    assert row['symmetry_score'] > .9 and record['fold'] == 2
    assert 'mirrored copy' in sentence(record)


def test_composite_shader_without_a_flip_has_no_mirror():
    record = mirror_operators(composite_program(flip_u=False))
    assert record['operators'] == [] and record['fold'] == 1


def test_blur_driven_chance_correlation_is_not_a_mirror():
    # A composite that only reads a heavily blurred image: few independent samples correlate with the flip
    # by chance, but no more than with shifted copies of themselves (goody nematodes, suksma n19).
    import numpy as np
    from mirror_symmetry import _correlation
    rng = np.random.default_rng(3)
    field = np.repeat(np.repeat(rng.random((3, 4)), 12, axis=0), 16, axis=1)
    flip = _correlation(field, field[:, ::-1]); shifted = abs(_correlation(field, np.roll(field, 16, axis=1)))
    assert flip - shifted < .4
