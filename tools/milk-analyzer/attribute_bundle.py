"""Mood facet attribute bundle: engine-ruler measurements + source style facts -> Android assets.

build() writes preset-attributes/{facets.json, attributes.tsv, manifest.json}; check() verifies the
bundle against presets.idx, the definition, its frozen activity reference and its manifest, and
recomputes every membership from the stored values and style options. Activity is scored against the
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


def freeze_activity_reference(ruler_dir, output, ruler_manifest):
    """Writes the activity reference once from the measured corpus; returns its sha256."""
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
    styles = {}
    for line in lines[1:]:
        name, _digest, found = line.split('\t')
        values = {s for s in found.split(',') if s}
        if values - STYLES:
            raise ValueError('unknown style in %s: %s' % (name, sorted(values - STYLES)))
        styles[name] = values
    return lines[0], styles


def _format(value):
    return '-' if value is None else '%.4f' % value


def _header(definition, definition_sha):
    lines = ['#%s\t1' % SCHEMA, '#definition\t' + definition_sha]
    for group in definition['groups']:
        lines.append('#group\t%s\t%s' % (group['id'], group['label']))
        lines += ['#option\t%s\t%s\t%s' % (group['id'], o['id'], o['label']) for o in group['options']]
    lines.append('#columns\tname\toptions\t' + '\t'.join(COLUMNS))
    return lines


def build(ruler_dir, style_tsv, presets_idx, output_dir, definition_path=None, ruler_manifest=None):
    definition_path = Path(definition_path or preset_facets.DEFINITION)
    definition_bytes = definition_path.read_bytes(); definition = json.loads(definition_bytes)
    reference = load_activity_reference(definition, definition_path)
    names = _index_names(presets_idx)
    rows, ruler = _measured_rows(ruler_dir)
    style_header, styles = _read_style(style_tsv)
    measured = [rows[n] for n in names if n in rows]
    activity = activity_values(measured, reference)
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
    manifest = {'schema': SCHEMA, 'version': 1, 'definition_sha256': _sha(definition_bytes),
                'presets_idx_sha256': _sha(Path(presets_idx).read_bytes()), 'attributes_sha256': _sha(attributes),
                'preset_count': len(names), 'measured_count': len(measured), 'ruler': ruler,
                'style_facts': {'header': style_header, 'sha256': _sha(Path(style_tsv).read_bytes())},
                'ruler_results_manifest_sha256': _sha(Path(ruler_manifest).read_bytes()) if ruler_manifest else None,
                'option_counts': counts}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    return manifest


def check(bundle_dir, presets_idx, definition_path=None):
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
    try:
        load_activity_reference(json.loads(definition_path.read_bytes()), definition_path)
    except (OSError, KeyError, ValueError) as error:
        problems.append('activity reference unusable: %s' % error)
    if manifest.get('definition_sha256') != _sha(shipped):
        problems.append('manifest definition hash is stale')
    if manifest.get('presets_idx_sha256') != _sha(Path(presets_idx).read_bytes()):
        problems.append('presets.idx changed since the bundle was built')
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
    for row in rows:
        if len(row) != 2 + len(COLUMNS):
            problems.append('malformed row: ' + row[0]); continue
        if all(v == '-' for v in row[2:]):
            if row[1]:
                problems.append('unmeasured preset has options: ' + row[0])
            continue
        values = {c: float(v) for c, v in zip(COLUMNS, row[2:]) if v != '-'}
        options = row[1].split(',') if row[1] else []
        style = {o for o in options if o in {s['id'] for g in definition['groups'] if g['id'] == 'style' for s in g['options']}}
        if preset_facets.memberships(values, style, definition) != options:
            problems.append('attributes membership mismatch: ' + row[0])
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ruler', type=Path); parser.add_argument('--style', type=Path)
    parser.add_argument('--ruler-manifest', type=Path, help='committed engine-ruler results manifest (evidence)')
    parser.add_argument('--presets-idx', type=Path, default=Path('core/src/main/assets/presets.idx'))
    parser.add_argument('--bundle', type=Path, default=Path('core/src/main/assets/preset-attributes'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--freeze-activity-reference', type=Path, metavar='OUTPUT',
                        help='write the frozen activity reference from --ruler and --ruler-manifest (once per definition version)')
    args = parser.parse_args(argv)
    if args.freeze_activity_reference:
        if not args.ruler or not args.ruler_manifest:
            parser.error('--ruler and --ruler-manifest are required to freeze the activity reference')
        print(freeze_activity_reference(args.ruler, args.freeze_activity_reference, args.ruler_manifest))
        return
    if args.check:
        problems = check(args.bundle, args.presets_idx)
        for problem in problems:
            print(problem)
        raise SystemExit(1 if problems else 0)
    if not args.ruler or not args.style:
        parser.error('--ruler and --style are required to build')
    print(json.dumps({k: v for k, v in build(args.ruler, args.style, args.presets_idx, args.bundle, ruler_manifest=args.ruler_manifest).items() if k != 'option_counts'}))


if __name__ == '__main__':
    main()
