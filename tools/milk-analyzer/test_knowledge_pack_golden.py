"""Golden reader vectors: the reference reader accepts and rejects exactly what every reader must."""
import json
import math
import shutil
from pathlib import Path

import pytest

import knowledge_pack as K
import knowledge_pack_golden as G

EXPECTED = json.loads((G.DEFAULT / 'expected.json').read_text(encoding='utf-8'))


def _close(a, b, tolerance):
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tolerance) for k in a)
    return a == b


@pytest.mark.parametrize('pack', sorted(EXPECTED['accept']))
def test_reader_accepts_and_exposes_the_expected_view(pack):
    recipes = K.load_core(G.DEFAULT / pack)
    views = [G.view(recipes[name]) for name in recipes]
    assert _close(views, EXPECTED['accept'][pack], EXPECTED['float_tolerance'])


@pytest.mark.parametrize('pack,rule', sorted(EXPECTED['reject'].items()))
def test_reader_rejects_a_pack_breaking_one_rule(pack, rule):
    with pytest.raises(ValueError, match=rule):
        K.load_core(G.DEFAULT / pack)


def test_vectors_regenerate_byte_for_byte(tmp_path):
    shutil.copytree(G.DEFAULT / 'recipes', tmp_path / 'recipes')
    G.generate(tmp_path)
    for path in sorted(G.DEFAULT.rglob('*')):
        if path.is_file():
            assert (tmp_path / path.relative_to(G.DEFAULT)).read_bytes() == path.read_bytes(), path
