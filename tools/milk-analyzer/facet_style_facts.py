"""Facet style facts (kaleidoscope, tunnel, liquid, geometric, particles, fractal) from source summaries.

Mechanisms are proven program constructions; structure scores are the approximate mood features.
Rules are the Mood facets definition's style_rules; no rendered image or simulation is used.
"""
import argparse, base64, gzip, json, subprocess
from pathlib import Path

STYLES = ('kaleidoscope', 'tunnel', 'liquid', 'geometric', 'particles', 'fractal')
MECHANISMS = {
    'kaleidoscope': {'angular_mirror_fold', 'cartesian_mirror_fold'},
    'tunnel': {'polar_radial_sampling', 'radial_feedback_transform'},
    'liquid': {'image_driven_advection', 'gradient_driven_advection'},
    'geometric': set(),
    'particles': {'point_cloud_primitive', 'procedural_point_motion'},
    'fractal': {'nonlinear_feedback_map', 'complex_quadratic_recurrence'},
}
SCORES = {'kaleidoscope': ('structure.symmetry', .55), 'liquid': ('structure.organic', .6),
          'geometric': ('structure.geometric', .6), 'fractal': ('structure.fractal', .6)}


def _mechanisms(summary):
    return {item['value'].get('mechanism') for item in (summary.get('facts') or {}).get('construction', [])
            if str(item.get('path', '')).startswith('/analysis/families/') and isinstance(item.get('value'), dict)}


def _features(summary):
    if isinstance(summary.get('approximate_mood_features'), dict):
        return summary['approximate_mood_features']
    from approximate_features import feature_vector
    return feature_vector(summary)


def style_facts(summary):
    mechanisms = _mechanisms(summary)
    features = _features(summary)
    found = []
    for style in STYLES:
        hit = bool(mechanisms & MECHANISMS[style])
        if not hit and style in SCORES:
            name, threshold = SCORES[style]
            value = (features.get(name) or {}).get('value')
            hit = type(value) in (int, float) and value >= threshold
        if hit:
            found.append(style)
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('results', type=Path, help='whole-pack results directory (corpus_understanding)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    rows = []
    for path in sorted(args.results.glob('*.json')):
        row = json.loads(path.read_text())
        if row.get('status') != 'computed' or not row.get('summary_gzip_base64'):
            continue
        summary = json.loads(gzip.decompress(base64.b64decode(row['summary_gzip_base64'])))
        rows.append((row['name'], row['sha256'], ','.join(style_facts(summary))))
    rows.sort()
    with args.output.open('w') as out:
        out.write('#projectm-tv-facet-style-facts\t1\t%s\n' % sha)
        for name, digest, styles in rows:
            out.write('%s\t%s\t%s\n' % (name, digest, styles))
    print(json.dumps({'presets': len(rows), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
