"""Versioned preset knowledge pack: source-only recipes for a whole preset collection, for applications.

Build from a corpus_understanding.py run (its results keep each preset's full understanding summary):

    python knowledge_pack.py build <corpus-run-dir> <pack-dir> [--with-programs] [--workers 8]
    python knowledge_pack.py check <pack-dir> [--presets <presets-dir>]

Layout of <pack-dir>:
    manifest.json      pack identity: versions, hashes, producer commit, counts
    core.jsonl.gz      one recipe per line (sorted by preset name); expression/program graphs removed
    full/<sha256>.json.gz   complete recipes with programs (only with --with-programs)

Every core line validates against export-contract/preset-recipe.schema.json and manifest.json against
export-contract/knowledge-pack-manifest.schema.json. `check` re-validates both, recomputes the file hashes and, with --presets, verifies every preset name and sha256 against
the collection. Consumers read it with load_core(pack_dir).
"""
import argparse
import base64
import gzip
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PACK_POLICY = 'preset-knowledge-pack-v1'
HERE = Path(__file__).resolve().parent
# Recipe keys holding serialised expression/program graphs: kept only in the full layer.
GRAPH_KEYS = {'expression', 'expressions', 'programs', 'time_expression', 'frame_expression', 'terms',
              'control_expressions', 'frame_recurrence', 'point_recurrence', 'program'}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def core_recipe(recipe):
    """The recipe without serialised graphs (same contract; graphs are optional fields)."""
    if isinstance(recipe, dict):
        return {k: core_recipe(v) for k, v in recipe.items() if k not in GRAPH_KEYS}
    if isinstance(recipe, list):
        return [core_recipe(v) for v in recipe]
    return recipe


def _recipe_from_result(path):
    from preset_recipe import build_recipe
    from contract_schema import recipe_errors
    row = json.loads(Path(path).read_text())
    if row.get('status') != 'computed' or not row.get('summary_gzip_base64'):
        return row.get('name'), row.get('sha256'), None, 'status ' + str(row.get('status'))
    summary = json.loads(gzip.decompress(base64.b64decode(row['summary_gzip_base64'])))
    try:
        recipe = build_recipe(summary)
    except Exception as error:  # noqa: BLE001 - recorded per preset, the pack still builds
        return row.get('name'), row.get('sha256'), None, 'recipe failed: ' + str(error)[:200]
    problems = recipe_errors(recipe)
    if problems:
        return row.get('name'), row.get('sha256'), None, 'schema: ' + '; '.join(problems[:3])
    return row.get('name'), row.get('sha256'), recipe, None


def _producer_commit():
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=HERE, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--', str(HERE)], cwd=HERE, capture_output=True, text=True).stdout.strip())
        return {'commit': commit or None, 'analyzer_dirty': dirty}
    except OSError:
        return {'commit': None, 'analyzer_dirty': None}


def _file_hash(path):
    return _sha256(Path(path).read_bytes()) if Path(path).exists() else None


def build(corpus_dir, pack_dir, *, with_programs=False, workers=8):
    corpus_dir, pack_dir = Path(corpus_dir), Path(pack_dir)
    pack_dir.mkdir(parents=True, exist_ok=True)
    results = sorted((corpus_dir / 'results').glob('*.json'))
    failures, rows = {}, []
    if with_programs:(pack_dir / 'full').mkdir(exist_ok=True)
    # Stream: full recipes are written as they arrive; only the compact core lines stay in memory.
    with ProcessPoolExecutor(workers) as pool:
        for name, sha, recipe, problem in pool.map(_recipe_from_result, results, chunksize=4):
            if recipe is None:failures[name or '?'] = problem;continue
            rows.append(_row(pack_dir, name, sha, recipe, with_programs))
    run_manifest = corpus_dir / 'run-manifest.json'
    return _write(pack_dir, rows, failures, {'directory': corpus_dir.name, 'run_manifest_sha256': _file_hash(run_manifest)},
                  with_programs)


def _row(pack_dir, name, sha, recipe, with_programs):
    # ASCII JSON (non-ASCII escaped), sorted keys, no spaces: one line per recipe.
    line = json.dumps(core_recipe(recipe), separators=(',', ':'), sort_keys=True)
    entry = {'name': name, 'sha256': sha, 'core_line_sha256': _sha256(line.encode('utf-8'))}
    if with_programs:
        full = json.dumps(recipe, separators=(',', ':'), sort_keys=True).encode('utf-8')
        (pack_dir / 'full' / (sha + '.json.gz')).write_bytes(gzip.compress(full, mtime=0))
        entry['full_sha256'] = _sha256(full)
    return name, line, entry


