"""Mood facet memberships and selection (standard library).

Facet groups combine OR within a group and AND across groups; a group without a selection means
"any". Memberships come from the frozen definition (facets/facets-v1.json): metric thresholds on
display statistics and source style facts. The Java PresetFacets mirrors select() exactly; both
run fixtures/facet-selection-vectors-v1.json.
"""
import json
from pathlib import Path

DEFINITION = Path(__file__).with_name('facets') / 'facets-v1.json'
_OPS = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}


def load_definition(path=None):
    return json.loads(Path(path or DEFINITION).read_text())


def option_ids(definition):
    return [option['id'] for group in definition['groups'] for option in group['options']]


def group_of(definition):
    return {option['id']: group['id'] for group in definition['groups'] for option in group['options']}


def _holds(condition, values, style, members):
    if 'metric' in condition:
        value = values.get(condition['metric'])
        return type(value) in (int, float) and _OPS[condition['op']](float(value), float(condition['value']))
    if 'style' in condition:
        return condition['style'] in style
    if 'not_option' in condition:
        return condition['not_option'] not in members
    raise ValueError('unknown facet condition: ' + json.dumps(condition))


def memberships(values, style, definition):
    """Option ids a preset belongs to; options are evaluated in definition order (not_option sees earlier ones)."""
    members = []
    for group in definition['groups']:
        for option in group['options']:
            if all(_holds(c, values, style, members) for c in option['all']):
                members.append(option['id'])
    return members


def _pool(rows, selected, groups, excluded):
    by_group = {}
    for option in selected:
        by_group.setdefault(groups[option], set()).add(option)
    return [row['name'] for row in rows if row['name'] not in excluded
            and all(set(row['options']) & wanted for wanted in by_group.values())]


def select(rows, selected, definition, excluded=()):
    groups = group_of(definition)
    excluded = set(excluded)
    chosen = [option for option in dict.fromkeys(selected) if option in groups]
    ignored = [option for option in dict.fromkeys(selected) if option not in groups]
    pool = _pool(rows, chosen, groups, excluded)
    counts = {}
    for option in option_ids(definition):
        toggled = [o for o in chosen if o != option] if option in chosen else chosen + [option]
        counts[option] = len(_pool(rows, toggled, groups, excluded))
    dimmed = [option for option, count in counts.items() if count == 0 and option not in chosen]
    return {'selected': chosen, 'ignored': ignored, 'pool': pool, 'count': len(pool),
            'option_counts': counts, 'dimmed': dimmed}
