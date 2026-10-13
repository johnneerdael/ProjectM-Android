"""Golden reader vectors for the knowledge pack: packs every reader implementation must accept or reject.

    python knowledge_pack_golden.py <out-dir>      # writes export-contract/knowledge-pack/golden-v1 by default

Inputs are the frozen recipes in <out-dir>/recipes/*.json. Outputs (all deterministic):
    valid/            a well-formed pack
    unknown-fields/   the same data plus fields a v1 reader does not know (must be accepted, same values)
    null-containers/  view containers set to null, as producers emit when an estimate is missing
                      (must be accepted; null means empty)
    bad-policy/       manifest policy of a later pack version (must be rejected)
    bad-recipe-policy/ one recipe line with a later recipe policy, hashes consistent (must be rejected)
    bad-core-hash/    core file bytes that do not match manifest core.sha256 (must be rejected)
    bad-line-hash/    one recipe line changed, file hash updated, line hash not (must be rejected)
    bad-utf8/         one line holding an invalid UTF-8 byte, all hashes consistent (must be rejected)
    bad-field-type/   a reader-view field of the wrong JSON type, hashes consistent (must be rejected)
    bad-no-presets/   manifest without its presets array, empty core with a matching hash (must be rejected)
    bad-crlf/         lines ending in CR LF, hashes taken over the bytes including CR (must be rejected)
    bad-final-lf/     the last line without its terminating LF, hashes consistent (must be rejected)
    bad-two-members/  each line in its own gzip member, file hash updated (must be rejected)
    bad-trailing-bytes/ one valid gzip member followed by extra bytes, file hash updated (must be rejected)
    bad-header-crc/   a gzip header with FHCRC set and a wrong header CRC, file hash updated (must be rejected)
    expected.json     what a reader exposes for the accepted packs, and the rule each rejected pack breaks
"""
import gzip
import json
import shutil
import zlib
import sys
from pathlib import Path

import knowledge_pack as K

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / 'export-contract' / 'knowledge-pack' / 'golden-v1'
FLOAT_TOLERANCE = 1e-9