def build_from_recipes(recipe_paths, pack_dir, *, source='recipes'):
    """Pack from finished recipe JSON files (golden reader vectors, small collections)."""
    pack_dir = Path(pack_dir); pack_dir.mkdir(parents=True, exist_ok=True)
    from contract_schema import recipe_errors
    rows, failures = [], {}
    for path in recipe_paths:
        recipe = json.loads(Path(path).read_text(encoding='utf-8'))
        problems = recipe_errors(recipe)
        if problems:failures[recipe.get('preset', {}).get('name', str(path))] = 'schema: ' + '; '.join(problems[:3]);continue
        rows.append(_row(pack_dir, recipe['preset']['name'], recipe['preset']['sha256'], recipe, False))
    return _write(pack_dir, rows, failures, {'directory': source, 'run_manifest_sha256': None}, False)


def _write(pack_dir, rows, failures, corpus_run, with_programs):
    rows.sort(key=lambda row: row[0])
    entries = [entry for _, _, entry in rows]
    core_bytes = gzip.compress(('\n'.join(line for _, line, _ in rows) + '\n').encode('utf-8'), mtime=0)
    (pack_dir / 'core.jsonl.gz').write_bytes(core_bytes)
    manifest = {
        'policy': PACK_POLICY,
        'recipe_policy': RECIPE_POLICY,
        'schema': {'file': 'export-contract/preset-recipe.schema.json', 'sha256': _file_hash(HERE / 'export-contract/preset-recipe.schema.json')},
        'producer': _producer_commit(),
        'corpus_run': corpus_run,
        'calibration_model_sha256': _file_hash(HERE / 'fixtures/calibrated-display-model.json.gz'),
        'activity_reference_sha256': _file_hash(HERE / 'fixtures/display-activity-reference-v1.json'),
        'facet_definition_sha256': _file_hash(HERE / 'facets/facets-v1.json'),
        'counts': {'presets': len(entries), 'failed': len(failures)},
        'core': {'file': 'core.jsonl.gz', 'sha256': _sha256(core_bytes), 'graphs_removed': sorted(GRAPH_KEYS)},
        'full': {'directory': 'full', 'present': with_programs},
        'presets': entries,
        'failures': failures,
        'uses_rendered_images': False,
        'note': 'Source-only recipes; display_estimate/facets are calibrated estimates, not measurements.',
    }
    (pack_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    return manifest


def _decode(data, what):
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('encoding: %s is not valid UTF-8 (%s)' % (what, error.reason))


def _one_gzip_member(data):
    """Decompressed bytes of exactly one gzip member; extra members or trailing bytes are an error."""
    import zlib
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        text = inflater.decompress(data) + inflater.flush()
    except zlib.error as error:
        raise ValueError('gzip: core is not a valid gzip stream (%s)' % error)
    if not inflater.eof or inflater.unused_data:raise ValueError('gzip: core must be exactly one gzip member with no trailing bytes')
    return text


def _core_lines(pack_dir):
    """(manifest, stored core lines as bytes) after the policy and core file hash checks."""
    pack_dir = Path(pack_dir)
    manifest = json.loads(_decode((pack_dir / 'manifest.json').read_bytes(), 'manifest.json'))
    if manifest.get('policy') != PACK_POLICY:raise ValueError('unsupported pack policy %r' % manifest.get('policy'))
    data = (pack_dir / manifest['core']['file']).read_bytes()
    if _sha256(data) != manifest['core']['sha256']:raise ValueError('core file hash mismatch')
    text = _one_gzip_member(data)
    if text and not text.endswith(b'\n'):raise ValueError('line ending: the last core line has no terminating LF')
    lines = [line for line in text.split(b'\n') if line]
    if any(line.endswith(b'\r') for line in lines):raise ValueError('line ending: core lines end in CR LF, not LF')
    return manifest, lines


RECIPE_POLICY = 'preset-visual-recipe-v1'
_TEXT, _NUMBER = (str, type(None)), (int, float, type(None))


def _check_view_types(recipe, name):
    """Reader-view fields must have their JSON types (FORMAT.md rule 7); other fields are free."""
    def fail(path):raise ValueError('recipe types: %s: %s has the wrong JSON type' % (name, path))
    def obj(value, path):
        if value is None:return {}
        if not isinstance(value, dict):fail(path)
        return value
    def rows(value, path):
        if value is None:return []
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):fail(path)
        return value
    def texts(value, path):
        if value is not None and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):fail(path)
    def number(value, path):
        if isinstance(value, bool) or not isinstance(value, _NUMBER):fail(path)
    preset = obj(recipe.get('preset'), 'preset')
    if not isinstance(preset.get('name'), str) or not isinstance(preset.get('sha256'), str):fail('preset.name/sha256')
    intent = obj(recipe.get('intent'), 'intent')
    for row in rows(intent.get('effects'), 'intent.effects'):
        if not isinstance(row.get('effect'), str) or not isinstance(row.get('stage'), _TEXT):fail('intent.effects[].effect/stage')
    for row in rows(intent.get('reactivity'), 'intent.reactivity'):
        if not all(isinstance(row.get(k), _TEXT) for k in ('band', 'target', 'kind', 'response')):fail('intent.reactivity[]')
    texts(obj(intent.get('energy'), 'intent.energy').get('tags'), 'intent.energy.tags')
    estimate = obj(recipe.get('display_estimate'), 'display_estimate')
    statistics = obj(estimate.get('statistics'), 'display_estimate.statistics')
    for key in ('mean_luminance', 'mean_abs_frame_difference'):
        row = obj(statistics.get(key), 'display_estimate.statistics.' + key)
        number(row.get('value'), key + '.value')
        interval = row.get('interval')
        if interval is not None and (not isinstance(interval, list) or len(interval) != 2):fail(key + '.interval')
        for bound in interval or []:
            if bound is None:fail(key + '.interval')
            number(bound, key + '.interval')
    activity = obj(estimate.get('activity'), 'display_estimate.activity')
    number(activity.get('activity'), 'display_estimate.activity.activity')
    texts(activity.get('bands'), 'display_estimate.activity.bands')
    facets = obj(recipe.get('facets'), 'facets')
    texts(facets.get('options'), 'facets.options')
    for key, row in obj(facets.get('values'), 'facets.values').items():number(obj(row, 'facets.values.' + key).get('value'), 'facets.values.' + key)


