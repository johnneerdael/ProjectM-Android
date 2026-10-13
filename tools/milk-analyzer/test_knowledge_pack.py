"""Knowledge pack: build from corpus results, read back, and catch tampering or drift."""
import base64
import gzip
import json

import knowledge_pack as K


def _corpus(tmp_path):
    import test_preset_recipe as T
    results = tmp_path / 'corpus' / 'results'
    results.mkdir(parents=True)
    for index, name in enumerate(('a.milk', 'b.milk')):
        summary = T.record()
        summary['preset'] = {'name': name, 'sha256': str(index) * 64}
        row = {'name': name, 'sha256': str(index) * 64, 'status': 'computed',
               'summary_gzip_base64': base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode()}
        (results / (name + '.json')).write_text(json.dumps(row))
    (results / 'broken.milk.json').write_text(json.dumps({'name': 'broken.milk', 'sha256': 'f' * 64, 'status': 'timeout'}))
    (tmp_path / 'corpus' / 'run-manifest.json').write_text('{}')
    return tmp_path / 'corpus'


def test_pack_builds_reads_back_and_checks(tmp_path):
    manifest = K.build(_corpus(tmp_path), tmp_path / 'pack', with_programs=True, workers=1)
    assert manifest['counts'] == {'presets': 2, 'failed': 1} and 'broken.milk' in manifest['failures']
    recipes = K.load_core(tmp_path / 'pack')
    assert sorted(recipes) == ['a.milk', 'b.milk']
    assert recipes['a.milk']['policy'] == 'preset-visual-recipe-v1'
    # Graph keys stay in the full layer only.
    assert 'expression' not in json.dumps(recipes['a.milk'])
    assert (tmp_path / 'pack' / 'full' / ('0' * 64 + '.json.gz')).exists()
    assert K.check(tmp_path / 'pack') == []


def test_check_detects_tampered_core_and_changed_presets(tmp_path):
    K.build(_corpus(tmp_path), tmp_path / 'pack', workers=1)
    presets = tmp_path / 'presets'; presets.mkdir()
    (presets / 'a.milk').write_text('changed bytes')
    problems = K.check(tmp_path / 'pack', presets)
    assert any('a.milk: preset bytes changed' in p for p in problems) and any('b.milk: not in the collection' in p for p in problems)
    core = tmp_path / 'pack' / 'core.jsonl.gz'
    core.write_bytes(gzip.compress(gzip.decompress(core.read_bytes()).replace(b'a.milk', b'z.milk')))
    assert K.check(tmp_path / 'pack') == ['core file hash mismatch']
