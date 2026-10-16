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


def test_stage_controls_stop_stepping_at_a_deterministic_work_budget(monkeypatch):
    # The step count no longer depends on wall-clock time (machine load changed the probes of ~1% of presets):
    # each frame step charges the frame program's node count against a fixed work budget.
    import time
    import prediction_illustration as P
    node = {'op': 'constant', 'args': [], 'detail': {'value': 0.}}
    facts = {'/analysis/visual_description/stage_programs': {'frame': {'status': 'exported', 'state': {},
                                                                       'outputs': {'q1': {'root': 0, 'nodes': [node] * 10}}, 'unsupported': {}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    counts = []
    for delay in (0., .01):
        calls = []
        def step(self, time_s, fps, bands, k, calls=calls, delay=delay):
            calls.append(k); time.sleep(delay); return {}
        monkeypatch.setattr(P._FrameStepper, 'step', step)
        controls = E._stage_controls_uncached(facts, {'bass': 1.}, (2., 5., 8.), budget_units=70)
        counts.append(len(calls))
        assert set(controls) == {2., 5., 8.} and controls[8.]['time'] == 8.
    assert counts == [7, 7]


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


def test_shape_with_a_previous_frame_texture_adds_no_light():
    # r198 Wavering Flower: the textured disc (texture role previous_main, colour 0.9) copies the canvas. Its
    # parameters carry no 'textured' flag, so it was counted as a 0.9 fill over a third of the screen and the
    # steady state read white for a near-black preset.
    base = '/analysis/visual_description/elements/0'
    facts = {base + '/geometry': {'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': .5},
             base + '/material': {'centre_vertex_rgba': [.9, .9, .9, 1.], 'perimeter_vertex_rgba': [.9, .9, .9, 1.],
                                  'texture': {'role': 'previous_main'}},
             base + '/parameters': {}}
    notes = []
    assert E._shape_terms(facts, notes) == [] and any('copies the canvas' in n for n in notes)
    facts[base + '/material']['texture'] = {'role': 'untextured_vertex_gradient'}
    assert len(E._shape_terms(facts, [])) == 1


def test_shape_outline_adds_light_even_when_the_fill_is_textured():
    # r257 Cradle of Life class: a textured fill copies the canvas (no new light), but the engine draws the outline
    # (border_a > 0.0001) untextured in the border colour. Corners sit at rad*aspectY, rad in NDC, so the polygon has a
    # circumradius of rad*H/2 px; a 1-px line over its on-screen perimeter is the covered area.
    import math
    base = '/analysis/visual_description/elements/0'
    material = {'centre_vertex_rgba': [.9, .9, .9, 1.], 'perimeter_vertex_rgba': [.9, .9, .9, 1.], 'texture': {'role': 'previous_main'},
                'border_vertex_rgba': [1., .5, 0., 1.], 'border_draw_enabled': True, 'thick_outline': False}
    facts = {base + '/geometry': {'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': .2},
             base + '/material': material, base + '/parameters': {'sides': 100, 'rad': .5, 'x': .5, 'y': .5, 'instances': 1}}
    terms = E._shape_terms(facts, [])
    assert len(terms) == 1
    area, premultiplied, alpha, additive = terms[0]
    expected = 2 * 100 * (.5 * 270 / 2) * math.sin(math.pi / 100) / (480 * 270)
    assert abs(area - expected) < 1e-9 and premultiplied == [1., .5, 0.] and alpha == 1. and not additive
    material['thick_outline'] = True
    assert abs(E._shape_terms(facts, [])[0][0] - 2 * expected) < 1e-9
    # Entirely off screen (circumradius 2.2*H/2 = 297 px > 275 px, half the 480x270 diagonal): no light.
    facts[base + '/parameters']['rad'] = 2.2
    assert E._shape_terms(facts, []) == []
    # Disabled outline: none.
    facts[base + '/parameters']['rad'] = .5; material['border_draw_enabled'] = False
    assert E._shape_terms(facts, []) == []


def test_composite_colour_matrix_captures_channel_swaps(monkeypatch):
    # Grey flat probes cannot see a composite that swaps channels (ret = tex.zxy): a red canvas shows green.
    # Coloured flat probes give the response matrix that maps element colours to displayed colours.
    import numpy as np
    import prediction_illustration as P
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'composite': {'status': 'exported',
                 'program': {'root': 0, 'nodes': []}}}},
             '/analysis/visual_description/static_behaviour/context': {'viewport': [480, 270]}}
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, *a, **k: image[..., [2, 0, 1]].astype(np.float32))
    m = E.composite_colour_matrix(facts, level=.5)
    out = E.apply_colour_matrix(m, [1., 0., 0.])
    assert out[1] > .9 and out[0] < .1 and out[2] < .1


