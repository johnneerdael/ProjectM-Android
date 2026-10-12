#!/usr/bin/env python3
"""Build source-bound preset distributions; never fetch presets during a build."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile


REPO = Path(__file__).resolve().parents[1]
GENRES = ('chill', 'normal', 'intense')
BUILDER = {'format': 1, 'compression': 'deflate', 'level': 9, 'timestamp': [1980, 1, 1, 0, 0, 0]}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), REPO / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_path(name):
    if (not isinstance(name, str) or not name or name.startswith('/') or '\\' in name
            or any(p in ('', '.', '..') for p in name.split('/'))
            or ':' in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError('unsafe file path')
    return name


def source_files(root):
    assets = root / 'core/src/main/assets'
    files = {}
    for folder in ('presets', 'textures', 'preset-genres'):
        for path in (assets / folder).rglob('*'):
            if path.is_symlink(): raise ValueError('symlink in collection')
            if path.is_file(): files[safe_path(path.relative_to(assets).as_posix())] = path.read_bytes()
    files['presets.idx'] = (assets / 'presets.idx').read_bytes()
    for name in ('LICENSE', 'LICENSES/CC0-1.0.txt', 'docs/THIRD_PARTY.md'):
        files[name] = (root / name).read_bytes()
    return files


def collection_manifest(files):
    records = [{'path': name, 'bytes': len(files[name]), 'sha256': digest(files[name])}
               for name in sorted(files, key=lambda s: s.encode('utf-8'))]
    identity = digest(canonical({'schema_version': 1, 'files': records}))
    return {'schema_version': 1, 'collection_id': identity, 'files': records}


def write_archive(path, files, manifest):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = dict(files, **{'manifest.json': canonical(manifest)})
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(contents, key=lambda s: s.encode('utf-8')):
            info = zipfile.ZipInfo(name, tuple(BUILDER['timestamp']))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contents[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def archive_facts(path, files, manifest):
    return {'schema_version': 1, 'collection_id': manifest['collection_id'],
            'archive_sha256': digest(path.read_bytes()), 'compressed_bytes': path.stat().st_size,
            'expanded_bytes': sum(map(len, files.values())) + len(canonical(manifest)),
            'preset_count': sum(n.startswith('presets/') and n.endswith('.milk') for n in files),
            'texture_count': sum(n.startswith('textures/') for n in files), 'builder': BUILDER}


def lock_archive(root, output):
    root, output = Path(root), Path(output)
    files = source_files(root)
    manifest = collection_manifest(files)
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'collection.zip'
        write_archive(archive, files, manifest)
        facts = archive_facts(archive, files, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(facts))
    return facts


def texture_dependencies(texts, textures):
    generator, checks = helper('gen-preset-index'), helper('check-presets')
    images = {}
    for name in textures:
        stem = Path(name).stem.lower()
        if stem in images: raise ValueError('ambiguous texture stem')
        images[stem] = name
    needed = set()
    for text in texts:
        code = generator.shader_code(text).lower()
        aliases = dict(checks.ALIAS.findall(code))
        names = set(re.findall(r'(?:sampler|texsize)_(\w+)', code))
        for name in names:
            if name[:3] in generator.PREFIXES: name = name[3:]
            name = aliases.get(name, name)
            if name[:3] in generator.PREFIXES: name = name[3:]
            random = re.fullmatch(r'rand\d\d(?:_(\w+))?', name)
            if random:
                pool = [v for k, v in images.items() if not random[1] or k.startswith(random[1])]
                if not pool: raise ValueError('random texture pool is empty')
                needed.update(pool)
            elif name == 'state' or generator.BUILTIN.fullmatch(name):
                continue
            elif name in images:
                needed.add(images[name])
            else:
                raise ValueError('missing texture: ' + name)
        problems = checks.problems(text, set(images))
        if problems: raise ValueError('; '.join(problems))
    return needed


def starter_files(files, selection):
    if selection.get('schema_version') != 1 or selection.get('status') not in ('candidate', 'qualified'):
        raise ValueError('invalid starter selection schema/status')
    records = selection.get('presets', [])
    if len(records) != 20: raise ValueError('starter selection must contain exactly 20 presets')
    selected, folded = set(), set()
    for record in records:
        name = safe_path(record['name'])
        if '/' in name or not name.endswith('.milk') or name.casefold() in folded:
            raise ValueError('invalid or duplicate starter name')
        folded.add(name.casefold()); selected.add(name)
        if digest(files.get('presets/' + name, b'')) != record['sha256']:
            raise ValueError('starter source hash mismatch: ' + name)
    output = {'presets/' + name: files['presets/' + name] for name in selected}
    textures = [n for n in files if n.startswith('textures/')]
    dependencies = texture_dependencies([v.decode('utf-8', errors='replace') for v in output.values()], textures)
    output.update({n: files[n] for n in dependencies})
    index_names = {line.split('\t')[0] for line in files['presets.idx'].decode().splitlines()}
    if not selected <= index_names: raise ValueError('starter missing from preset index')
    def filter_index(data):
        return ''.join(line + '\n' for line in data.decode().splitlines() if line.split('\t')[0] in selected).encode()
    output['presets.idx'] = filter_index(files['presets.idx'])
    for genre in GENRES:
        name = 'preset-genres/genres/' + genre + '.idx'
        output[name] = filter_index(files[name])
    rows = [json.loads(line) for line in files['preset-genres/presets.jsonl'].decode().splitlines()]
    output['preset-genres/presets.jsonl'] = b''.join(canonical(row) for row in rows if row['preset'] in selected)
    manifest = json.loads(files['preset-genres/manifest.json'])
    manifest['source_library_sha256'] = manifest['library_sha256']
    manifest['library_sha256'] = digest(canonical([{'name': n, 'sha256': digest(files['presets/' + n])} for n in sorted(selected)]))
    manifest['texture_sha256'] = digest(canonical([{'name': n, 'sha256': digest(files[n])} for n in sorted(dependencies)]))
    manifest['total_presets'] = 20
    manifest['inactive_presets'] = sum(not r.get('group_eligible', True) for r in rows if r['preset'] in selected)
    for genre in GENRES:
        manifest['groups'][genre]['count'] = len(output['preset-genres/genres/' + genre + '.idx'].splitlines())
    manifest['checksums'] = {n.removeprefix('preset-genres/'): digest(data) for n, data in output.items() if n.startswith('preset-genres/')}
    output['preset-genres/manifest.json'] = canonical(manifest)
    output['starter-selection.json'] = canonical(selection)
    return output


def build_distribution(root, selection, output, release_tag, build_archive=False):
    root, selection, output = Path(root), Path(selection), Path(output)
    if not re.fullmatch(r'v\d+\.\d+\.\d+', release_tag): raise ValueError('invalid stable release tag')
    files = source_files(root)
    manifest = collection_manifest(files)
    lock = json.loads((root / 'tools/preset-distribution/official-archive.json').read_text())
    if lock.get('schema_version') != 1 or lock.get('builder') != BUILDER or lock.get('collection_id') != manifest['collection_id']:
        raise ValueError('collection identity differs from archive lock; regenerate lock-archive')
    if not re.fullmatch('[0-9a-f]{64}', str(lock.get('archive_sha256', ''))) or lock.get('compressed_bytes', 0) <= 0:
        raise ValueError('invalid archive lock')
    expected_expanded = sum(map(len, files.values())) + len(canonical(manifest))
    if lock.get('expanded_bytes') != expected_expanded or lock.get('preset_count') != sum(n.startswith('presets/') and n.endswith('.milk') for n in files) or lock.get('texture_count') != sum(n.startswith('textures/') for n in files):
        raise ValueError('archive lock counts/sizes differ')
    starters = starter_files(files, json.loads(selection.read_text()))
    descriptor = {k: v for k, v in lock.items() if k != 'builder'}
    archive_name = 'cream-of-the-crop-' + release_tag[1:] + '.zip'
    descriptor['archive_url'] = 'https://github.com/johnneerdael/ProjectM-Android/releases/download/' + release_tag + '/' + archive_name
    starters['official-pack.json'] = canonical(descriptor)
    assets = output / 'starter-assets'
    output.mkdir(parents=True, exist_ok=True)
    # The task exclusively owns this output directory; never mutate source assets.
    with tempfile.TemporaryDirectory(dir=output, prefix='starter-stage-') as temporary:
        staging = Path(temporary)
        for name, content in starters.items():
            target = staging / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
        if assets.exists(): shutil.rmtree(assets)
        shutil.copytree(staging, assets)
    archive = None
    if build_archive:
        archive = output / archive_name
        write_archive(archive, files, manifest)
        if archive_facts(archive, files, manifest) != lock:
            archive.unlink()
            raise ValueError('archive bytes differ from committed lock; verify builder toolchain')
    return {'starter_assets': assets, 'archive': archive, 'descriptor': descriptor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    lock = sub.add_parser('lock-archive'); lock.add_argument('--root', type=Path, required=True); lock.add_argument('--output', type=Path, required=True)
    build = sub.add_parser('build'); build.add_argument('--root', type=Path, required=True); build.add_argument('--selection', type=Path, required=True); build.add_argument('--output', type=Path, required=True); build.add_argument('--release-tag', required=True); build.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.action == 'lock-archive': print(json.dumps(lock_archive(args.root, args.output), sort_keys=True))
    else:
        result = build_distribution(args.root, args.selection, args.output, args.release_tag, args.archive)
        print(json.dumps(result, default=str, sort_keys=True))


if __name__ == '__main__': main()
