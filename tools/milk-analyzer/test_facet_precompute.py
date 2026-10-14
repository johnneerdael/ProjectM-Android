import base64, gzip, json


def test_summary_is_read_from_the_compressed_corpus_row_or_inline():
    from facet_precompute import _summary
    summary = {'facts': {'x': []}}
    row = {'summary_gzip_base64': base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode()}
    assert _summary(row) == summary
    assert _summary({'summary': summary}) == summary
    assert _summary({}) is None


def test_statistics_average_the_seeds_and_skip_missing_values(monkeypatch):
    import numpy as np
    import facet_precompute as F
    monkeypatch.setattr(F, 'per_load_random', lambda summary: True)
    monkeypatch.setattr(F, 'random_flash', lambda summary, audio: {'reads_rand_frame': False})
    monkeypatch.setattr(F, '_frames', lambda summary, audio, seed, w, h, n: (np.zeros((2, 2, 2, 3), np.uint8), []))
    # The cold load (seed None: a fresh engine's first draws, what a capture after app start shows) joins the seeds.
    values = iter([.2, .4, .6, .8])
    def measure(path):
        v = next(values)
        return {'mean_luminance': v, 'warm_cool': None if v == .4 else v}
    record = F.preset_statistics({}, {}, measure)
    assert record['seeds'] == [None, 1, 2, 3] and abs(record['statistics']['mean_luminance'] - .5) < 1e-9
    assert abs(record['statistics']['warm_cool'] - .5333333333) < 1e-9 and record['uses_engine_execution'] is False


def test_random_flash_finds_the_joint_tail_of_the_draw_that_floods_the_screen():
    # A singular term 1/|rand.x, rand.y| floods the screen only when both components are small (r118): the
    # probe must find both active components and integrate the tail cell, not just sample typical draws.
    import numpy as np
    import facet_precompute as F
    def evaluate(v):
        level = min(1., .3 + .002 / max(np.hypot(v[0], v[1]), 1e-6))
        return np.full((2, 2, 3), level, np.float32)
    risk = F.random_flash_risk(evaluate, [.6, .4, .5, .5], base_jump=0.)
    assert risk['active_components'] == [0, 1]
    assert risk['max_jump'] > .5 and 0 < risk['flash_probability_per_frame'] < .01
    assert risk['worst_vector'][:2] == [.001, .001]


def test_random_flash_is_absent_when_the_draw_only_moves_texture():
    import numpy as np
    import facet_precompute as F
    risk = F.random_flash_risk(lambda v: np.full((2, 2, 3), .4 + .01 * v[2], np.float32), [.5, .5, .5, .5], base_jump=.01)
    assert risk['active_components'] == [2] and risk['flash_probability_per_frame'] == 0 and risk['max_jump'] < .08


def test_rand_override_replaces_one_stage_draw():
    import numpy as np
    import prediction_illustration as P
    P._RAND_OVERRIDE[0] = {'warp': [.1, .2, .3, .4]}
    try:
        assert np.allclose(P._frame_rand(1., 30), [.1, .2, .3, .4])
        assert not np.allclose(P._frame_rand(1., 30, 'composite'), [.1, .2, .3, .4])
    finally:P._RAND_OVERRIDE[0] = None
    assert not np.allclose(P._frame_rand(1., 30), [.1, .2, .3, .4])


def test_warp_and_composite_draw_rand_frame_separately():
    # MilkdropShader::LoadVariables calls floatRand for each shader: the two draws of a frame are independent.
    import numpy as np
    import prediction_illustration as P
    assert not np.allclose(P._frame_rand(1., 30, 'warp'), P._frame_rand(1., 30, 'composite'))
    assert np.allclose(P._frame_rand(1., 30, 'composite'), P._frame_rand(1., 30, 'composite'))


def test_flash_probabilities_of_independent_stage_draws_combine():
    import facet_precompute as F
    assert abs(F._either(.1, .2) - .28) < 1e-12 and F._either(0., 0.) == 0.


def test_peak_global_brightness_change_uses_the_ruler_grey_from_frame_60():
    # No strobe needs headroom below the ruler's 0.08 jump: the largest frame-to-frame change of mean grey
    # (frames 60+, Rec.601 grey at 320x180 as the ruler measures) is recorded with the statistics.
    import numpy as np
    import facet_precompute as F
    frames = np.zeros((70, 18, 32, 3), np.uint8)
    frames[30] = 255                      # before frame 60: ignored
    frames[65:] = 20                      # a step of 20/255 at frame 65
    assert abs(F.peak_brightness_change(frames) - 20 / 255) < 1e-3


def test_random_texture_dependence_is_detected_from_the_exported_programs():
    # A shader that samples randNN shows a texture drawn at every load: flash statistics depend on the draw.
    import facet_precompute as F
    node = lambda name: {'op': 'sample', 'detail': {'canonical_texture': name}}
    assert F.random_texture_dependent({'facts': {'g': [{'path': '/p', 'value': {'nodes': [node('rand00')]}}]}})
    assert F.random_texture_dependent({'facts': {'g': [{'path': '/p', 'value': {'nodes': [node('rand03_smalltiled')]}}]}})
    assert not F.random_texture_dependent({'facts': {'g': [{'path': '/p', 'value': {'nodes': [node('noise_lq'), node('main')]}}]}})


def test_per_load_randomness_is_read_from_the_source_facts():
    # Seeds reach a prediction only through rand calls, rand_frame/rand_preset, the hue shader (random hue
    # offsets), noise or random textures and the legacy corner tint. Checked against two-seed runs on 117
    # checkpoint descriptions: no preset the runs found seed-dependent was missed.
    from facet_precompute import per_load_random
    plain = {'facts': {'motion': [{'path': '/x', 'value': {'nodes': [{'op': 'add'}]}}]}}
    assert per_load_random(plain) is False
    assert per_load_random({'facts': {'motion': [{'path': '/x', 'value': {'nodes': [{'op': 'rand'}]}}]}}) is True
    assert per_load_random({'facts': {'colour': [{'path': '/s', 'value': {'inputs': ['rand_frame']}}]}}) is True
    assert per_load_random({'facts': {'colour': [{'path': '/s', 'value': {'canonical_texture': 'noise_lq'}}]}}) is True
    assert per_load_random({'facts': {'colour': [{'path': '/a/legacy_response', 'value': {'tint_amount': .2}}]}}) is True
    assert per_load_random({'facts': {'colour': [{'path': '/a/legacy_response', 'value': {'tint_amount': 0.}}]}}) is False


def test_statistics_run_only_the_cold_load_without_per_load_randomness(monkeypatch):
    import numpy as np
    import facet_precompute as F
    monkeypatch.setattr(F, 'per_load_random', lambda summary: False)
    monkeypatch.setattr(F, 'random_flash', lambda summary, audio: {'reads_rand_frame': False})
    seeds = []
    monkeypatch.setattr(F, '_frames', lambda summary, audio, seed, w, h, n: (seeds.append(seed), (np.zeros((2, 2, 2, 3), np.uint8), []))[1])
    record = F.preset_statistics({}, {}, lambda path: {'mean_luminance': .3})
    assert seeds == [None] and record['seeds'] == [None] and record['depends_on_seed'] is False
