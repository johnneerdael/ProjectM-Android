"""Preset recipes conform to export-contract/preset-recipe.schema.json; the validator rejects drift."""
import copy
import json
import os
from pathlib import Path

import pytest

from contract_schema import errors, recipe_errors
from preset_recipe import build_recipe


def test_validator_reports_type_required_range_and_ref_errors():
    schema = {'type': 'object', 'required': ['a'], 'properties': {'a': {'$ref': '#/$defs/p'}, 'b': {'anyOf': [{'type': 'null'}, {'type': 'string'}]}},
              '$defs': {'p': {'type': 'number', 'minimum': 0, 'maximum': 1}}}
    assert errors({'a': .5, 'b': None}, schema) == []
    assert errors({}, schema) == ["$: missing required 'a'"]
    assert errors({'a': 2}, schema) == ['$.a: above maximum 1']
    assert errors({'a': .5, 'b': 3}, schema) == ['$.b: matches no anyOf alternative']
    assert errors({'a': True}, schema) == ['$.a: expected type number']  # booleans are not numbers


def _synthetic_recipe():
    import test_preset_recipe as T
    return build_recipe(T.record())


def test_recipe_from_source_facts_conforms_to_the_contract():
    assert recipe_errors(_synthetic_recipe()) == []


def test_contract_rejects_changed_meaning_or_out_of_range_values():
    recipe = _synthetic_recipe()
    broken = copy.deepcopy(recipe); broken['policy'] = 'preset-visual-recipe-v2'
    assert any('policy' in e for e in recipe_errors(broken))
    broken = copy.deepcopy(recipe)
    broken['render']['composite']['per_load_random'] = {'switches': [{'component': 'x', 'condition': '>= 0.4', 'probability_true': 1.5}],
                                                        'continuous_components': []}
    assert any('probability_true: above maximum' in e for e in recipe_errors(broken))
    broken = copy.deepcopy(recipe); del broken['render']['layers']
    assert any("missing required 'layers'" in e for e in recipe_errors(broken))


def test_fresh_export_recipe_conforms_when_provided():
    path = os.environ.get('PRESET_UNDERSTANDING_FRESH_EXPORT')
    if path is None:
        pytest.skip('set PRESET_UNDERSTANDING_FRESH_EXPORT to a fresh source export')
    from preset_understanding import summarize_preset
    recipe = build_recipe(summarize_preset(json.loads(Path(path).read_text())))
    assert recipe_errors(recipe) == []
