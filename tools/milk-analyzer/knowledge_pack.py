"""Versioned preset knowledge pack: source-only recipes for a whole preset collection, for applications.

Build from a corpus_understanding.py run (its results keep each preset's full understanding summary):

    python knowledge_pack.py build <corpus-run-dir> <pack-dir> [--with-programs] [--workers 8]
    python knowledge_pack.py check <pack-dir> [--presets <presets-dir>]

Layout of <pack-dir>:
    manifest.json      pack identity: versions, hashes, producer commit, counts
    core.jsonl.gz      one recipe per line (sorted by preset name); expression/program graphs removed
    full/<sha256>.json.gz   complete recipes with programs (only with --with-programs)

Every core line validates against export-contract/preset-recipe.schema.json. `check` re-validates the
lines, recomputes the file hashes and, with --presets, verifies every preset name and sha256 against
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
    rows, failures = [], {}
    with ProcessPoolExecutor(workers) as pool:
        for name, sha, recipe, problem in pool.map(_recipe_from_result, results, chunksize=4):
            if recipe is None:failures[name or '?'] = problem;continue
            rows.append((name, sha, recipe))
    rows.sort(key=lambda row: row[0])
    entries = []
    core_lines = []
    if with_programs:(pack_dir / 'full').mkdir(exist_ok=True)
    for name, sha, recipe in rows:
        line = json.dumps(core_recipe(recipe), separators=(',', ':'), sort_keys=True)
        core_lines.append(line)
        entry = {'name': name, 'sha256': sha, 'core_line_sha256': _sha256(line.encode())}
        if with_programs:
            full = json.dumps(recipe, separators=(',', ':'), sort_keys=True).encode()
            target = pack_dir / 'full' / (sha + '.json.gz')
            target.write_bytes(gzip.compress(full, mtime=0))
            entry['full_sha256'] = _sha256(full)
        entries.append(entry)
    core_bytes = gzip.compress(('\n'.join(core_lines) + '\n').encode(), mtime=0)
    (pack_dir / 'core.jsonl.gz').write_bytes(core_bytes)
    run_manifest = corpus_dir / 'run-manifest.json'
    manifest = {
        'policy': PACK_POLICY,
        'recipe_policy': 'preset-visual-recipe-v1',
        'schema': {'file': 'export-contract/preset-recipe.schema.json', 'sha256': _file_hash(HERE / 'export-contract/preset-recipe.schema.json')},
        'producer': _producer_commit(),
        'corpus_run': {'directory': corpus_dir.name, 'run_manifest_sha256': _file_hash(run_manifest)},
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


def load_core(pack_dir):
    """{preset name: core recipe} after checking the pack policy and core hash."""
    pack_dir = Path(pack_dir)
    manifest = json.loads((pack_dir / 'manifest.json').read_text())
    if manifest.get('policy') != PACK_POLICY:raise ValueError('unsupported pack policy %r' % manifest.get('policy'))
    data = (pack_dir / manifest['core']['file']).read_bytes()
    if _sha256(data) != manifest['core']['sha256']:raise ValueError('core file hash mismatch')
    recipes = [json.loads(line) for line in gzip.decompress(data).decode().splitlines() if line]
    return {recipe['preset']['name']: recipe for recipe in recipes}


def check(pack_dir, presets_dir=None):
    """List of problems (empty when the pack is consistent)."""
    from contract_schema import recipe_errors
    pack_dir = Path(pack_dir)
    problems = []
    try:
        manifest = json.loads((pack_dir / 'manifest.json').read_text())
        recipes = load_core(pack_dir)
    except (OSError, ValueError, KeyError) as error:
        return [str(error)]
    if manifest['schema']['sha256'] != _file_hash(HERE / manifest['schema']['file']):
        problems.append('schema changed since the pack was built')
    entries = {e['name']: e for e in manifest['presets']}
    if set(entries) != set(recipes):problems.append('manifest and core list different presets')
    for name, recipe in recipes.items():
        entry = entries.get(name) or {}
        line = json.dumps(recipe, separators=(',', ':'), sort_keys=True)
        if _sha256(line.encode()) != entry.get('core_line_sha256'):problems.append(name + ': core line hash mismatch')
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
