"""Mood facet attribute bundle: engine-ruler measurements + source style facts -> Android assets.

build() writes preset-attributes/{facets.json, attributes.tsv, manifest.json} after verifying the ruler
results against the evidence manifest in both directions and the bundled preset bytes against its preset
hashes; check() verifies the bundle against presets.idx, the definition, its frozen activity reference,
its manifest, the evidence manifest and the bundled preset bytes, and recomputes every membership from
the stored values and style options. Activity is scored against the
frozen reference (facets/activity-reference-v1.json, written once by --freeze-activity-reference),
never against the corpus of the current build. Standard library only.
"""
import argparse, bisect, hashlib, json, shutil
from pathlib import Path

import preset_facets

COLUMNS = ('luminance', 'saturation', 'coloured_share', 'warm_cool', 'flow', 'frame_difference', 'jumps', 'activity')
RULER_FIELDS = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'coloured_share': 'coloured_share',
                'warm_cool': 'warm_cool', 'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference',
                'jumps': 'global_brightness_jumps_per_10s'}
ACTIVITY_METRICS = ('mean_abs_frame_difference', 'mean_flow_screen_widths_per_s', 'global_brightness_jumps_per_10s')
STYLES = {'kaleidoscope', 'tunnel', 'liquid', 'geometric', 'particles', 'fractal'}
SCHEMA = 'projectm-tv-preset-attributes'
MANIFEST_VERSION = 1
REFERENCE_SCHEMA = 'projectm-tv-activity-reference'
QUANTILES = 1001


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _mid_rank(sorted_values, value):
    low = bisect.bisect_left(sorted_values, value); high = bisect.bisect_right(sorted_values, value)
    return (low + high) / 2 / len(sorted_values)


def _quantiles(values, count=QUANTILES):
    """count evenly spaced quantiles (0..1) with linear interpolation between order statistics."""
    ordered = sorted(float(v) for v in values)
    last = len(ordered) - 1; table = []
    for i in range(count):
        h = last * i / (count - 1); low = int(h); high = min(low + 1, last)
        table.append(ordered[low] + (h - low) * (ordered[high] - ordered[low]))
    return table


def _mean_rank(reference, row):
    return sum(_mid_rank(reference['metrics'][m], float(row[m])) for m in ACTIVITY_METRICS) / len(ACTIVITY_METRICS)


def make_activity_reference(rows, provenance):
    """The frozen activity reference: quantile tables of the three metrics and of their mean rank."""
    reference = {'schema': REFERENCE_SCHEMA, 'version': 1, 'quantiles': QUANTILES,
                 'description': 'activity = mid-rank of the mean of the three metric mid-ranks, each looked up in these '
                                'frozen quantile tables; not recomputed per release',
                 'provenance': provenance,
                 'metrics': {m: _quantiles(float(r[m]) for r in rows) for m in ACTIVITY_METRICS}}
    reference['mean_rank'] = _quantiles(_mean_rank(reference, r) for r in rows)
    return reference


def activity_values(rows, reference):
    """Activity percentile of each row against the frozen reference (independent of the other rows)."""
    return {r['preset']: _mid_rank(reference['mean_rank'], _mean_rank(reference, r)) for r in rows}


def _reference_path(definition, definition_path):
    return Path(definition_path).parent / definition['activity_reference']['file']


def load_activity_reference(definition, definition_path):
    """Reads the reference the definition names; raises ValueError when its hash differs."""
    data = _reference_path(definition, definition_path).read_bytes()
    if _sha(data) != definition['activity_reference']['sha256']:
        raise ValueError('activity reference differs from the hash in the definition')
    return json.loads(data)


def _measured_rows(ruler_dir):
    rows = {}; ruler = None
    for path in sorted(Path(ruler_dir).glob('*.json')):
        row = json.loads(path.read_text())
        if row.get('status') != 'measured':
            continue
        # warm_cool is None (undefined) when a preset shows no coloured pixels; every other field is required
        missing = [f for f in RULER_FIELDS.values() if type(row.get(f)) not in (int, float) and not (f == 'warm_cool' and row.get(f) is None and f in row)]
        if missing:
            raise ValueError('ruler result %s lacks %s' % (row.get('preset'), missing))
        rows[row['preset']] = row; ruler = ruler or row.get('ruler')
    return rows, ruler


def evidence_metrics(result):
    """The seven ruler values of a measured result as the bundle stores them before activity (4 decimals, '-' for none)."""
    return {k: _format(result[f]) for k, f in RULER_FIELDS.items()}