def test_warp_detail_gain_measures_how_a_stage_amplifies_fine_structure(monkeypatch):
    # Sparkly LSB Feedback class: ret += (ret - blur)*0.6; ret *= 0.9 keeps flat-field gain 0.9 (equilibrium black),
    # but fine structure grows ~1.44x per frame until it clips, so the canvas fills with bright spots. The gain is
    # std(output detail) / std(input detail) on a dim noise canvas: 1 for a copy, the factor for a scale, > 1 when
    # the stage sharpens.
    import numpy as np
    from scipy.ndimage import uniform_filter
    import prediction_illustration as P
    facts = {'/analysis/visual_description/stage_programs': {'stages': {'warp': {'status': 'exported', 'program': {'root': 0, 'nodes': []}}}}}
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, *a, **k: image.astype(np.float32))
    assert abs(E.stage_detail_gain(facts)['gain'] - 1.) < 1e-6
    monkeypatch.setattr(P, '_evaluate_stage', lambda program, image, *a, **k: (image * .5).astype(np.float32))
    assert abs(E.stage_detail_gain(facts)['gain'] - .5) < 1e-3
    def sharpen(program, image, *a, **k):
        blur = uniform_filter(image, (5, 5, 1), mode='wrap')
        return ((image + .6 * (image - blur)) * .9).astype(np.float32)
    monkeypatch.setattr(P, '_evaluate_stage', sharpen)
    assert E.stage_detail_gain(facts)['gain'] > 1.2
    assert E.stage_detail_gain({}) is None


def test_partial_motion_vector_grid_contributes_from_its_control_ranges():
    # A grid whose size is set per frame (mv_x, mv_y ranges) was status 'partial' and dropped from the closed form;
    # presets with active motion vectors were over-represented among the worst brightness errors.
    facts = {'/analysis/visual_description/static_behaviour/motion_vectors': {
        'status': 'partial', 'activation': 'possible',
        'control_ranges': {'mv_x': [3., 15.], 'mv_y': [3., 15.], 'mv_a': [.3, 1.], 'mv_r': [1., 1.], 'mv_g': [.91, .91], 'mv_b': [.71, .71]}}}
    terms = E._wave_terms(facts, [])
    assert len(terms) == 1
    area, premultiplied, alpha, additive = terms[0]
    assert area > 0 and abs(alpha - .65) < 1e-6 and premultiplied[0] > premultiplied[2]


def test_stage_controls_are_computed_once_per_preset_and_times(monkeypatch):
    # A recipe build probed the same per-frame program 16 times (4.8 of 6.4 s). Results are reused for the same
    # facts object and times, and recomputed for a different preset.
    import feedback_equilibrium as Q
    calls = []
    real = Q._stage_controls_uncached
    def counting(facts, bands, times, **k):
        calls.append(1); return real(facts, bands, times, **k)
    monkeypatch.setattr(Q, '_stage_controls_uncached', counting)
    Q._STAGE_CONTROL_CACHE.clear()
    a = {'/analysis/visual_description/static_behaviour/context': {}}
    b = {'/analysis/visual_description/static_behaviour/context': {}}
    bands = {'bass': 1.}
    first = Q._stage_controls(a, bands, (5.,)); again = Q._stage_controls(a, bands, (5.,))
    assert len(calls) == 1 and first == again and first is not again
    Q._stage_controls(b, bands, (5.,))
    assert len(calls) == 2


