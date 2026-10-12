import hashlib, json, tempfile, unittest
from pathlib import Path

import attribute_bundle as B

RULER = {'engine': 'test', 'size': [480, 270], 'frames': 300, 'audio': 'test'}


def write_manifest(tmp, skip=()):
    """An evidence manifest matching the result files in tmp/ruler (rows for names in skip are left out)."""
    rows = []
    for path in sorted((tmp / 'ruler').glob('*.json')):
        row = json.loads(path.read_text())
        if row['preset'] not in skip:
            rows.append({'preset': row['preset'], 'preset_sha256': row['preset_sha256'],
                         'result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': row['status']})
    (tmp / 'ruler-manifest.json').write_text(json.dumps({'policy': 'test', 'rows': rows}, indent=1) + '\n')


def write_style(tmp, styles, digests=None, extra=''):
    """A style facts file with one row per name; each row carries the sha256 of tmp/presets/<name> unless overridden."""
    lines = ['#projectm-tv-facet-style-facts\t1\tabc']
    for name, found in styles.items():
        digest = (digests or {}).get(name) or hashlib.sha256((tmp / 'presets' / name).read_bytes()).hexdigest()
        lines.append('%s\t%s\t%s' % (name, digest, found))
    (tmp / 'style.tsv').write_text('\n'.join(lines) + '\n' + extra)


