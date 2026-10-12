import json, tempfile, unittest
from pathlib import Path

import attribute_bundle as B

RULER = {'engine': 'test', 'size': [480, 270], 'frames': 300, 'audio': 'test'}


def make_inputs(tmp):
    tmp = Path(tmp)
    (tmp / 'ruler').mkdir()
    stats = {'a.milk': (.05, .1, .05, .0, .01, .005, 0.), 'b.milk': (.3, .6, .8, .3, .2, .05, 3.), 'c.milk': (.5, .2, .4, -.3, .5, .2, 30.)}
    for name, (lum, sat, col, wc, flow, diff, jumps) in stats.items():
        (tmp / 'ruler' / (name + '.json')).write_text(json.dumps({
            'status': 'measured', 'preset': name, 'preset_sha256': name * 2, 'ruler': RULER, 'mean_luminance': lum, 'mean_saturation': sat,
            'coloured_share': col, 'warm_cool': wc, 'mean_flow_screen_widths_per_s': flow, 'mean_abs_frame_difference': diff,
            'global_brightness_jumps_per_10s': jumps}))
    (tmp / 'style.tsv').write_text('#projectm-tv-facet-style-facts\t1\tabc\na.milk\tx\ttunnel\nb.milk\tx\t\nc.milk\tx\tkaleidoscope,fractal\n')
    (tmp / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\n')
    return tmp


class BundleTest(unittest.TestCase):
    def test_build_then_check_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            manifest = B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            self.assertEqual(manifest['preset_count'], 4); self.assertEqual(manifest['measured_count'], 3)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx'), [])
            lines = (t / 'out' / 'attributes.tsv').read_text().splitlines()
            rows = {l.split('\t')[0]: l.split('\t') for l in lines if not l.startswith('#')}
            self.assertIn('tunnel', rows['a.milk'][1].split(',')); self.assertIn('dark', rows['a.milk'][1].split(','))
            self.assertIn('monochrome', rows['a.milk'][1].split(','))
            self.assertEqual(rows['d.milk'][1:], [''] + ['-'] * 8)  # unmeasured preset: no options, no values
            self.assertIn('fast', rows['c.milk'][1].split(',')); self.assertNotIn('no_strobe', rows['c.milk'][1].split(','))

    def test_activity_is_the_percentile_of_the_mean_metric_rank(self):
        rows = [{'preset': n, 'mean_abs_frame_difference': d, 'mean_flow_screen_widths_per_s': f, 'global_brightness_jumps_per_10s': j}
                for n, d, f, j in (('x', .01, .01, 0), ('y', .05, .1, 1), ('z', .2, .5, 30))]
        a = B.activity_values(rows)
        self.assertLess(a['x'], a['y']); self.assertLess(a['y'], a['z'])
        self.assertTrue(all(0 <= v <= 1 for v in a.values()))

    def test_check_detects_stale_index_definition_and_tampered_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            (t / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\ne.milk\t0\n')
            self.assertTrue(any('presets.idx' in p for p in B.check(t / 'out', t / 'presets.idx')))
            text = (t / 'out' / 'attributes.tsv').read_text().replace('tunnel', 'liquid')
            (t / 'out' / 'attributes.tsv').write_text(text)
            problems = B.check(t / 'out', t / 'presets.idx')
            self.assertTrue(any('attributes' in p for p in problems))

    def test_rejects_missing_ruler_fields_and_unknown_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'style.tsv').write_text('#projectm-tv-facet-style-facts\t1\tabc\na.milk\tx\tspirals\n')
            with self.assertRaises(ValueError):
                B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')

    def test_undefined_warm_cool_is_a_dash_and_never_warm_or_cool(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            path = t / 'ruler' / 'a.milk.json'
            row = json.loads(path.read_text()); row['warm_cool'] = None; row['coloured_share'] = 0.0
            path.write_text(json.dumps(row))
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx'), [])
            rows = {l.split('\t')[0]: l.split('\t') for l in (t / 'out' / 'attributes.tsv').read_text().splitlines() if not l.startswith('#')}
            self.assertEqual(rows['a.milk'][5], '-')
            self.assertFalse({'warm', 'cool'} & set(rows['a.milk'][1].split(',')))
