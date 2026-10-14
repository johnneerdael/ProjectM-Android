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
    monkeypatch.setattr(F, '_frames', lambda summary, audio, seed, w, h, n: (np.zeros((2, 2, 2, 3), np.uint8), []))
    values = iter([.2, .4, .6])
    def measure(path):
        v = next(values)
        return {'mean_luminance': v, 'warm_cool': None if v == .4 else v}
    record = F.preset_statistics({}, {}, measure)
    assert record['seeds'] == [1, 2, 3] and abs(record['statistics']['mean_luminance'] - .4) < 1e-9
    assert abs(record['statistics']['warm_cool'] - .4) < 1e-9 and record['uses_engine_execution'] is False