def evidence_activity_inputs(result):
    """The three unrounded activity inputs of a measured result (activity is scored from these, not the 4-decimal columns)."""
    return {k: result[f] for k, f in (('frame_difference', 'mean_abs_frame_difference'), ('flow', 'mean_flow_screen_widths_per_s'),
                                      ('jumps', 'global_brightness_jumps_per_10s'))}


def _activity_input(inputs):
    """Activity-metric row built from evidence activity_inputs, keyed as the reference expects."""
    return {'mean_abs_frame_difference': float(inputs['frame_difference']), 'mean_flow_screen_widths_per_s': float(inputs['flow']),
            'global_brightness_jumps_per_10s': float(inputs['jumps'])}


EVIDENCE_POLICY = 'engine-ruler-results-manifest-v2'


def write_evidence_manifest(ruler_dir, source_manifest, output):
    """Rewrites the evidence manifest with a `metrics` object per measured row, derived from the ruler results.

    All other fields are kept; each row's result hash must still match its result file."""
    manifest = json.loads(Path(source_manifest).read_text())
    results = {}
    for path in sorted(Path(ruler_dir).glob('*.json')):
        raw = path.read_bytes(); row = json.loads(raw)
        if row.get('status') == 'measured':
            results[row['preset']] = (row, _sha(raw))
    for entry in manifest['rows']:
        if entry.get('status') != 'measured':
            entry.pop('metrics', None); continue
        row, digest = results.get(entry['preset'], (None, None))
        if row is None or digest != entry.get('result_sha256'):
            raise ValueError('%s: no measured result matching the manifest result_sha256' % entry['preset'])
        entry['metrics'] = evidence_metrics(row); entry['activity_inputs'] = evidence_activity_inputs(row)
    manifest['policy'] = EVIDENCE_POLICY
    Path(output).write_text(json.dumps(manifest, indent=0) + '\n')


def _manifest_entries(ruler_manifest):
    """Evidence manifest rows by preset; a preset listed twice is rejected."""
    rows = json.loads(Path(ruler_manifest).read_text()).get('rows', [])
    entries = {r['preset']: r for r in rows}
    if len(entries) != len(rows):
        raise ValueError('ruler results manifest lists a preset more than once')
    return entries


def _presets_dir(presets_idx, presets_dir):
    return Path(presets_dir) if presets_dir is not None else Path(presets_idx).parent / 'presets'


def preset_asset_problems(names, entries, presets_dir):
    """Every named preset with a measured evidence row must still have the bytes the ruler measured."""
    problems = []
    for name in names:
        entry = entries.get(name)
        if entry is None or entry.get('status') != 'measured':
            continue
        try:
            data = (Path(presets_dir) / name).read_bytes()
        except OSError:
            problems.append('%s: preset asset missing from %s' % (name, presets_dir)); continue
        if _sha(data) != entry.get('preset_sha256'):
            problems.append('%s: preset asset differs from the evidence preset_sha256' % name)
    return problems


def verify_against_manifest(ruler_dir, ruler_manifest, presets_idx, presets_dir=None):
    """Two-way check of the ruler results against the evidence manifest, then of the measured bytes.

    Every measured result file must be a row of the manifest (same preset, result and preset hashes);
    every manifest row marked measured must have exactly one measured result file; neither may name a
    preset absent from presets.idx; and every preset in
    presets.idx with a measured row must still have the measured bytes in presets_dir (default:
    presets/ next to presets.idx)."""
    entries = _manifest_entries(ruler_manifest)
    indexed = set(_index_names(presets_idx))
    problems = ['%s: manifest row is not in presets.idx' % n for n, e in sorted(entries.items())
                if e.get('status') == 'measured' and n not in indexed]
    consumed = {}
    for path in sorted(Path(ruler_dir).glob('*.json')):
        raw = path.read_bytes(); row = json.loads(raw)
        if row.get('status') != 'measured':
            continue
        name = row.get('preset'); consumed[name] = consumed.get(name, 0) + 1
        if name not in indexed:
            problems.append('%s: measured result is not in presets.idx' % name)
        entry = entries.get(name)
        if entry is None:
            problems.append('%s: not in the evidence manifest' % name)
        elif entry.get('status') != 'measured':
            problems.append('%s: measured result but the manifest status is %r' % (name, entry.get('status')))
        elif entry.get('result_sha256') != _sha(raw):
            problems.append('%s: result differs from the manifest result_sha256' % name)
        elif entry.get('preset_sha256') != row.get('preset_sha256'):
            problems.append('%s: preset_sha256 differs from the manifest' % name)
        elif entry.get('metrics') != evidence_metrics(row) or entry.get('activity_inputs') != evidence_activity_inputs(row):
            problems.append('%s: result metrics differ from the manifest metrics' % name)
    for name, entry in sorted(entries.items()):
        if entry.get('status') == 'measured' and consumed.get(name, 0) != 1:
            problems.append('%s: manifest row is measured but %d measured result files match it' % (name, consumed.get(name, 0)))
    problems += preset_asset_problems(_index_names(presets_idx), entries, _presets_dir(presets_idx, presets_dir))
    if problems:
        raise ValueError('ruler results do not match the evidence manifest (%d): %s' % (len(problems), '; '.join(problems[:5])))


