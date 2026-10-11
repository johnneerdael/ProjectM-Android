import json

from audio_series import audio_drawing_series

STATIC = '/analysis/visual_description/static_behaviour'
BASE = '/analysis/visual_description/elements/0'


def graph(nodes):
    return {'root': len(nodes) - 1, 'nodes': nodes}


def constant(value):
    return graph([{'op': 'constant', 'args': [], 'detail': {'value': value}}])


def gate():
    # above(mid, 1.5): on only for loud frames
    return graph([{'op': 'input', 'args': [], 'detail': {'name': 'mid'}},
                  {'op': 'constant', 'args': [], 'detail': {'value': 1.5}},
                  {'op': 'greater', 'args': [0, 1], 'detail': {}}])


def summary(alpha):
    channels = {'centre': {'r': constant(1.), 'g': constant(1.), 'b': constant(1.), 'a': alpha},
                'perimeter': {'r2': constant(1.), 'g2': constant(1.), 'b2': constant(1.), 'a2': alpha}}
    facts = [{'path': STATIC + '/context', 'value': {'viewport': [480, 270]}},
             {'path': BASE + '/id', 'value': 'shape_0'},
             {'path': BASE + '/geometry', 'value': {'summed_nominal_area_fraction_per_aspect_y': 1.}},
             {'path': BASE + '/material', 'value': {'texture': {'role': 'untextured_vertex_gradient'}, 'channel_expressions': channels}}]
    return {'facts': {'all': facts}}


def test_audio_gated_shape_gives_transitions_and_mean(tmp_path):
    frames = [{'bass': 1, 'mid': 2 if i % 2 else 1, 'treb': 1, 'bass_att': 1, 'mid_att': 1, 'treb_att': 1} for i in range(30)]
    path = tmp_path / 'bands.json'
    path.write_text(json.dumps({'policy': 'declared-reference-band-sequence-v1', 'fps': 30, 'frames': frames}))
    from audio_series import load_sequence
    result = audio_drawing_series(summary(gate()), load_sequence(path))
    assert abs(result['mean'] - .5 * 270 / 480) < 1e-6  # on in half the frames, full white over aspect-scaled area
    assert result['transitions_hz'] == 29.  # 29 toggles in one second
    assert result['components']['shape_0']['max'] > .5


def test_constant_drawing_is_not_audio_driven():
    assert audio_drawing_series(summary(constant(1.))) is None