def make_inputs(tmp):
    tmp = Path(tmp)
    (tmp / 'ruler').mkdir(); (tmp / 'presets').mkdir()
    stats = {'a.milk': (.05, .1, .05, .0, .01, .005, 0.), 'b.milk': (.3, .6, .8, .3, .2, .05, 3.), 'c.milk': (.5, .2, .4, -.3, .5, .2, 30.)}
    for name in list(stats) + ['d.milk']:
        (tmp / 'presets' / name).write_text('[preset00]\n// %s\n' % name)  # presets/ next to presets.idx: the default
    for name, (lum, sat, col, wc, flow, diff, jumps) in stats.items():
        digest = hashlib.sha256((tmp / 'presets' / name).read_bytes()).hexdigest()
        (tmp / 'ruler' / (name + '.json')).write_text(json.dumps({
            'status': 'measured', 'preset': name, 'preset_sha256': digest, 'ruler': RULER, 'mean_luminance': lum, 'mean_saturation': sat,
            'coloured_share': col, 'warm_cool': wc, 'mean_flow_screen_widths_per_s': flow, 'mean_abs_frame_difference': diff,
            'global_brightness_jumps_per_10s': jumps}))
    write_manifest(tmp)
    write_style(tmp, {'a.milk': 'tunnel', 'b.milk': '', 'c.milk': 'kaleidoscope,fractal', 'd.milk': ''})
    (tmp / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\n')
    return tmp


class BundleTest(unittest.TestCase):
    def test_build_then_check_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            manifest = B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')
            self.assertEqual(manifest['preset_count'], 4); self.assertEqual(manifest['measured_count'], 3)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
            lines = (t / 'out' / 'attributes.tsv').read_text().splitlines()
            rows = {l.split('\t')[0]: l.split('\t') for l in lines if not l.startswith('#')}
            self.assertIn('tunnel', rows['a.milk'][1].split(',')); self.assertIn('dark', rows['a.milk'][1].split(','))
            self.assertIn('monochrome', rows['a.milk'][1].split(','))
            self.assertEqual(rows['d.milk'][1:], [''] + ['-'] * 8)  # unmeasured preset: no options, no values
            self.assertIn('fast', rows['c.milk'][1].split(',')); self.assertNotIn('no_strobe', rows['c.milk'][1].split(','))

    def test_check_verifies_the_ruler_evidence_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
            (t / 'ruler-manifest.json').write_text('{"evidence": 2, "rows": []}\n')
            self.assertTrue(any('ruler' in p for p in B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')))
            self.assertTrue(any('ruler' in p for p in B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'missing.json')))
            self.assertTrue(any('ruler' in p for p in B.check(t / 'out', t / 'presets.idx')))

    def test_check_fails_when_the_bundle_records_no_ruler_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.build(t)
            manifest = json.loads((t / 'out' / 'manifest.json').read_text()); manifest['ruler_results_manifest_sha256'] = None
            (t / 'out' / 'manifest.json').write_text(json.dumps(manifest))
            self.assertTrue(any('ruler' in p for p in B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')))

    def build(self, t):
        return B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')

    def test_build_rejects_a_result_altered_after_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            path = t / 'ruler' / 'b.milk.json'
            path.write_text(path.read_text().replace('"mean_luminance": 0.3', '"mean_luminance": 0.31'))
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.build(t)

    def test_build_rejects_a_result_missing_from_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            write_manifest(t, skip=('c.milk',))
            with self.assertRaisesRegex(ValueError, 'c.milk'):
                self.build(t)

    def test_build_rejects_a_preset_hash_that_differs_from_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            manifest = json.loads((t / 'ruler-manifest.json').read_text())
            manifest['rows'][0]['preset_sha256'] = 'f' * 64
            (t / 'ruler-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                self.build(t)

    def test_build_rejects_a_measured_manifest_row_whose_result_was_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'ruler' / 'b.milk.json').unlink()
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.build(t)
            self.assertFalse((t / 'out').exists())

    def test_build_rejects_a_measured_manifest_row_whose_result_is_no_longer_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            path = t / 'ruler' / 'b.milk.json'
            path.write_text(path.read_text().replace('"status": "measured"', '"status": "failed"'))
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.build(t)

    def test_build_rejects_two_measured_results_for_one_manifest_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'ruler' / 'b-copy.json').write_bytes((t / 'ruler' / 'b.milk.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.build(t)

    def test_build_rejects_a_preset_asset_that_differs_from_the_measured_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'presets' / 'c.milk').write_text('[preset00]\nchanged\n')
            with self.assertRaisesRegex(ValueError, 'c.milk'):
                self.build(t)
            (t / 'presets' / 'c.milk').unlink()
            with self.assertRaisesRegex(ValueError, 'c.milk'):
                self.build(t)
            self.assertFalse((t / 'out').exists())

    def test_build_rejects_a_style_row_for_changed_preset_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            write_style(t, {'a.milk': 'tunnel', 'b.milk': '', 'c.milk': '', 'd.milk': ''}, digests={'a.milk': '0' * 64})
            with self.assertRaisesRegex(ValueError, 'a.milk'):
                self.build(t)
            self.assertFalse((t / 'out').exists())

    def test_build_rejects_a_missing_style_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            write_style(t, {'a.milk': 'tunnel', 'b.milk': '', 'd.milk': ''})
            with self.assertRaisesRegex(ValueError, 'c.milk'):
                self.build(t)

    def test_build_rejects_a_duplicate_style_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            write_style(t, {'a.milk': 'tunnel', 'b.milk': '', 'c.milk': '', 'd.milk': ''}, extra='a.milk\t%s\t\n' % hashlib.sha256((t / 'presets' / 'a.milk').read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, 'a.milk'):
                self.build(t)

    def test_build_and_check_take_an_explicit_presets_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'presets').rename(t / 'elsewhere')
            with self.assertRaises(ValueError):
                self.build(t)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json', presets_dir=t / 'elsewhere')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json', presets_dir=t / 'elsewhere'), [])
            self.assertTrue(any('a.milk' in p for p in B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')))

    def test_check_compares_bundled_preset_bytes_with_the_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.build(t)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
            (t / 'presets' / 'd.milk').write_text('unmeasured presets have no evidence row\n')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
            (t / 'presets' / 'a.milk').write_text('[preset00]\nedited after measuring\n')
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')
            self.assertTrue(any('a.milk' in p for p in problems), problems)
            (t / 'presets' / 'a.milk').unlink()
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')
            self.assertTrue(any('a.milk' in p for p in problems), problems)

    def freeze(self, t):
        return B.freeze_activity_reference(t / 'ruler', t / 'reference.json', t / 'ruler-manifest.json', t / 'presets.idx')

    def test_freeze_verifies_the_evidence_before_writing_the_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.assertEqual(len(self.freeze(t)), 64)
            (t / 'reference.json').unlink()
            (t / 'ruler' / 'c.milk.json').unlink()  # completeness
            with self.assertRaisesRegex(ValueError, 'c.milk'):
                self.freeze(t)
            self.assertFalse((t / 'reference.json').exists())
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            path = t / 'ruler' / 'b.milk.json'  # result hash
            path.write_text(path.read_text().replace('"mean_luminance": 0.3', '"mean_luminance": 0.31'))
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.freeze(t)
            self.assertFalse((t / 'reference.json').exists())
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'presets' / 'a.milk').write_text('[preset00]\nchanged\n')  # preset asset hash
            with self.assertRaisesRegex(ValueError, 'a.milk'):
                self.freeze(t)
            self.assertFalse((t / 'reference.json').exists())

    def test_build_requires_a_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            with self.assertRaises(ValueError):
                B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            self.assertFalse((t / 'out').exists())

    def test_activity_is_the_percentile_of_the_mean_metric_rank(self):
        rows = [{'preset': n, 'mean_abs_frame_difference': d, 'mean_flow_screen_widths_per_s': f, 'global_brightness_jumps_per_10s': j}
                for n, d, f, j in (('x', .01, .01, 0), ('y', .05, .1, 1), ('z', .2, .5, 30))]
        a = B.activity_values(rows, B.make_activity_reference(rows, {'test': 1}))
        self.assertLess(a['x'], a['y']); self.assertLess(a['y'], a['z'])
        self.assertTrue(all(0 <= v <= 1 for v in a.values()))

    def test_activity_scores_against_the_frozen_reference_not_the_current_rows(self):
        reference_rows = [{'preset': 'r%d' % i, 'mean_abs_frame_difference': i / 100, 'mean_flow_screen_widths_per_s': i / 50,
                           'global_brightness_jumps_per_10s': i % 7} for i in range(200)]
        reference = B.make_activity_reference(reference_rows, {'test': 1})
        self.assertEqual(len(reference['mean_rank']), 1001)
        self.assertTrue(all(len(reference['metrics'][m]) == 1001 for m in B.ACTIVITY_METRICS))
        row = {'preset': 'q', 'mean_abs_frame_difference': 1.0, 'mean_flow_screen_widths_per_s': 2.0, 'global_brightness_jumps_per_10s': 3}
        others = [{'preset': 'h', 'mean_abs_frame_difference': 9, 'mean_flow_screen_widths_per_s': 9, 'global_brightness_jumps_per_10s': 99}]
        alone = B.activity_values([row], reference)['q']
        self.assertEqual(alone, B.activity_values([row] + others, reference)['q'])
        self.assertNotEqual(alone, 0.5)  # a one-row corpus percentile would be 0.5
        self.assertAlmostEqual(alone, 0.5, delta=0.1)  # the median-ish reference preset

    def test_the_committed_reference_matches_the_definition(self):
        definition = json.loads(B.preset_facets.DEFINITION.read_text())
        entry = definition['activity_reference']
        data = (B.preset_facets.DEFINITION.parent / entry['file']).read_bytes()
        self.assertEqual(B._sha(data), entry['sha256'])
        reference = json.loads(data)
        self.assertEqual(reference['provenance']['preset_count'], 9606)
        self.assertEqual(reference['provenance']['ruler_results_manifest_sha256'],
                         'f7ccb0ca37ca86bd3252a72226ba30b547a03f964182884bef145815049db1e3')

    def test_check_fails_when_the_activity_reference_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'facets').mkdir()
            definition = json.loads(B.preset_facets.DEFINITION.read_text())
            source = B.preset_facets.DEFINITION.parent / definition['activity_reference']['file']
            (t / 'facets' / definition['activity_reference']['file']).write_bytes(source.read_bytes())
            (t / 'facets' / 'facets-v1.json').write_bytes(B.preset_facets.DEFINITION.read_bytes())
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', definition_path=t / 'facets' / 'facets-v1.json', ruler_manifest=t / 'ruler-manifest.json')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json', definition_path=t / 'facets' / 'facets-v1.json'), [])
            reference = t / 'facets' / definition['activity_reference']['file']
            reference.write_text(reference.read_text().replace('"mean_rank"', '"mean_rank" ', 1))
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json', definition_path=t / 'facets' / 'facets-v1.json')
            self.assertTrue(any('activity reference' in p for p in problems), problems)
            with self.assertRaises(ValueError):
                B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', definition_path=t / 'facets' / 'facets-v1.json', ruler_manifest=t / 'ruler-manifest.json')

    def test_check_detects_stale_index_definition_and_tampered_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')
            (t / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\ne.milk\t0\n')
            self.assertTrue(any('presets.idx' in p for p in B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')))
            text = (t / 'out' / 'attributes.tsv').read_text().replace('tunnel', 'liquid')
            (t / 'out' / 'attributes.tsv').write_text(text)
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')
            self.assertTrue(any('attributes' in p for p in problems))

    def test_rejects_missing_ruler_fields_and_unknown_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            write_style(t, {'a.milk': 'spirals', 'b.milk': '', 'c.milk': '', 'd.milk': ''})
            with self.assertRaises(ValueError):
                B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')

    def test_undefined_warm_cool_is_a_dash_and_never_warm_or_cool(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            path = t / 'ruler' / 'a.milk.json'
            row = json.loads(path.read_text()); row['warm_cool'] = None; row['coloured_share'] = 0.0
            path.write_text(json.dumps(row))
            write_manifest(t)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out', ruler_manifest=t / 'ruler-manifest.json')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
            rows = {l.split('\t')[0]: l.split('\t') for l in (t / 'out' / 'attributes.tsv').read_text().splitlines() if not l.startswith('#')}
            self.assertEqual(rows['a.milk'][5], '-')
            self.assertFalse({'warm', 'cool'} & set(rows['a.milk'][1].split(',')))