def freeze_activity_reference(ruler_dir, output, ruler_manifest, presets_idx, presets_dir=None):
    """Writes the activity reference once from the verified measured corpus; returns its sha256."""
    verify_against_manifest(ruler_dir, ruler_manifest, presets_idx, presets_dir)
    rows, ruler = _measured_rows(ruler_dir)
    provenance = {'ruler': ruler, 'preset_count': len(rows),
                  'ruler_results_manifest_sha256': _sha(Path(ruler_manifest).read_bytes())}
    data = (json.dumps(make_activity_reference(list(rows.values()), provenance), indent=1, sort_keys=True) + '\n').encode()
    Path(output).write_bytes(data)
    return _sha(data)


def _index_names(presets_idx):
    names = [line.split('\t', 1)[0] for line in Path(presets_idx).read_text().splitlines() if line.strip()]
    if len(names) != len(set(names)):
        raise ValueError('duplicate names in presets.idx')
    return names


def _read_style(path):
    lines = Path(path).read_text().splitlines()
    if not lines or not lines[0].startswith('#projectm-tv-facet-style-facts\t1'):
        raise ValueError('style facts header missing')
    styles, digests, duplicates = {}, {}, []
    for line in lines[1:]:
        name, digest, found = line.split('\t')
        if name in styles:
            duplicates.append(name)
        digests[name] = digest
        values = {s for s in found.split(',') if s}
        if values - STYLES:
            raise ValueError('unknown style in %s: %s' % (name, sorted(values - STYLES)))
        styles[name] = values
    if duplicates:
        raise ValueError('style facts list a preset more than once: %s' % sorted(set(duplicates))[:5])
    return lines[0], styles, digests


def style_problems(names, digests, presets_dir):
    """Exactly one style row per indexed preset, each hashed from the preset bytes it was derived from."""
    problems = []
    for name in names:
        if name not in digests:
            problems.append('%s: no style facts row' % name); continue
        try:
            data = (Path(presets_dir) / name).read_bytes()
        except OSError:
            problems.append('%s: preset asset missing from %s' % (name, presets_dir)); continue
        if _sha(data) != digests[name]:
            problems.append('%s: style facts were derived from different preset bytes' % name)
    problems += ['%s: style facts row for a preset not in presets.idx' % n for n in sorted(set(digests) - set(names))]
    return problems


def _format(value):
    return '-' if value is None else '%.4f' % value


def _header(definition, definition_sha):
    lines = ['#%s\t1' % SCHEMA, '#definition\t' + definition_sha]
    for group in definition['groups']:
        lines.append('#group\t%s\t%s' % (group['id'], group['label']))
        lines += ['#option\t%s\t%s\t%s' % (group['id'], o['id'], o['label']) for o in group['options']]
    lines.append('#columns\tname\toptions\t' + '\t'.join(COLUMNS))
    return lines