def load_core(pack_dir):
    """{preset name: core recipe}: the reference reader. Applies every rule of
    export-contract/knowledge-pack/FORMAT.md that a reader in another language must apply."""
    manifest, lines = _core_lines(pack_dir)
    if manifest.get('recipe_policy') != RECIPE_POLICY:raise ValueError('unsupported recipe policy %r' % manifest.get('recipe_policy'))
    entries = manifest.get('presets')
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ValueError('manifest structure: presets must be an array of objects')
    if len(entries) != len(lines):raise ValueError('manifest lists %d presets, core holds %d lines' % (len(entries), len(lines)))
    recipes = {}
    for entry, line in zip(entries, lines):
        if _sha256(line) != entry.get('core_line_sha256'):raise ValueError(entry.get('name', '?') + ': core line hash mismatch')
        recipe = json.loads(_decode(line, entry.get('name', '?')))
        if recipe.get('policy') != RECIPE_POLICY:raise ValueError(entry['name'] + ': unsupported recipe policy %r' % recipe.get('policy'))
        _check_view_types(recipe, entry['name'])
        preset = recipe.get('preset') or {}
        if preset.get('name') != entry['name'] or preset.get('sha256') != entry['sha256']:raise ValueError(entry['name'] + ': recipe identity differs from the manifest')
        recipes[entry['name']] = recipe
    return recipes


def check(pack_dir, presets_dir=None):
    """List of problems (empty when the pack is consistent)."""
    from contract_schema import recipe_errors
    pack_dir = Path(pack_dir)
    problems = []
    try:
        manifest, lines = _core_lines(pack_dir)
        recipes = {}
        for line in lines:
            recipe = json.loads(_decode(line, 'core line'));recipes[recipe['preset']['name']] = (recipe, line)
    except (OSError, ValueError, KeyError) as error:
        return [str(error)]
    from contract_schema import errors, load_schema
    problems += ['manifest: ' + p for p in errors(manifest, load_schema('knowledge-pack-manifest.schema.json'))]
    if manifest['schema']['sha256'] != _file_hash(HERE / manifest['schema']['file']):
        problems.append('schema changed since the pack was built')
    entries = {e['name']: e for e in manifest['presets']}
    if set(entries) != set(recipes):problems.append('manifest and core list different presets')
    if [e['name'] for e in manifest['presets']] != [name for name in recipes]:problems.append('core lines are not in manifest order')
    for name, (recipe, line) in recipes.items():
        entry = entries.get(name) or {}
        # The hash covers the stored UTF-8 line, so any reader can verify it without re-serialising.
        if _sha256(line) != entry.get('core_line_sha256'):problems.append(name + ': core line hash mismatch')
        if recipe['preset']['sha256'] != entry.get('sha256'):problems.append(name + ': preset sha256 mismatch')
        for problem in recipe_errors(recipe)[:2]:problems.append(name + ': ' + problem)
    if presets_dir is not None:
        for name, entry in entries.items():
            path = Path(presets_dir) / name
            if not path.exists():problems.append(name + ': not in the collection')
            elif _sha256(path.read_bytes()) != entry['sha256']:problems.append(name + ': preset bytes changed')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build');b.add_argument('corpus');b.add_argument('pack')
    b.add_argument('--with-programs', action='store_true');b.add_argument('--workers', type=int, default=8)
    c = sub.add_parser('check');c.add_argument('pack');c.add_argument('--presets')
    args = parser.parse_args(argv)
    if args.command == 'build':
        manifest = build(args.corpus, args.pack, with_programs=args.with_programs, workers=args.workers)
        print(json.dumps(manifest['counts']))
        return 0
    problems = check(args.pack, args.presets)
    for problem in problems[:50]:print(problem)
    print('ok' if not problems else '%d problems' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    raise SystemExit(main())