def _rewrite(pack, lines, manifest_edit=None, *, update_core_hash=True, update_line_hashes=True, final_lf=True):
    lines = [line if isinstance(line, bytes) else line.encode('utf-8') for line in lines]
    data = gzip.compress(b'\n'.join(lines) + (b'\n' if final_lf and lines else b''), mtime=0)
    (pack / 'core.jsonl.gz').write_bytes(data)
    manifest = json.loads((pack / 'manifest.json').read_text(encoding='utf-8'))
    if update_core_hash:manifest['core']['sha256'] = K._sha256(data)
    if update_line_hashes:
        for entry, line in zip(manifest['presets'], lines):entry['core_line_sha256'] = K._sha256(line)
    if manifest_edit:manifest_edit(manifest)
    (pack / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')


def _lines(pack):
    return gzip.decompress((pack / 'core.jsonl.gz').read_bytes()).decode('utf-8').split('\n')[:-1]


def view(recipe):
    """The reader view every implementation exposes (FORMAT.md, "Reader view")."""
    estimate = recipe.get('display_estimate') or {}
    statistics = estimate.get('statistics') or {}
    activity = estimate.get('activity') or {}
    facets = recipe.get('facets') or {}
    intent = recipe.get('intent') or {}
    def stat(name):
        row = statistics.get(name) or {}
        return {'value': row.get('value'), 'interval': row.get('interval')}
    return {
        'name': recipe['preset']['name'], 'sha256': recipe['preset']['sha256'],
        'effects': [row.get('effect') for row in intent.get('effects') or []],
        'reactivity': [[row.get('band'), row.get('target'), row.get('kind'), row.get('response')] for row in intent.get('reactivity') or []],
        'mean_luminance': stat('mean_luminance'), 'mean_abs_frame_difference': stat('mean_abs_frame_difference'),
        'activity': activity.get('activity'), 'activity_bands': activity.get('bands') or [],
        'facet_options': facets.get('options') or [],
        'facet_values': {name: row.get('value') for name, row in sorted((facets.get('values') or {}).items())},
        'energy_tags': (intent.get('energy') or {}).get('tags') or [],
    }


def generate(out=DEFAULT):
    out = Path(out)
    recipes = sorted((out / 'recipes').glob('*.json'))
    for name in ('valid', 'unknown-fields', 'null-containers', 'bad-policy', 'bad-recipe-policy', 'bad-core-hash', 'bad-line-hash', 'bad-utf8', 'bad-field-type', 'bad-no-presets', 'bad-crlf', 'bad-final-lf', 'bad-two-members', 'bad-trailing-bytes', 'bad-header-crc'):
        shutil.rmtree(out / name, ignore_errors=True)
    K.build_from_recipes(recipes, out / 'valid', source='golden-v1 recipes')
    manifest = json.loads((out / 'valid' / 'manifest.json').read_text(encoding='utf-8'))
    # Producer and model hashes describe the build machine, not the format: pin them for stable vectors.
    manifest['producer'] = {'commit': None, 'analyzer_dirty': None}
    for key in ('calibration_model_sha256', 'activity_reference_sha256', 'facet_definition_sha256'):manifest[key] = None
    (out / 'valid' / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    lines = _lines(out / 'valid')

    for name in ('unknown-fields', 'null-containers', 'bad-policy', 'bad-recipe-policy', 'bad-core-hash', 'bad-line-hash', 'bad-utf8', 'bad-field-type', 'bad-no-presets', 'bad-crlf', 'bad-final-lf', 'bad-two-members', 'bad-trailing-bytes', 'bad-header-crc'):
        shutil.copytree(out / 'valid', out / name)
    extended = []
    for line in lines:
        recipe = json.loads(line)
        recipe['x_later_field'] = {'added_in': 'a later v1 producer', 'values': [1, 2.5, None, True]}
        recipe['intent']['x_later_hint'] = 'ignored by v1 readers'
        extended.append(json.dumps(recipe, separators=(',', ':'), sort_keys=True))
    _rewrite(out / 'unknown-fields', extended, lambda m: m.update({'x_later_manifest_field': {'note': 'ignored by v1 readers'}}))
    nulled = [json.loads(line) for line in lines]
    nulled[0]['facets'] = None; nulled[0]['display_estimate']['activity'] = None; nulled[0]['intent']['reactivity'] = None
    nulled[1]['display_estimate'] = None; nulled[1]['intent']['energy'] = None
    nulled = [json.dumps(recipe, separators=(',', ':'), sort_keys=True) for recipe in nulled]
    _rewrite(out / 'null-containers', nulled)
    _rewrite(out / 'bad-policy', lines, lambda m: m.update({'policy': 'preset-knowledge-pack-v2'}))
    changed = json.loads(lines[0]); changed['policy'] = 'preset-visual-recipe-v2'
    _rewrite(out / 'bad-recipe-policy', [json.dumps(changed, separators=(',', ':'), sort_keys=True)] + lines[1:])
    # Same lines, different gzip stream (compression level 1): bytes no longer match core.sha256.
    (out / 'bad-core-hash' / 'core.jsonl.gz').write_bytes(gzip.compress(('\n'.join(lines) + '\n').encode('utf-8'), compresslevel=1, mtime=0))
    tampered = json.loads(lines[-1]); tampered['intent']['effects'] = []
    _rewrite(out / 'bad-line-hash', lines[:-1] + [json.dumps(tampered, separators=(',', ':'), sort_keys=True)], update_line_hashes=False)

    # A raw 0xFF byte inside a JSON string: hash-valid bytes that are not UTF-8.
    first = lines[0].encode('utf-8')
    marker = b'"description":"'
    cut = first.index(marker) + len(marker)
    _rewrite(out / 'bad-utf8', [first[:cut] + b'\xff' + first[cut:]] + lines[1:])
    typed = json.loads(lines[1]); typed['intent']['effects'][0]['effect'] = 5
    _rewrite(out / 'bad-field-type', [lines[0], json.dumps(typed, separators=(',', ':'), sort_keys=True)] + lines[2:])
    _rewrite(out / 'bad-no-presets', [], lambda m: (m.pop('presets'), m['counts'].update(presets=0)))
    _rewrite(out / 'bad-crlf', [line.encode('utf-8') + b'\r' for line in lines])
    _rewrite(out / 'bad-final-lf', lines, final_lf=False)
    valid_core = (out / 'valid' / 'core.jsonl.gz').read_bytes()
    header = bytes([valid_core[0], valid_core[1], valid_core[2], valid_core[3] | 2]) + valid_core[4:10]
    wrong_crc = (zlib.crc32(header) & 0xffff) ^ 0xffff
    for name, data in (('bad-header-crc', header + wrong_crc.to_bytes(2, 'little') + valid_core[10:]),
                       ('bad-two-members', b''.join(gzip.compress(line.encode('utf-8') + b'\n', mtime=0) for line in lines)),
                       ('bad-trailing-bytes', (out / 'valid' / 'core.jsonl.gz').read_bytes() + b'\x00trailing')):
        (out / name / 'core.jsonl.gz').write_bytes(data)
        manifest = json.loads((out / name / 'manifest.json').read_text(encoding='utf-8'))
        manifest['core']['sha256'] = K._sha256(data)
        (out / name / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')

    expected = {
        'format': K.PACK_POLICY, 'recipe_policy': K.RECIPE_POLICY, 'float_tolerance': FLOAT_TOLERANCE,
        'accept': {'valid': [view(json.loads(line)) for line in lines], 'unknown-fields': [view(json.loads(line)) for line in lines],
                   'null-containers': [view(json.loads(line)) for line in nulled]},
        'reject': {'bad-policy': 'pack policy', 'bad-recipe-policy': 'recipe policy',
                   'bad-core-hash': 'core file hash', 'bad-line-hash': 'core line hash',
                   'bad-utf8': 'encoding', 'bad-field-type': 'recipe types',
                   'bad-no-presets': 'manifest structure', 'bad-crlf': 'line ending', 'bad-final-lf': 'line ending',
                   'bad-two-members': 'gzip', 'bad-trailing-bytes': 'gzip', 'bad-header-crc': 'gzip'},
    }
    (out / 'expected.json').write_text(json.dumps(expected, indent=1) + '\n', encoding='utf-8')
    return expected


if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    generate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