def build(ruler_dir, style_tsv, presets_idx, output_dir, definition_path=None, ruler_manifest=None, presets_dir=None):
    if ruler_manifest is None:
        raise ValueError('a ruler results manifest (evidence) is required to build')
    verify_against_manifest(ruler_dir, ruler_manifest, presets_idx, presets_dir)
    definition_path = Path(definition_path or preset_facets.DEFINITION)
    definition_bytes = definition_path.read_bytes(); definition = json.loads(definition_bytes)
    reference = load_activity_reference(definition, definition_path)
    names = _index_names(presets_idx)
    rows, ruler = _measured_rows(ruler_dir)
    style_header, styles, style_digests = _read_style(style_tsv)
    problems = style_problems(names, style_digests, _presets_dir(presets_idx, presets_dir))
    if problems:
        raise ValueError('style facts do not match the current presets (%d): %s' % (len(problems), '; '.join(problems[:5])))
    measured = [rows[n] for n in names if n in rows]
    activity = {n: _mid_rank(reference['mean_rank'], _mean_rank(reference, _activity_input(evidence_activity_inputs(rows[n]))))
                for n in names if n in rows}
    lines = _header(definition, _sha(definition_bytes))
    counts = {o: 0 for o in preset_facets.option_ids(definition)}
    for name in sorted(names):
        if name in rows:
            values = {k: float(rows[name][f]) for k, f in RULER_FIELDS.items() if rows[name][f] is not None}; values['activity'] = activity[name]
            values = {k: float(_format(v)) for k, v in values.items()}  # memberships use the stored 4-decimal values, as check() and devices do
            options = preset_facets.memberships(values, styles.get(name, set()), definition)
            for option in options:
                counts[option] += 1
            lines.append('\t'.join([name, ','.join(options)] + [_format(values.get(c)) for c in COLUMNS]))
        else:
            lines.append('\t'.join([name, ''] + ['-'] * len(COLUMNS)))
    attributes = ('\n'.join(lines) + '\n').encode()
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    (output / 'facets.json').write_bytes(definition_bytes)
    (output / 'attributes.tsv').write_bytes(attributes)
    manifest = {'schema': SCHEMA, 'version': MANIFEST_VERSION, 'definition_sha256': _sha(definition_bytes),
                'presets_idx_sha256': _sha(Path(presets_idx).read_bytes()), 'attributes_sha256': _sha(attributes),
                'preset_count': len(names), 'measured_count': len(measured), 'ruler': ruler,
                'style_facts': {'header': style_header, 'sha256': _sha(Path(style_tsv).read_bytes())},
                'ruler_results_manifest_sha256': _sha(Path(ruler_manifest).read_bytes()),
                'option_counts': counts}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    return manifest


DEFAULT_RULER_MANIFEST = Path('docs/superpowers/evidence/mood-facets-ruler-2026-10-12/ruler-results-manifest.json')


