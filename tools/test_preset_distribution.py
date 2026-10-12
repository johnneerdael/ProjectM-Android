import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


MODULE = Path(__file__).with_name('preset_distribution.py')


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'deterministic distribution generator is missing')
        spec = importlib.util.spec_from_file_location('distribution', MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'core/src/main/assets'
        (self.assets / 'presets').mkdir(parents=True)
        (self.assets / 'textures').mkdir()
        (self.assets / 'preset-genres/genres').mkdir(parents=True)
        rows, metadata, selection = [], [], []
        for i in range(23):
            name = f'Preset {i:02}.milk'
            content = f'[preset00]\nper_frame_1=q1=bass+{i};\n'.encode()
            (self.assets / 'presets' / name).write_bytes(content)
            rows.append(f'{name}\t{i}\n')
            metadata.append({'preset': name, 'score': i, 'sha256': hashlib.sha256(content).hexdigest()})
            if i < 20:
                selection.append({'name': name, 'sha256': hashlib.sha256(content).hexdigest()})
        (self.assets / 'presets.idx').write_text(''.join(rows))
        for genre in ['chill', 'normal', 'intense']:
            (self.assets / f'preset-genres/genres/{genre}.idx').write_text(''.join(rows[::3]))
        (self.assets / 'preset-genres/presets.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in metadata))
        (self.assets / 'preset-genres/manifest.json').write_text(json.dumps({'schema_version': 2, 'total_presets': 23, 'groups': {g: {'count': 8} for g in ['chill', 'normal', 'intense']}, 'checksums': {}, 'library_sha256': 'original', 'status': 'beta'}))
        (self.root / 'docs').mkdir()
        (self.root / 'docs/THIRD_PARTY.md').write_text('Original author notices\n')
        (self.root / 'LICENSES').mkdir()
        (self.root / 'LICENSES/CC0-1.0.txt').write_text('CC0\n')
        (self.root / 'LICENSE').write_text('LGPL\n')
        (self.root / 'tools/preset-distribution').mkdir(parents=True)
        self.selection = self.root / 'tools/preset-distribution/starter-presets.json'
        self.selection.write_text(json.dumps({'schema_version': 1, 'status': 'candidate', 'presets': selection}))
        self.lock = self.root / 'tools/preset-distribution/official-archive.json'
        self.module.lock_archive(self.root, self.lock)

    def build(self, tag='v2.3.39', archive=False):
        return self.module.build_distribution(self.root, self.selection, self.root / tag, tag, archive)

    def test_twenty_unique_presets_and_existing_weights(self):
        result = self.build()
        assets = result['starter_assets']
        self.assertEqual(len(list((assets/'presets').glob('*.milk'))), 20)
        self.assertEqual((assets/'presets.idx').read_text(), ''.join((self.assets/'presets.idx').read_text().splitlines(True)[:20]))
        self.assertEqual(list((assets/'textures').glob('*')), [])
        self.assertEqual(json.loads((assets/'starter-selection.json').read_text())['status'], 'candidate')

    def test_mood_subset_keeps_original_scores(self):
        assets = self.build()['starter_assets']
        lines = (assets/'preset-genres/presets.jsonl').read_text().splitlines()
        self.assertEqual([json.loads(r)['score'] for r in lines], list(range(20)))
        self.assertNotIn('Preset 21.milk', (assets/'preset-genres/genres/chill.idx').read_text())
        manifest = json.loads((assets/'preset-genres/manifest.json').read_text())
        self.assertEqual(manifest['total_presets'], 20)
        self.assertEqual(manifest['groups']['chill']['count'], 7)
        self.assertEqual(manifest['source_library_sha256'], 'original')

    def test_starter_filters_preset_attributes_to_selected_presets(self):
        folder = self.assets / 'preset-attributes'
        folder.mkdir()
        header = ('#projectm-tv-preset-attributes\t1\n#definition\tabc\n#group\tcomfort\tComfort\n'
                  '#option\tcomfort\tno_strobe\tNo strobe\n'
                  '#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n')
        names = [f'Preset {i:02}.milk' for i in range(23)]
        rows = ''.join('%s\tno_strobe\t0.1000\t0.1000\t0.1000\t0.0000\t0.1000\t0.0100\t0.0000\t0.5000\n' % n for n in names)
        (folder / 'attributes.tsv').write_text(header + rows)
        (folder / 'facets.json').write_text('{}')
        (folder / 'manifest.json').write_text(json.dumps({'preset_count': 23, 'measured_count': 23, 'option_counts': {'no_strobe': 23}}))
        files = self.module.source_files(self.root)
        self.assertIn('preset-attributes/attributes.tsv', files)
        output = self.module.starter_files(files, json.loads(self.selection.read_text()))
        lines = [l for l in output['preset-attributes/attributes.tsv'].decode().splitlines() if not l.startswith('#')]
        self.assertEqual([l.split('\t')[0] for l in lines], names[:20])
        manifest = json.loads(output['preset-attributes/manifest.json'])
        self.assertEqual(manifest['preset_count'], 20)
        self.assertEqual(manifest['measured_count'], 20)
        self.assertEqual(manifest['option_counts']['no_strobe'], 20)
        self.assertEqual(manifest['attributes_sha256'], hashlib.sha256(output['preset-attributes/attributes.tsv']).hexdigest())
        self.assertEqual(manifest['presets_idx_sha256'], hashlib.sha256(output['presets.idx']).hexdigest())

    def test_bad_source_hash_rejected(self):
        (self.assets/'presets/Preset 00.milk').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'identity|hash'):
            self.build()

    def test_duplicate_and_unsafe_selection_rejected(self):
        data = json.loads(self.selection.read_text())
        for name in ['Preset 01.milk', '../escape.milk', '/absolute.milk']:
            with self.subTest(name=name):
                altered = json.loads(json.dumps(data))
                altered['presets'][0]['name'] = name
                self.selection.write_text(json.dumps(altered))
                with self.assertRaises(ValueError): self.build()

    def test_texture_and_random_pool_dependencies(self):
        (self.assets/'textures/cells.png').write_bytes(b'one')
        (self.assets/'textures/other.png').write_bytes(b'two')
        p = self.assets/'presets/Preset 00.milk'
        p.write_text('[preset00]\nper_frame_1=q1=bass;\ncomp_1=sampler_cells;\ncomp_2=texsize_cells;\n')
        data=json.loads(self.selection.read_text());data['presets'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.selection.write_text(json.dumps(data))
        self.module.lock_archive(self.root, self.lock)
        a=self.build()['starter_assets']
        self.assertEqual([p.name for p in (a/'textures').iterdir()], ['cells.png'])
        p.write_text(p.read_text()+'comp_3=sampler_rand00;\n')
        data['presets'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.selection.write_text(json.dumps(data));self.module.lock_archive(self.root,self.lock)
        self.assertEqual(len(list((self.build()['starter_assets']/'textures').iterdir())), 2)
        p.write_text(p.read_text()+'comp_4=sampler_missing;\n')
        data['presets'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.selection.write_text(json.dumps(data));self.module.lock_archive(self.root,self.lock)
        with self.assertRaisesRegex(ValueError,'texture'): self.build()

    def test_archive_bytes_ignore_release_tag_and_mtime(self):
        one=self.build(archive=True)
        for p in self.assets.rglob('*'):
            if p.is_file(): os.utime(p, (12345, 12345))
        two=self.build('v2.3.40',archive=True)
        self.assertEqual(one['archive'].read_bytes(), two['archive'].read_bytes())
        self.assertNotEqual(one['descriptor']['archive_url'],two['descriptor']['archive_url'])
        self.assertEqual(one['descriptor']['collection_id'],two['descriptor']['collection_id'])

    def test_descriptor_matches_archive(self):
        result=self.build(archive=True);d=result['descriptor'];archive=result['archive']
        self.assertEqual(d['archive_sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(d['compressed_bytes'],archive.stat().st_size)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(d['expanded_bytes'],sum(e.file_size for e in z.infolist()))
            manifest=json.loads(z.read('manifest.json'))
            for record in manifest['files']:
                self.assertEqual(record['sha256'],hashlib.sha256(z.read(record['path'])).hexdigest())
            self.assertEqual(d['preset_count'],23)
            self.assertIn('LICENSES/CC0-1.0.txt',z.namelist())

    def test_apk_descriptor_uses_lock_without_host_recompression(self):
        before=self.build()['descriptor']
        with patch.object(self.module, 'write_archive', side_effect=ValueError('compression backend changed')):
            self.assertEqual(self.build()['descriptor'],before)
            with self.assertRaisesRegex(ValueError,'compression'): self.build(archive=True)

    def test_changed_builder_bytes_fail_lock_comparison(self):
        original=self.module.write_archive
        def altered(path,files,manifest):
            original(path,files,manifest)
            with path.open('ab') as out: out.write(b'changed compression output')
        with patch.object(self.module,'write_archive',side_effect=altered):
            with self.assertRaisesRegex(ValueError,'lock|archive'): self.build(archive=True)


if __name__ == '__main__': unittest.main()
