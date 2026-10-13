"""Dependency-free validation of SDK exports against their export-contract JSON Schemas.

Supports the draft 2020-12 keywords the contract schemas use: type, const, enum, required,
properties, items, minItems, maxItems, minimum, maximum, anyOf and local $ref (#/$defs/...).
Unknown keywords are ignored. jsonschema is not part of the analyzer toolchain; this subset keeps
the contract machine-checkable in the suite without a new dependency.
"""
import json
from pathlib import Path

CONTRACT = Path(__file__).resolve().parent / 'export-contract'
_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}


def _is_type(value, name):
    if name == 'number':return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == 'integer':return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def errors(value, schema, root=None, path='$'):
    """List of 'path: message' strings; empty when value conforms."""
    root = schema if root is None else root
    found = []
    if '$ref' in schema:
        ref = schema['$ref']
        if not ref.startswith('#/'):raise ValueError('only local $ref is supported: ' + ref)
        target = root
        for part in ref[2:].split('/'):target = target[part]
        found += errors(value, target, root, path)
    if 'anyOf' in schema and not any(not errors(value, option, root, path) for option in schema['anyOf']):
        found.append(path + ': matches no anyOf alternative')
    if 'const' in schema and value != schema['const']:
        found.append(path + ': expected %r' % (schema['const'],))
    if 'enum' in schema and value not in schema['enum']:
        found.append(path + ': %r not in %r' % (value, schema['enum']))
    if 'type' in schema:
        names = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_is_type(value, name) for name in names):
            return found + [path + ': expected type %s' % '/'.join(names)]
    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:found.append(path + ': missing required %r' % key)
        for key, sub in schema.get('properties', {}).items():
            if key in value:found += errors(value[key], sub, root, path + '.' + key)
    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:found.append(path + ': fewer than %d items' % schema['minItems'])
        if 'maxItems' in schema and len(value) > schema['maxItems']:found.append(path + ': more than %d items' % schema['maxItems'])
        if 'items' in schema:
            for index, item in enumerate(value):found += errors(item, schema['items'], root, '%s[%d]' % (path, index))
    if _is_type(value, 'number'):
        if 'minimum' in schema and value < schema['minimum']:found.append(path + ': below minimum %r' % schema['minimum'])
        if 'maximum' in schema and value > schema['maximum']:found.append(path + ': above maximum %r' % schema['maximum'])
    return found


def load_schema(name):
    return json.loads((CONTRACT / name).read_text())


def recipe_errors(recipe):
    """Contract errors of a preset_recipe.build_recipe result (empty list when valid)."""
    return errors(json.loads(json.dumps(recipe)), load_schema('preset-recipe.schema.json'))