def test_trail_histogram_gives_the_canvas_level_distribution_of_decaying_paint():
    # For a nonlinear composite the display is the mean of T(level) over the canvas, not T(mean level). An element
    # painting area a per frame at level L leaves pixels at levels bg + (L - bg) g^k (age k), each covering a, until the
    # screen is covered; the rest stays at the background. Found with previews: 14.milk's composite maps every flat
    # level near its canvas mean to black, yet trails pass through the bright band (engine 0.51).
    hist = E._trail_histogram([(.1, [.8, .8, .8], .8, False)], [.9, .9, .9], [0., 0., 0.])
    assert abs(sum(share for share, _ in hist) - 1.) < 1e-9
    assert abs(hist[0][1][0] - 1.) < 1e-9 and abs(hist[1][1][0] - .9) < 1e-9 and abs(hist[2][1][0] - .81) < 1e-9
    assert len(hist) == 11 and abs(hist[-1][0]) < 1e-9  # ten ages fill the screen; no background share left
    sparse = E._trail_histogram([(.001, [.5, .5, .5], .5, False)], [.5, .5, .5], [.1, .1, .1])
    assert abs(sparse[-1][0] - (1 - sum(s for s, _ in sparse[:-1]))) < 1e-9 and sparse[-1][1] == [.1, .1, .1]


def test_equilibrium_reports_the_trail_display_level():
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': .9, 'constant_offset_rgb': [0., 0., 0.]},
             '/analysis/visual_description/elements/0/geometry': {
                 'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': 1 / E.ASPECT_Y * .1},
             '/analysis/visual_description/elements/0/material': {
                 'centre_vertex_rgba': [.5, .5, .5, 1.], 'perimeter_vertex_rgba': [.5, .5, .5, 1.]}}
    result = E.equilibrium(summary(facts))
    assert 0. < result['display_trail_luma'] <= 1. and len(result['display_trail_rgb']) == 3


def test_canvas_fixed_point_converges_to_an_alpha_over_colour_not_to_white():
    # Found with previews: with no decay (gain 1) the spread bound energy / (1 - g) clipped alpha-over presets to white
    # (Cathedral: equilibrium 1.0, preview canvas 0.84). Under complete mixing an alpha-over element with coverage c
    # converges to x* = c L / (1 - g (1 - c)), at most its colour L.
    facts = {'/analysis/visual_description/feedback_transfer': {'uniform_diagonal_gain': 1., 'constant_offset_rgb': [0., 0., 0.]},
             '/analysis/visual_description/elements/0/geometry': {
                 'policy': 'source-custom-shape-footprint-v1', 'summed_nominal_area_fraction_per_aspect_y': 1 / E.ASPECT_Y * .05},
             '/analysis/visual_description/elements/0/material': {
                 'centre_vertex_rgba': [.6, .6, .6, 1.], 'perimeter_vertex_rgba': [.6, .6, .6, 1.]}}
    result = E.equilibrium(summary(facts))
    assert result['canvas_spread_rgb'][0] == 1.  # the area-preserving additive bound saturates
    # Averaged over the ruler window (frames 60-299 from a black start) the canvas sits just under the colour.
    assert abs(result['canvas_fixed_rgb'][0] - .6) < 5e-3


def test_canvas_fixed_point_follows_a_nonlinear_warp_transfer(monkeypatch):
    # Iterating the measured warp transfer table from a black start finds its own fixed point: W(x) = 0.25 + 0.5 x
    # settles at 0.5 (a nonlinear table can hold a level that an affine fit would not).
    import numpy as np
    levels = list(np.linspace(0, 1, 11))
    table = {'levels': levels, 'rgb': [[.25 + .5 * v] * 3 for v in levels]}
    monkeypatch.setattr(E, 'stage_transfer', lambda facts, stage, *a, **k: table if stage == 'warp' else None)
    result = E.equilibrium(summary({}))
    assert abs(result['canvas_fixed_rgb'][0] - .5) < 1e-3
