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

