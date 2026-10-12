import feedback_equilibrium as E


def summary(facts):
    return {'facts': {'feedback': [{'path': path, 'value': value} for path, value in facts.items()]}}


def test_apply_transfer_interpolates_each_channel_linearly():
    transfer = {'levels': [0., .5, 1.], 'rgb': [[0., .1, .2], [.5, .4, .3], [1., .8, .6]]}
    assert E._apply_transfer(transfer, [.25, .5, 1.]) == [.25, .4, .6]


def test_additive_element_converges_to_alpha_colour_over_one_minus_gain():
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': .9, 'constant_offset_rgb': [0., 0., 0.]},
             '/analysis/visual_description/elements/0/geometry': {
                 'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': 1 / E.ASPECT_Y * .1},
             '/analysis/visual_description/elements/0/material': {
                 'centre_vertex_rgba': [.05, .05, .05, 1.], 'perimeter_vertex_rgba': [.05, .05, .05, 1.]},
             '/analysis/visual_description/elements/0/parameters': {'additive': 1}}
    result = E.equilibrium(summary(facts))
    # area .1, premultiplied .05 per frame: local value .05 / (1 - .9) = .5 over 10% of the screen
    assert abs(result['canvas_local_rgb'][0] - .05) < 1e-9
    assert abs(result['canvas_spread_rgb'][0] - .05) < 1e-9
    assert result['gain_rgb'] == [.9, .9, .9]


def test_alpha_over_element_converges_to_its_colour_when_opaque():
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': .98, 'constant_offset_rgb': [0., 0., 0.]},
             '/analysis/visual_description/elements/0/geometry': {
                 'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': 1 / E.ASPECT_Y},
             '/analysis/visual_description/elements/0/material': {
                 'centre_vertex_rgba': [.4, .2, .8, 1.], 'perimeter_vertex_rgba': [.4, .2, .8, 1.]}}
    result = E.equilibrium(summary(facts))
    assert [round(v, 6) for v in result['canvas_local_rgb']] == [.4, .2, .8]


def test_offset_alone_sets_the_background_level():
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': .5, 'constant_offset_rgb': [.1, 0., .05]}}
    result = E.equilibrium(summary(facts))
    assert [round(v, 6) for v in result['canvas_local_rgb']] == [.2, 0., .1]


def test_unknown_gain_is_reported_as_a_substitution():
    result = E.equilibrium(summary({}))
    assert result['gain_rgb'] == [.95, .95, .95]
    assert any('gain unknown' in note for note in result['substitutions'])


def test_legacy_transfers_apply_gamma_then_darken():
    facts = {'/analysis/visual_description/static_behaviour/prominence/components/0/final_transfer/legacy_response': {
        'native_control_ranges': {'gamma': [2., 2.], 'darken': [1., 1.]}}}
    shown, model = E._composite([.2, .4, .6], {k: v for k, v in facts.items()}, [])
    assert model == 'legacy' and [round(v, 6) for v in shown] == [.16, .64, 1.]


def test_dynamic_shape_colour_uses_the_time_average_of_its_formula():
    # r = .9 + .05*sin(time): the time-averaged colour (.9) replaces the neutral prior (.5).
    def program(*nodes):
        return {'root': 0, 'nodes': list(nodes)}
    red = program({'op': 'add', 'args': [1, 2], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .9}},
                  {'op': 'multiply', 'args': [3, 4], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .05}},
                  {'op': 'sin', 'args': [5], 'detail': {}}, {'op': 'input', 'args': [], 'detail': {'name': 'time'}})
    zero = program({'op': 'constant', 'args': [], 'detail': {'value': 0.}})
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': 0., 'constant_offset_rgb': [0., 0., 0.]},
             '/analysis/visual_description/elements/0/geometry': {
                 'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': 1 / E.ASPECT_Y},
             '/analysis/visual_description/elements/0/material': {
                 'centre_vertex_rgba': [None, 0., 0., 1.], 'perimeter_vertex_rgba': [None, 0., 0., 1.],
                 'channel_expressions': {'centre': {'r': red, 'g': zero, 'b': zero}, 'perimeter': {'r2': red, 'g2': zero, 'b2': zero}}}}
    result = E.equilibrium(summary(facts))
    assert abs(result['canvas_local_rgb'][0] - .9) < .02
    assert not any('colour unknown' in note for note in result['substitutions'])


def test_random_shape_colour_uses_the_expected_value_of_its_distribution():
    # r = rand(100)/100: projectm-eval draws uniformly on [0, 100], so the expected colour is .5;
    # g = .2 + rand(1)*.1 has expectation .25.
    red = {'root': 0, 'nodes': [{'op': 'eel_divide', 'args': [1, 3], 'detail': {}}, {'op': 'rand', 'args': [2], 'detail': {}},
                                {'op': 'constant', 'args': [], 'detail': {'value': 100.}}, {'op': 'constant', 'args': [], 'detail': {'value': 100.}}]}
    green = {'root': 0, 'nodes': [{'op': 'add', 'args': [1, 2], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .2}},
                                  {'op': 'multiply', 'args': [3, 5], 'detail': {}}, {'op': 'rand', 'args': [4], 'detail': {}},
                                  {'op': 'constant', 'args': [], 'detail': {'value': 1.}}, {'op': 'constant', 'args': [], 'detail': {'value': .1}}]}
    assert abs(E._formula_mean(red) - .5) < .02
    assert abs(E._formula_mean(green) - .25) < .01


def test_stage_transfer_supplies_render_inputs_and_stepped_frame_state(monkeypatch):
    # Shader programs inline per-frame graphs: time, frame and Q state must be bound, or the
    # transfer of about half of all custom shaders is lost.
    import prediction_illustration as P
    seen = []
    def fake(program, image, uv, time, fps, bands, controls=None, stage='warp', **_):
        seen.append(dict(controls));import numpy as np;return np.full(image.shape, .5, np.float32)
    monkeypatch.setattr(P, '_evaluate_stage', fake)
    q1 = {'root': 0, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'time'}}], 'plans': []}
    facts = {'/analysis/visual_description/stage_programs': {
        'stages': {'warp': {'status': 'exported', 'program': {'root': 0, 'nodes': []}}},
        'frame': {'status': 'exported', 'state': {}, 'outputs': {'q1': q1}, 'unsupported': {}}},
        '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    table = E.stage_transfer(facts, 'warp', levels=(0., 1.), times=(2.,))
    assert table['rgb'][0] == [.5, .5, .5]
    controls = seen[0]
    assert abs(controls['time'] - 2.) < 1e-6 and controls['frame'] == 59. and controls['fps'] == 30.
    assert abs(controls['q1'] - 2.) < 1e-6 and controls['aspecty'] > 1.


def test_stage_controls_stop_stepping_at_their_budget(monkeypatch):
    import time
    import prediction_illustration as P
    calls = []
    def slow_step(self, time_s, fps, bands, k):
        calls.append(k); time.sleep(.02); return {}
    monkeypatch.setattr(P._FrameStepper, 'step', slow_step)
    facts = {'/analysis/visual_description/stage_programs': {'frame': {'status': 'exported', 'state': {}, 'outputs': {'q1': {}}, 'unsupported': {}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    started = time.perf_counter()
    controls = E._stage_controls(facts, {'bass': 1.}, (2., 5., 8.), budget_seconds=.1)
    assert time.perf_counter() - started < 1. and len(calls) < 20
    assert set(controls) == {2., 5., 8.} and controls[8.]['time'] == 8.
