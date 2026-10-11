"""The SDK-fact illustrator uses closed-form maps and abstains without facts."""
import numpy as np
import pytest

from prediction_illustration import _retained_radius,illustrate,_spread_sigma


@pytest.mark.parametrize('a,b',[(0.9995139837265015,.01),(1.0,.02),(1.01,0.0)])
def test_closed_form_matches_iterated_inverse_feature_map(a,b):
    radius=np.array([.05,.3,.6])
    iterated=radius.copy()
    for _ in range(25):iterated=a*iterated/(1-b*iterated)
    assert np.allclose(_retained_radius(radius,{'a':a,'b':b},25),iterated,rtol=1e-12)


def test_summary_without_supported_facts_draws_nothing_and_says_why():
    summary={'policy':'preset-understanding-v1','facts':{'context':[{'path':
        '/analysis/visual_description/static_behaviour/context','value':{'viewport':[64,36],'feedback_fps':30}}]}}
    image,used,limitations=illustrate(summary,time=1.0,fps=30.0,history_steps=4)
    assert image.shape==(36,64,3) and not image.any()
    assert used==[]
    assert limitations


def test_spread_reference_uses_uniform_offset_variance():
    spread={'per_step_variance_uniform_offset_reference_texels2':1/6}
    assert _spread_sigma(spread,6)==pytest.approx(1.0)
    assert _spread_sigma(None,6)==0.0
