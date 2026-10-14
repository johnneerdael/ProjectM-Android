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
    monkeypatch.setattr(F, 'depends_on_seed', lambda summary, audio: True)
    monkeypatch.setattr(F, 'random_flash', lambda summary, audio: {'reads_rand_frame': False})
    monkeypatch.setattr(F, '_frames', lambda summary, audio, seed, w, h, n: (np.zeros((2, 2, 2, 3), np.uint8), []))
    values = iter([.2, .4, .6])
    def measure(path):
        v = next(values)
        return {'mean_luminance': v, 'warm_cool': None if v == .4 else v}
    record = F.preset_statistics({}, {}, measure)
    assert record['seeds'] == [1, 2, 3] and abs(record['statistics']['mean_luminance'] - .4) < 1e-9
    assert abs(record['statistics']['warm_cool'] - .4) < 1e-9 and record['uses_engine_execution'] is False


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