def check(bundle_dir, presets_idx, definition_path=None, ruler_manifest=None, presets_dir=None):
    bundle = Path(bundle_dir); problems = []
    definition_path = Path(definition_path or preset_facets.DEFINITION)
    try:
        manifest = json.loads((bundle / 'manifest.json').read_text())
        attributes = (bundle / 'attributes.tsv').read_bytes()
        shipped = (bundle / 'facets.json').read_bytes()
    except (OSError, ValueError) as error:
        return ['bundle unreadable: %s' % error]
    if shipped != definition_path.read_bytes():
        problems.append('facets.json differs from the definition')
    reference = None
    try:
        reference = load_activity_reference(json.loads(definition_path.read_bytes()), definition_path)
    except (OSError, KeyError, ValueError) as error:
        problems.append('activity reference unusable: %s' % error)
    if manifest.get('definition_sha256') != _sha(shipped):
        problems.append('manifest definition hash is stale')
    if manifest.get('presets_idx_sha256') != _sha(Path(presets_idx).read_bytes()):
        problems.append('presets.idx changed since the bundle was built')
    recorded = manifest.get('ruler_results_manifest_sha256')
    if not recorded:
        problems.append('manifest records no ruler results manifest hash')
    evidence = None
    if ruler_manifest is None:
        problems.append('ruler results manifest evidence path is required')
    else:
        try:
            if recorded and _sha(Path(ruler_manifest).read_bytes()) != recorded:
                problems.append('ruler results manifest evidence differs from the bundle manifest hash')
            evidence = _manifest_entries(ruler_manifest)
            problems += preset_asset_problems(_index_names(presets_idx), evidence,
                                              _presets_dir(presets_idx, presets_dir))
        except (OSError, KeyError, ValueError) as error:
            problems.append('ruler results manifest evidence unreadable: %s' % error)
    if manifest.get('attributes_sha256') != _sha(attributes):
        problems.append('attributes.tsv does not match its manifest hash')
    definition = json.loads(shipped)
    header = _header(definition, _sha(shipped))
    lines = attributes.decode().splitlines()
    if lines[:len(header)] != header:
        problems.append('attributes header differs from the definition')
    rows = [line.split('\t') for line in lines[len(header):]]
    names = [r[0] for r in rows]
    if names != sorted(_index_names(presets_idx)):
        problems.append('attributes rows do not match presets.idx names')
    state = []; mismatches = []
    counts = {o: 0 for o in preset_facets.option_ids(definition)}; measured = 0
    for row in rows:
        if len(row) != 2 + len(COLUMNS):
            problems.append('malformed row: ' + row[0]); continue
        if not all(v == '-' for v in row[2:]):
            measured += 1
        for option in (row[1].split(',') if row[1] else []):
            counts[option] = counts.get(option, 0) + 1
        if evidence is not None:
            in_evidence = (evidence.get(row[0]) or {}).get('status') == 'measured'
            if in_evidence != (not all(v == '-' for v in row[2:])):
                state.append('%s: bundle row is %s but the evidence manifest is %s' % (
                    row[0], 'measured' if not in_evidence else 'unmeasured', 'not measured' if not in_evidence else 'measured'))
        if all(v == '-' for v in row[2:]):
            if row[1]:
                problems.append('unmeasured preset has options: ' + row[0])
            continue
        if evidence is not None and (evidence.get(row[0]) or {}).get('status') == 'measured':
            metrics = evidence[row[0]].get('metrics')
            if not isinstance(metrics, dict) or list(row[2:2 + len(RULER_FIELDS)]) != [metrics.get(c) for c in COLUMNS[:-1]]:
                mismatches.append('%s: bundle values differ from the evidence manifest metrics' % row[0])
            elif not isinstance(evidence[row[0]].get('activity_inputs'), dict):
                mismatches.append('%s: evidence manifest has no activity_inputs' % row[0])
            elif reference is not None:
                expected = _format(_mid_rank(reference['mean_rank'], _mean_rank(reference, _activity_input(evidence[row[0]]['activity_inputs']))))
                if row[-1] != expected:
                    mismatches.append('%s: activity %s differs from %s recomputed from the evidence metrics' % (row[0], row[-1], expected))
        values = {c: float(v) for c, v in zip(COLUMNS, row[2:]) if v != '-'}
        options = row[1].split(',') if row[1] else []
        style = {o for o in options if o in {s['id'] for g in definition['groups'] if g['id'] == 'style' for s in g['options']}}
        if preset_facets.memberships(values, style, definition) != options:
            problems.append('attributes membership mismatch: ' + row[0])
    if mismatches:
        problems.append('bundle rows differ from the evidence manifest metrics (%d): %s' % (len(mismatches), '; '.join(mismatches[:5])))
    if state:
        problems.append('bundle rows differ from the evidence manifest measured state (%d): %s' % (len(state), '; '.join(state[:5])))
    # The generated metadata must agree with the rows it describes, like the hashes above.
    expected = {'schema': SCHEMA, 'version': MANIFEST_VERSION, 'preset_count': len(rows),
                'measured_count': measured, 'option_counts': counts}
    for field, value in expected.items():
        if manifest.get(field) != value:
            problems.append('manifest %s %s differs from %s recomputed from the bundle' % (
                field, json.dumps(manifest.get(field), sort_keys=True), json.dumps(value, sort_keys=True)))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ruler', type=Path); parser.add_argument('--style', type=Path)
    parser.add_argument('--ruler-manifest', type=Path, help='committed engine-ruler results manifest (evidence); --check defaults to %s' % DEFAULT_RULER_MANIFEST)
    parser.add_argument('--presets-idx', type=Path, default=Path('core/src/main/assets/presets.idx'))
    parser.add_argument('--presets-dir', type=Path, help='bundled preset files hashed against the evidence (default: presets/ next to --presets-idx)')
    parser.add_argument('--bundle', type=Path, default=Path('core/src/main/assets/preset-attributes'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--write-evidence-manifest', type=Path, metavar='OUTPUT',
                        help='write the evidence manifest with per-row metrics from --ruler and --ruler-manifest (the source manifest)')
    parser.add_argument('--freeze-activity-reference', type=Path, metavar='OUTPUT',
                        help='write the frozen activity reference from --ruler and --ruler-manifest (once per definition version)')
    args = parser.parse_args(argv)
    if args.freeze_activity_reference:
        if not args.ruler or not args.ruler_manifest:
            parser.error('--ruler and --ruler-manifest are required to freeze the activity reference')
        print(freeze_activity_reference(args.ruler, args.freeze_activity_reference, args.ruler_manifest, args.presets_idx, args.presets_dir))
        return
    if args.write_evidence_manifest:
        if not args.ruler or not args.ruler_manifest:
            parser.error('--ruler and --ruler-manifest are required to write the evidence manifest')
        write_evidence_manifest(args.ruler, args.ruler_manifest, args.write_evidence_manifest)
        return
    if args.check:
        problems = check(args.bundle, args.presets_idx, ruler_manifest=args.ruler_manifest or DEFAULT_RULER_MANIFEST, presets_dir=args.presets_dir)
        for problem in problems:
            print(problem)
        raise SystemExit(1 if problems else 0)
    if not args.ruler or not args.style or not args.ruler_manifest:
        parser.error('--ruler, --style and --ruler-manifest are required to build')
    print(json.dumps({k: v for k, v in build(args.ruler, args.style, args.presets_idx, args.bundle, ruler_manifest=args.ruler_manifest, presets_dir=args.presets_dir).items() if k != 'option_counts'}))


if __name__ == '__main__':
    main()
