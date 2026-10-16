import gzip, hashlib, json, tempfile, unittest
from pathlib import Path

import attribute_bundle as B

RULER = {'engine': 'test', 'size': [480, 270], 'frames': 300, 'audio': 'test'}


FIELDS = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'coloured_share': 'coloured_share',
          'warm_cool': 'warm_cool', 'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference',
          'jumps': 'global_brightness_jumps_per_10s'}


def write_manifest(tmp, skip=()):
    """An evidence manifest matching the result files in tmp/ruler (rows for names in skip are left out)."""
    rows = []
    for path in sorted((tmp / 'ruler').glob('*.json')):
        row = json.loads(path.read_text())
        if row['preset'] not in skip:
            rows.append({'preset': row['preset'], 'preset_sha256': row['preset_sha256'],
                         'result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': row['status']})
            if row['status'] == 'measured':
                rows[-1]['metrics'] = {k: '-' if row[f] is None else '%.4f' % row[f] for k, f in FIELDS.items()}
                rows[-1]['activity_inputs'] = {k: row[FIELDS[k]] for k in ('frame_difference', 'flow', 'jumps')}
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

    def test_check_requires_bundle_rows_to_match_the_manifest_measured_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.build(t)
            mpath = t / 'ruler-manifest.json'
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=mpath), [])

            def rerecord():
                bm = json.loads((t / 'out' / 'manifest.json').read_text())
                bm['ruler_results_manifest_sha256'] = hashlib.sha256(mpath.read_bytes()).hexdigest()
                (t / 'out' / 'manifest.json').write_text(json.dumps(bm))
            original = mpath.read_text()
            data = json.loads(original)
            for row in data['rows']:
                if row['preset'] == 'a.milk':
                    row['status'] = 'render_error'
            mpath.write_text(json.dumps(data)); rerecord()
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=mpath)
            self.assertTrue(any('a.milk' in p and 'measured' in p for p in problems), problems)
            data = json.loads(original)
            data['rows'].append({'preset': 'd.milk', 'preset_sha256': hashlib.sha256((t / 'presets' / 'd.milk').read_bytes()).hexdigest(),
                                 'result_sha256': '0' * 64, 'status': 'measured'})
            mpath.write_text(json.dumps(data)); rerecord()
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=mpath)
            self.assertTrue(any('d.milk' in p and 'measured' in p for p in problems), problems)

    def rewrite_bundle_row(self, t, name, edit):
        """Applies edit(cells) to a bundle row and re-records attributes_sha256, as a forger would."""
        path = t / 'out' / 'attributes.tsv'
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.split('\t')[0] == name:
                cells = line.split('\t'); edit(cells); lines[i] = '\t'.join(cells)
        data = ('\n'.join(lines) + '\n').encode(); path.write_bytes(data)
        manifest = json.loads((t / 'out' / 'manifest.json').read_text())
        manifest['attributes_sha256'] = hashlib.sha256(data).hexdigest()
        (t / 'out' / 'manifest.json').write_text(json.dumps(manifest))

    def test_check_rejects_edited_values_and_memberships_that_still_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.build(t)
            mpath = t / 'ruler-manifest.json'
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=mpath), [])

            def edit(cells):
                cells[2] = '0.9000'  # luminance: dark -> bright; memberships recomputed to match
                cells[1] = ','.join(o for o in cells[1].split(',') if o != 'dark')
            self.rewrite_bundle_row(t, 'a.milk', edit)
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=mpath)
            self.assertTrue(any('a.milk' in p and 'evidence' in p for p in problems), problems)

    def test_check_rejects_an_edited_activity_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            self.build(t)
            self.rewrite_bundle_row(t, 'b.milk', lambda cells: cells.__setitem__(9, '0.9999'))
            problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')
            self.assertTrue(any('b.milk' in p and 'activity' in p for p in problems), problems)

    def test_build_rejects_a_result_whose_metrics_differ_from_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            data = json.loads((t / 'ruler-manifest.json').read_text())
            for row in data['rows']:
                if row['preset'] == 'b.milk':
                    row['metrics']['luminance'] = '0.9000'
            (t / 'ruler-manifest.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'b.milk'):
                self.build(t)

    def test_write_evidence_manifest_adds_metrics_and_keeps_other_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            expected = json.loads((t / 'ruler-manifest.json').read_text())
            old = json.loads((t / 'ruler-manifest.json').read_text())
            for row in old['rows']:
                del row['metrics']; del row['activity_inputs']
            old['policy'] = 'engine-ruler-results-manifest-v1'; old['keep'] = {'x': 1}
            (t / 'old.json').write_text(json.dumps(old))
            B.write_evidence_manifest(t / 'ruler', t / 'old.json', t / 'new.json')
            new = json.loads((t / 'new.json').read_text())
            self.assertEqual(new['policy'], 'engine-ruler-results-manifest-v2'); self.assertEqual(new['keep'], {'x': 1})
            self.assertEqual(new['rows'], expected['rows'])

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

    def test_build_and_freeze_reject_ruler_rows_outside_the_preset_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'presets' / 'gone.milk').write_text('[preset00]\n// gone\n')
            digest = hashlib.sha256((t / 'presets' / 'gone.milk').read_bytes()).hexdigest()
            base = json.loads((t / 'ruler' / 'a.milk.json').read_text())
            base.update(preset='gone.milk', preset_sha256=digest)
            (t / 'ruler' / 'gone.milk.json').write_text(json.dumps(base))
            write_manifest(t)  # the manifest row and the result are consistent; only presets.idx lacks the preset
            with self.assertRaisesRegex(ValueError, 'gone.milk.*not in presets.idx'):
                self.build(t)
            self.assertFalse((t / 'out').exists())
            with self.assertRaisesRegex(ValueError, 'gone.milk.*not in presets.idx'):
                self.freeze(t)
            self.assertFalse((t / 'reference.json').exists())

    def test_build_rejects_a_manifest_row_outside_the_preset_index_without_a_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            manifest = json.loads((t / 'ruler-manifest.json').read_text())
            manifest['rows'].append({'preset': 'gone.milk', 'preset_sha256': 'e' * 64, 'result_sha256': 'f' * 64, 'status': 'measured'})
            (t / 'ruler-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'gone.milk.*not in presets.idx'):
                self.build(t)

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

    def test_check_recomputes_the_generated_manifest_metadata(self):
        edits = {
            'schema': lambda m: m.update(schema='projectm-tv-other'),
            'version': lambda m: m.update(version=2),
            'preset_count': lambda m: m.update(preset_count=m['preset_count'] + 1),
            'measured_count': lambda m: m.update(measured_count=m['measured_count'] - 1),
            'option_counts': lambda m: m['option_counts'].update(tunnel=m['option_counts']['tunnel'] + 1),
        }
        missing = {
            'option_counts': lambda m: m['option_counts'].pop('tunnel'),
            'measured_count': lambda m: m.pop('measured_count'),
        }
        extra = {'option_counts': lambda m: m['option_counts'].update(unknown_option=0)}
        for label, cases in (('edited', edits), ('missing', missing), ('extra', extra)):
            for field, edit in cases.items():
                with self.subTest(change=label, field=field), tempfile.TemporaryDirectory() as tmp:
                    t = make_inputs(tmp)
                    self.build(t)
                    self.assertEqual(B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json'), [])
                    manifest = json.loads((t / 'out' / 'manifest.json').read_text())
                    edit(manifest)
                    (t / 'out' / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
                    problems = B.check(t / 'out', t / 'presets.idx', ruler_manifest=t / 'ruler-manifest.json')
                    self.assertTrue(any(field in p for p in problems), problems)

    def test_the_committed_bundle_passes_check(self):
        root = Path(__file__).resolve().parents[2]
        bundle = root / 'core/src/main/assets/preset-attributes'
        if not (bundle / 'manifest.json').is_file():
            self.skipTest('no committed bundle in this checkout')
        self.assertEqual(json.loads((bundle / 'manifest.json').read_text())['source'], B.STATIC_SOURCE)
        self.assertEqual(B.check(bundle, root / 'core/src/main/assets/presets.idx', ruler_manifest=root / B.DEFAULT_RULER_MANIFEST,
                                 static_evidence=root / B.DEFAULT_STATIC_EVIDENCE), [])


VALUES = {'luminance': .3, 'saturation': .6, 'coloured_share': .8, 'warm_cool': .3, 'flow': .2, 'frame_difference': .05,
          'jumps': 3., 'activity': .5}


def write_static_evidence(tmp, rows=None, edit=None):
    """Static evidence for tmp/presets: a.milk red/blue with a red main colour, b.milk grey, c.milk without values."""
    tmp = Path(tmp); sha = lambda n: hashlib.sha256((tmp / 'presets' / n).read_bytes()).hexdigest()
    rows = rows if rows is not None else [
        {'name': 'a.milk', 'sha256': sha('a.milk'), 'options': ['tunnel', 'intense', 'vivid'], 'palette': ['red', 'blue'],
         'dominant': 'red', 'values': dict(VALUES)},
        {'name': 'b.milk', 'sha256': sha('b.milk'), 'options': ['monochrome', 'chill'], 'palette': ['green'], 'dominant': None,
         'values': dict(VALUES, warm_cool=None)},
        {'name': 'c.milk', 'sha256': sha('c.milk'), 'options': [], 'palette': [], 'dominant': None,
         'values': {c: None for c in VALUES}}]
    evidence = {'schema': B.STATIC_EVIDENCE_SCHEMA, 'version': 1, 'producer': {'commit': 'abc', 'policy': 'test'}, 'rows': rows}
    if edit:
        edit(evidence)
    (tmp / 'evidence.json.gz').write_bytes(gzip.compress(json.dumps(evidence, sort_keys=True).encode(), mtime=0))
    return tmp / 'evidence.json.gz'


def make_static_inputs(tmp):
    tmp = Path(tmp); (tmp / 'presets').mkdir()
    for name in ('a.milk', 'b.milk', 'c.milk'):
        (tmp / 'presets' / name).write_text('[preset00]\n// %s\n' % name)
    (tmp / 'presets.idx').write_text('a.milk\t0\nb.milk\t0\nc.milk\t0\n')
    return tmp, write_static_evidence(tmp)


class StaticBundleTest(unittest.TestCase):
    def rows(self, out):
        return {l.split('\t')[0]: l.split('\t') for l in (out / 'attributes.tsv').read_text().splitlines() if not l.startswith('#')}

    def test_build_static_then_check_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            manifest = B.build_static(ev, t / 'presets.idx', t / 'out')
            self.assertEqual((manifest['source'], manifest['preset_count'], manifest['measured_count']), ('static-analysis', 3, 2))
            self.assertEqual(manifest['static_evidence_sha256'], hashlib.sha256(ev.read_bytes()).hexdigest())
            self.assertNotIn('ruler', manifest)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', static_evidence=ev), [])
            rows = self.rows(t / 'out')
            # options in definition order, palette families then the main colour
            self.assertEqual(rows['a.milk'][1], 'intense,vivid,red,blue,main_red,tunnel')
            self.assertEqual(rows['b.milk'][1], 'chill,monochrome')  # grey: no palette and no main colour
            self.assertEqual(rows['b.milk'][2:], ['0.3000', '0.6000', '0.8000', '-', '0.2000', '0.0500', '3.0000', '0.5000'])
            self.assertEqual(rows['c.milk'][1:], [''] + ['-'] * 8)
            self.assertEqual(manifest['option_counts']['red'], 1); self.assertEqual(manifest['option_counts']['green'], 0)

    def test_check_requires_the_static_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            self.assertEqual(B.check(t / 'out', t / 'presets.idx'), ['static evidence path is required for a static-analysis bundle'])

    def test_check_reports_evidence_drift_in_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            def drop_option(e): e['rows'][0]['options'].remove('vivid')
            write_static_evidence(t, edit=drop_option)
            problems = B.check(t / 'out', t / 'presets.idx', static_evidence=ev)
            self.assertTrue(any('differs from the bundle manifest hash' in p for p in problems), problems)
            self.assertTrue(any('a.milk: row differs from the static evidence' in p for p in problems), problems)

    def test_check_rejects_an_edited_row_even_with_a_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            text = (t / 'out' / 'attributes.tsv').read_text().replace('intense,vivid,red', 'intense,vivid,green')
            (t / 'out' / 'attributes.tsv').write_text(text)
            manifest = json.loads((t / 'out' / 'manifest.json').read_text())
            manifest['attributes_sha256'] = hashlib.sha256(text.encode()).hexdigest()
            manifest['option_counts']['green'] += 1; manifest['option_counts']['red'] -= 1
            (t / 'out' / 'manifest.json').write_text(json.dumps(manifest))
            problems = B.check(t / 'out', t / 'presets.idx', static_evidence=ev)
            self.assertEqual(problems, ['bundle rows differ from the static evidence (1): a.milk: row differs from the static evidence'])

    def test_a_preset_without_evidence_fails_build_and_check_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            (t / 'presets' / 'd.milk').write_text('[preset00]\n')
            (t / 'presets.idx').write_text('a.milk\t0\nb.milk\t0\nc.milk\t0\nd.milk\t0\n')
            with self.assertRaisesRegex(ValueError, 'd.milk: no static evidence row'):
                B.build_static(ev, t / 'presets.idx', t / 'out2')
            problems = B.check(t / 'out', t / 'presets.idx', static_evidence=ev)
            self.assertIn('d.milk: no static evidence row', problems)
            self.assertIn('presets.idx changed since the bundle was built', problems)

    def test_an_extra_evidence_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            write_static_evidence(t, edit=lambda e: e['rows'].append(dict(e['rows'][2], name='z.milk')))
            with self.assertRaisesRegex(ValueError, 'z.milk: static evidence row for a preset not in presets.idx'):
                B.build_static(ev, t / 'presets.idx', t / 'out')

    def test_a_changed_preset_file_fails_until_reanalysed(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            (t / 'presets' / 'b.milk').write_text('[preset00]\nzoom=2\n')
            self.assertIn('b.milk: preset bytes differ from the static evidence sha256 (re-analyse it)',
                          B.check(t / 'out', t / 'presets.idx', static_evidence=ev))
            with self.assertRaisesRegex(ValueError, 'preset bytes differ'):
                B.build_static(ev, t / 'presets.idx', t / 'out2')

    def test_unknown_options_and_colours_are_rejected(self):
        for edit, message in ((lambda e: e['rows'][0]['options'].append('spirals'), 'not in the definition'),
                              (lambda e: e['rows'][0]['options'].append('red'), 'not in the definition'),
                              (lambda e: e['rows'][0].update(palette=['magenta']), 'unknown colour families'),
                              (lambda e: e['rows'][0].update(dominant='teal'), 'unknown colour families')):
            with tempfile.TemporaryDirectory() as tmp:
                t, ev = make_static_inputs(tmp)
                write_static_evidence(t, edit=edit)
                with self.assertRaisesRegex(ValueError, message):
                    B.build_static(ev, t / 'presets.idx', t / 'out')

    def test_duplicate_rows_and_wrong_schema_are_rejected(self):
        for edit, message in ((lambda e: e['rows'].append(e['rows'][0]), 'more than once'),
                              (lambda e: e.update(schema='other'), 'schema')):
            with tempfile.TemporaryDirectory() as tmp:
                t, ev = make_static_inputs(tmp)
                write_static_evidence(t, edit=edit)
                with self.assertRaisesRegex(ValueError, message):
                    B.build_static(ev, t / 'presets.idx', t / 'out')

    def test_analysis_errors_are_limited_and_left_unlabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            write_static_evidence(t, edit=lambda e: e['rows'][0].update(error='boom'))
            with self.assertRaisesRegex(ValueError, '1 presets failed static analysis'):
                B.build_static(ev, t / 'presets.idx', t / 'out')
            manifest = B.build_static(ev, t / 'presets.idx', t / 'out', max_errors=1)
            self.assertEqual(manifest['analysis_errors'], 1)
            self.assertEqual(self.rows(t / 'out')['a.milk'][1:], [''] + ['-'] * 8)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx', static_evidence=ev), [])

    def test_size_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            t, ev = make_static_inputs(tmp)
            with self.assertRaisesRegex(ValueError, 'over the 10 byte budget'):
                B.build_static(ev, t / 'presets.idx', t / 'out', size_budget=10)
            B.build_static(ev, t / 'presets.idx', t / 'out')
            self.assertTrue(any(p.startswith('size budget') for p in
                                B.check_static(t / 'out', t / 'presets.idx', ev, size_budget=10)))

    def test_check_recomputes_the_static_manifest_metadata(self):
        for field, value in (('source', 'engine-ruler'), ('producer', {'commit': 'other'}), ('measured_count', 3),
                             ('analysis_errors', 2), ('option_counts', {})):
            with tempfile.TemporaryDirectory() as tmp:
                t, ev = make_static_inputs(tmp)
                B.build_static(ev, t / 'presets.idx', t / 'out')
                manifest = json.loads((t / 'out' / 'manifest.json').read_text()); manifest[field] = value
                (t / 'out' / 'manifest.json').write_text(json.dumps(manifest))
                problems = B.check_static(t / 'out', t / 'presets.idx', ev)
                self.assertTrue(any(field in p for p in problems), (field, problems))
