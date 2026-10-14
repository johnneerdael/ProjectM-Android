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



def test_frame_program_columns_find_periodic_counters_and_audio_gated_brightness():
    # Stahlregen Crossroads: counter = (counter+1 == 7) ? 1 : counter+1 cycles every 6 frames and drives the
    # wave colour, a strobe the calibrated jumps estimate missed. Static columns expose such mechanisms.
    from static_descriptor import _frame_program_columns
    n = lambda op, *args, **detail: {'op': op, 'dtype': 'float', 'args': list(args), 'detail': detail}
    counter = {'initial': {'root': 0, 'nodes': [n('constant', value=0.)]},
               'update': {'root': 0, 'nodes': [n('select', 1, 5, 2), n('eel_equal', 2, 4), n('add', 3, 6), n('input', name='counter'),
                                               n('constant', value=7.), n('constant', value=1.), n('constant', value=1.)]}}
    wave_r = {'root': 0, 'nodes': [n('multiply', 1, 2), n('constant', value=.5), n('less', 3, 4), n('input', name='counter'), n('constant', value=4.)]}
    gamma = {'root': 0, 'nodes': [n('greater', 1, 2), n('input', name='bass'), n('constant', value=1.2)]}
    summary = {'facts': {'feedback': [{'path': '/analysis/visual_description/stage_programs',
                                       'value': {'frame': {'status': 'exported', 'state': {'counter': counter},
                                                           'outputs': {'wave_r': wave_r, 'gamma': gamma}}}}]}}
    c = _frame_program_columns(summary)
    assert c['frameprog:periodic_state#count'] == 1 and c['frameprog:periodic_state_period#min'] == 6
    assert c['frameprog:brightness_outputs_from_periodic_state#count'] == 1
    assert c['frameprog:brightness_outputs_band_threshold#count'] == 1
