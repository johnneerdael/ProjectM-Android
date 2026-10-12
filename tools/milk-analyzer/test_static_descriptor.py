from static_descriptor import descriptor


def test_descriptor_collapses_indices_and_one_hots_short_strings():
    summary = {'facts': {
        'identity': [{'path': '/preset', 'value': {'name': 'x'}}],
        'motion': [{'path': '/analysis/visual_description/elements/0/geometry', 'value': {'radius': .2, 'kind': 'fan', 'flag': True}},
                   {'path': '/analysis/visual_description/elements/3/geometry', 'value': {'radius': .6, 'kind': 'fan'}}]}}
    columns = descriptor(summary)
    key = 'motion:/analysis/visual_description/elements/*/geometry/radius'
    assert columns[key + '#max'] == .6 and abs(columns[key + '#mean'] - .4) < 1e-9 and columns[key + '#count'] == 2
    assert columns['motion:/analysis/visual_description/elements/*/geometry/kind=fan#count'] == 2
    assert columns['motion:/analysis/visual_description/elements/*/geometry/flag#max'] == 1.
    assert not any(k.startswith('identity') for k in columns)


def test_control_series_columns_summarise_the_authored_per_frame_controls():
    # zoom = 1 + .02*sin(time): mean |zoom-1| ~ .0127 over 10 s; rot is constant .01; no other controls.
    from static_descriptor import _control_series_columns
    def g(*nodes):
        return {'root': 0, 'nodes': list(nodes), 'plans': []}
    zoom = g({'op': 'add', 'args': [1, 2], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 1.}},
             {'op': 'multiply', 'args': [3, 4], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .02}},
             {'op': 'sin', 'args': [5], 'detail': {}}, {'op': 'input', 'args': [], 'detail': {'name': 'time'}})
    rot = g({'op': 'constant', 'args': [], 'detail': {'value': .01}})
    frame = {'status': 'exported', 'state': {}, 'outputs': {'zoom': zoom, 'rot': rot}, 'unsupported': {}}
    summary = {'facts': {'construction': [{'path': '/analysis/visual_description/stage_programs', 'value': {'frame': frame}},
                                          {'path': '/analysis/visual_description/static_behaviour/context', 'value': {'viewport': [480, 270]}}]}}
    columns = _control_series_columns(summary)
    assert abs(columns['series:zoom#mean_abs_deviation_from_neutral'] - .0127) < .002
    assert columns['series:rot#mean'] == .01 and columns['series:rot#mean_abs_frame_change'] == 0.
    assert columns['series:zoom#mean_abs_frame_change'] > 0 and columns['series:changing_controls'] == 1.
