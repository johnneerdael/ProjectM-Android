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


def test_stage_transfer_reports_how_far_the_colour_moves_between_times(monkeypatch):
    # A composite such as ret *= 1+.2*sin(time*k) shifts its palette over time: the mean alone hides that.
    import numpy as np
    import prediction_illustration as P
    def fake(program, image, uv, time, fps, bands, controls=None, stage='warp', **_):
        out = np.empty(image.shape, np.float32); out[..., 0] = time / 10; out[..., 1] = .5; out[..., 2] = image[..., 2]
        return out
    monkeypatch.setattr(P, '_evaluate_stage', fake)
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': {'root': 0, 'nodes': []}}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    table = E.stage_transfer(facts, 'composite', levels=(0., 1.), times=(2., 5., 8.))
    assert [round(v, 4) for v in table['rgb_spread'][1]] == [.6, 0., 0.]
    assert abs(table['rgb'][1][0] - .5) < 1e-4


def test_stage_transfer_reports_the_share_of_undefined_outputs(monkeypatch):
    # r77: a composite dividing by never-written q values computes 0/0 everywhere; GLSL ES leaves the
    # displayed result undefined, so the share of non-finite outputs is reported rather than hidden as black.
    import numpy as np
    import prediction_illustration as P
    def fake(program, image, uv, time, fps, bands, controls=None, stage='warp', **_):
        out = np.full(image.shape, np.nan, np.float32); out[0] = .5
        return out
    monkeypatch.setattr(P, '_evaluate_stage', fake)
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': {'root': 0, 'nodes': []}}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    table = E.stage_transfer(facts, 'composite', levels=(0., 1.), times=(2.,), size=(8, 4))
    assert abs(table['nonfinite_share'] - .75) < 1e-9 and table['rgb'][0] == [.125, .125, .125]


def test_equilibrium_reports_composite_threshold_spread_and_undefined_share(monkeypatch):
    # r75/r77: a threshold composite, a time-varying palette and 0/0 output are descriptor inputs.
    table = {'levels': [0., .25, .5, .75, 1.], 'rgb': [[0, 0, 0], [0, 0, 0], [.2, .2, .2], [.8, .8, .8], [1, 1, 1]],
             'rgb_spread': [[0, 0, 0], [.1, .3, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], 'nonfinite_share': .25}
    monkeypatch.setattr(E, 'stage_transfer', lambda facts, stage, **_: table if stage == 'composite' else None)
    result = E.equilibrium(summary({}))
    assert abs(result['composite_threshold_level'] - .625) < 1e-9  # luma .2 at .5, .8 at .75: crosses .5 midway
    assert result['composite_spread_max'] == .3 and result['composite_nonfinite_share'] == .25
    monkeypatch.setattr(E, 'stage_transfer', lambda facts, stage, **_: None)
    result = E.equilibrium(summary({}))
    assert result['composite_threshold_level'] is None and result['composite_nonfinite_share'] == 0.


def test_channel_mixing_composite_is_evaluated_at_the_canvas_colour(monkeypatch):
    # r102: ret = lerp((1,1,0), 0, canvas.g). A green canvas (0,1,0) shows black; reading each output channel
    # from the grey ramp at that channel's own level gave red (output red at canvas red 0 is 1).
    import numpy as np
    import prediction_illustration as P
    def fake(program, image, uv, time, fps, bands, controls=None, stage='warp', **_):
        g = image[..., 1:2]
        return np.concatenate([1 - g, 1 - g, np.zeros_like(g)], axis=-1).astype(np.float32)
    monkeypatch.setattr(P, '_evaluate_stage', fake)
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': {'root': 0, 'nodes': []}}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    transfer = E.stage_transfer(facts, 'composite')
    shown, model = E._composite([0., 1., 0.], facts, [], transfer)
    assert model == 'composite_transfer' and max(shown) < 1e-6


def test_flat_transfer_resolves_faint_canvas_levels():
    # suksma kcigam spoo: ret = tex2D(main, uv)*50; ret = ret*(1-ret)*12. Only levels below 2% of full show:
    # 1/255 .. 4/255 display bright, 0.25 .. 1 display black. A grid of quarters alone reports all black.
    from feedback_equilibrium import stage_transfer
    nodes = [{'op': 'multiply', 'dtype': 'float3', 'args': [1, 7], 'detail': {}},
             {'op': 'multiply', 'dtype': 'float3', 'args': [2, 5], 'detail': {}},
             {'op': 'multiply', 'dtype': 'float3', 'args': [3, 8], 'detail': {}},
             {'op': 'member', 'dtype': 'float3', 'args': [4], 'detail': {'field': 'xyz', 'swizzle': True}},
             {'op': 'sample', 'dtype': 'float4', 'args': [9], 'detail': {'sampler': 'sampler_main', 'canonical_texture': 'main', 'site_index': 0, 'intrinsic': 'tex2D'}},
             {'op': 'subtract', 'dtype': 'float3', 'args': [6, 2], 'detail': {}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 1.}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 12.}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 50.}},
             {'op': 'input', 'dtype': 'float2', 'args': [], 'detail': {'name': '_uv'}}]
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported', 'program': {'root': 0, 'nodes': nodes, 'plans': []}}}}}
    table = stage_transfer(facts, 'composite')
    bright = [level for level, rgb in zip(table['levels'], table['rgb']) if rgb[0] > .9]
    assert bright and max(bright) < .02 and table['rgb'][-1][0] == 0.


def test_detail_response_reports_colour_a_composite_creates_from_structure(monkeypatch):
    # r165 Sunflower Passion: the composite colours detail (greens and magentas from structure) while a flat
    # canvas maps to near black, so flat-colour probes leave the palette unresolved. A grey multi-scale
    # texture through the composite shows the colour the shader itself creates.
    import numpy as np
    import prediction_illustration as P
    def facts():
        return {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported',
                    'program': {'root': 0, 'nodes': []}}}},
                '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    def detail_green(program, image, uv, time, fps, bands, controls=None, stage='composite', **_):
        g = np.clip(np.abs(image[..., 1] - .5) * 4, 0, 1)
        return np.stack([np.zeros_like(g), g, np.zeros_like(g)], -1).astype(np.float32)
    monkeypatch.setattr(P, '_evaluate_stage', detail_green)
    r = E.stage_detail_response(facts())
    assert r['hue_shares'] and next(iter(r['hue_shares'])) == 'green' and r['coloured_share'] > .5
    assert r['mean_saturation'] > .5 and r['mean_rgb'][1] > r['mean_rgb'][0]
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, *a, **k: image.astype(np.float32))
    grey = E.stage_detail_response(facts())
    assert grey['coloured_share'] == 0. and grey['hue_shares'] == {} and abs(grey['mean_luma'] - .5) < .05


def test_composite_load_spread_measures_brightness_that_depends_on_the_random_hue_tint(monkeypatch):
    # r181 Atomic Pulsagons: the composite multiplies by pow(hue_shader, 4) and dot(ret, hue_shader): the random
    # per-load corner tint changes displayed brightness several-fold. A composite that ignores it has no spread.
    import numpy as np
    import prediction_illustration as P
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported',
                 'program': {'root': 0, 'nodes': []}}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, uv, time, fps, bands, diffuse=None, **k: (image * diffuse[..., :3] ** 4).astype(np.float32))
    spread = E.composite_load_spread(facts)
    assert spread['luma_range'][1] > 1.5 * spread['luma_range'][0] and spread['draws'] >= 6
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, *a, **k: image.astype(np.float32))
    flat = E.composite_load_spread(facts)
    assert flat['luma_range'][1] - flat['luma_range'][0] < 1e-6
