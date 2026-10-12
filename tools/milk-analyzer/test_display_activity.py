"""Display activity percentiles and bands from frozen reference tables."""
import json
import random

from display_activity import activity, bands, build, classify


def _corpus(tmp_path, count=400):
    directory = tmp_path / 'ruler'
    directory.mkdir()
    rng = random.Random(3)
    for i in range(count):
        level = i / (count - 1)
        row = {'status': 'measured', 'mean_abs_frame_difference': level * .05 + rng.random() * 1e-4,
               'mean_flow_screen_widths_per_s': level * .4 + rng.random() * 1e-3,
               'global_brightness_jumps_per_10s': int(level * 20), 'ruler': {'engine': 'test'}}
        (directory / f'{i:04d}.json').write_text(json.dumps(row))
    return directory


def test_activity_percentile_orders_presets_and_bands_overlap(tmp_path):
    table = build([_corpus(tmp_path)], tmp_path / 'table.json')
    quiet = activity({'mean_abs_frame_difference': .001, 'mean_flow_screen_widths_per_s': .01, 'global_brightness_jumps_per_10s': 0}, table)
    busy = activity({'mean_abs_frame_difference': .049, 'mean_flow_screen_widths_per_s': .39, 'global_brightness_jumps_per_10s': 19}, table)
    assert quiet < .1 < .9 < busy
    assert bands(.3) == ['Chill', 'Normal'] and bands(.72) == ['Normal', 'Intense'] and bands(.9) == ['Intense']


def test_interval_estimates_report_possible_and_certain_bands(tmp_path):
    table = build([_corpus(tmp_path)], tmp_path / 'table.json')
    narrow = classify({'mean_abs_frame_difference': {'value': .005, 'interval': [.004, .006]},
                       'mean_flow_screen_widths_per_s': {'value': .04, 'interval': [.035, .045]},
                       'global_brightness_jumps_per_10s': {'value': 2, 'interval': [2, 2]}}, table)
    assert narrow['certain_bands'] == ['Chill'] and narrow['bands'] == ['Chill']
    wide = classify({'mean_abs_frame_difference': {'value': .025, 'interval': [.001, .049]},
                     'mean_flow_screen_widths_per_s': {'value': .2, 'interval': [.01, .39]},
                     'global_brightness_jumps_per_10s': {'value': 10, 'interval': [0, 19]}}, table)
    assert wide['certain_bands'] == [] and set(wide['possible_bands']) == {'Chill', 'Normal', 'Intense'}
    assert activity({'mean_abs_frame_difference': None}, table) is None
